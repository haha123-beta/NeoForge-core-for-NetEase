from workspace_paths import SCRIPTS_ROOT as _PROJECT_SCRIPTS
"""Modern Java CST to lossless tree IR and import triage. Code generation is a separate stage."""
import argparse
import base64
import subprocess
from bisect import bisect_left
import collections
import hashlib
import json
from pathlib import Path
import sys

DEV = Path(__file__).resolve().parent
sys.path.insert(0, str(DEV / 'vendor/java_parser'))
try:
    import tree_sitter_java
    from tree_sitter import Parser
    from java_grammar import language as parser_language
except ImportError as error:
    raise ImportError('Install dev/java_frontend_requirements.txt into dev/vendor/java_parser') from error

FEATURES = {'lambda_expression': 'lambda', 'method_reference': 'method_reference',
    'switch_expression': 'switch_expression', 'record_declaration': 'record',
    'record_pattern': 'pattern_matching', 'type_pattern': 'pattern_matching',
    'generic_type': 'generics', 'annotation': 'annotation', 'marker_annotation': 'annotation',
    'enum_declaration': 'enum', 'spread_parameter': 'varargs',
    'try_with_resources_statement': 'try_with_resources'}
PY2_KEYWORDS = frozenset(('is', 'pass', 'and', 'or', 'not', 'in', 'from', 'print', 'exec',
    'lambda', 'global', 'del', 'class', 'def', 'return', 'with', 'as', 'raise', 'yield'))


def api_index(path=None):
    path = Path(path) if path else DEV / 'java_import_index.json'
    if not path.is_file():
        return set(), True
    report = json.loads(path.read_text(encoding='utf-8'))
    root = Path(_PROJECT_SCRIPTS)
    recorded = report.get('runtime_sha256', {})
    current = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob('*.py')}
    return {name.replace('$', '.') for name in report['java_types']}, recorded != current


def parse_source(source, origin='<memory>', known_types=()):
    raw = source if isinstance(source, bytes) else source.encode('utf-8')
    text = raw.decode('utf-8-sig')
    data = text.encode('utf-8')
    language, parser_info = parser_language()
    parser = Parser(language)
    parsed_tree = parser.parse(data)
    root = parsed_tree.root_node
    known_types = set(known_types)
    contract_path = DEV / 'java_import_index.json'
    contract_index=json.loads(contract_path.read_text(encoding='utf-8')) if contract_path.is_file() else {}
    runtime_contracts = contract_index.get('runtime_superclasses', {})
    runtime_contracts = {name: row for name, row in runtime_contracts.items() if name in known_types}
    interface_contracts = contract_index.get('runtime_interface_contracts', {})
    interface_contracts = {name:row for name,row in interface_contracts.items() if name in known_types}
    runtime_enums = contract_index.get('runtime_enum_types', {})
    runtime_enums = {name: row for name, row in runtime_enums.items() if name in known_types}
    generic_interfaces=contract_index.get('runtime_generic_interfaces',{})
    generic_interfaces={n:c for n,c in generic_interfaces.items() if n in known_types}
    newlines = [index for index, byte in enumerate(data) if byte == 10]
    def position(node):
        offset = node.start_byte
        row = bisect_left(newlines, offset)
        previous = newlines[row - 1] if row else -1
        return row + 1, offset - previous
    errors, features, keywords = [], set(), []
    def convert(node):
        record = {'kind': node.type, 'span': [node.start_byte, node.end_byte],
            'line': position(node)[0]}
        if node.is_error or node.is_missing:
            errors.append({'kind': node.type, 'line': record['line'],
                'column': position(node)[1], 'missing': node.is_missing,
                'span': record['span'],
                'source': data[node.start_byte:node.end_byte].decode('utf-8')[:200]})
        if node.type in FEATURES:
            features.add(FEATURES[node.type])
        if node.type == 'object_creation_expression' and any(c.type == 'class_body' for c in node.named_children):
            features.add('anonymous_class')
        if node.type == 'method_invocation':
            name = node.child_by_field_name('name')
            if name is not None and name.text.decode('utf-8') in PY2_KEYWORDS:
                keywords.append({'line': record['line'], 'name': name.text.decode('utf-8'),
                    'strategy': 'getattr(receiver, original_name)(args)'})
        children = []
        for index, child in enumerate(node.children):
            entry = convert(child)
            field = node.field_name_for_child(index)
            if field:
                entry['field'] = field
            children.append(entry)
        if children:
            record['children'] = children
        else:
            record['text'] = data[node.start_byte:node.end_byte].decode('utf-8')
        return record
    tree = convert(root)
    imports, package = [], None
    for node in root.named_children:
        if node.type not in ('package_declaration', 'import_declaration'):
            continue
        identifier = next((c for c in node.named_children if c.type in ('identifier', 'scoped_identifier')), None)
        if identifier is None:
            continue
        name = identifier.text.decode('utf-8')
        if node.type == 'package_declaration':
            package = name
            continue
        static = any(c.type == 'static' for c in node.children)
        wildcard = any(c.type == 'asterisk' for c in node.named_children)
        owner = name.rpartition('.')[0] if static and not wildcard else name
        imports.append({'name': name + ('.*' if wildcard else ''), 'static': static,
            'wildcard': wildcard, 'line': position(node)[0],
            'known_type_identity': name in known_types,
            'known_static_owner': static and owner in known_types,
            'requires_semantic_resolution': static or wildcard or name not in known_types})
    return {'schema_version': 1, 'parser': parser_info, 'origin': origin, 'source_sha256': hashlib.sha256(raw).hexdigest(),
        'runtime_generic_interfaces':generic_interfaces, 'runtime_superclasses': runtime_contracts, 'runtime_enum_types': runtime_enums, 'runtime_interface_contracts':interface_contracts,
        'known_api_types': sorted(known_types), 'source_utf8': text, 'offsets': 'UTF-8 bytes after optional BOM removal',
        'package': package, 'imports': imports, 'features': sorted(features),
        'known_java_lang_api_types': sorted(name for name in known_types if name.startswith('java.lang.') and name.count('.') == 2),
        'known_nested_api_types': sorted(name for name in known_types if any(
            not item['static'] and not item['wildcard'] and name.startswith(item['name'] + '.')
            for item in imports)),
        'keyword_calls': keywords, 'syntax_errors': errors,
        'parse_status': 'SYNTAX_ERRORS' if root.has_error or errors else 'PARSED',
        'codegen_status': 'NOT_RUN', 'engine_verified': False, 'tree': tree}


def isolated_parse(source, origin, known_types):
    request = json.dumps({'source_base64': base64.b64encode(source).decode('ascii'),
        'origin': origin, 'known_types': sorted(known_types)}).encode('utf-8')
    process = subprocess.run([sys.executable, '-X', 'faulthandler', str(Path(__file__).resolve()), '--worker'],
        input=request, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    if process.returncode:
        raise RuntimeError('Parser worker exit ' + str(process.returncode) + ': ' +
            process.stderr.decode('utf-8', errors='replace')[-8000:])
    return json.loads(process.stdout.decode('utf-8'))


def scan(root, output=None, dry_run=False, progress=None):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError('Java input directory is missing')
    if output is not None:
        output = Path(output).resolve()
        if output.exists() or root == output or root in output.parents or output in root.parents:
            raise ValueError('Output exists or overlaps the input directory')
    if not dry_run and output is None:
        raise ValueError('Output directory required unless --dry-run')
    known, stale = api_index()
    summary = {'files': 0, 'parsed': 0, 'syntax_errors': 0, 'failed': 0,
        'api_index_stale': stale, 'python_generated': 0, 'engine_verified': False, 'results': []}
    if not dry_run:
        output.mkdir(parents=True)
    for path in sorted(root.rglob('*.java')):
        summary['files'] += 1
        relative = path.relative_to(root)
        try:
            if root not in path.resolve().parents:
                raise ValueError('Input link escapes Java root')
            ir = isolated_parse(path.read_bytes(), relative.as_posix(), known)
            category = 'parsed' if ir['parse_status'] == 'PARSED' else 'syntax_errors'
            summary[category] += 1
            row = {'file': relative.as_posix(), 'status': ir['parse_status'],
                'features': ir['features'], 'syntax_errors': ir['syntax_errors']}
            if not dry_run:
                target = output / 'ir' / relative.with_suffix('.json')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(ir, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as error:
            summary['failed'] += 1
            row = {'file': relative.as_posix(), 'status': 'FAILED', 'error': str(error)}
        summary['results'].append(row)
        if progress is not None:
            progress(summary, row)
    if not dry_run:
        (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--output')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.worker:
        request = json.loads(sys.stdin.buffer.read().decode('utf-8'))
        ir = parse_source(base64.b64decode(request['source_base64']), request['origin'], request['known_types'])
        sys.stdout.write(json.dumps(ir, ensure_ascii=True))
        sys.exit(0)
    if args.root is None:
        parser.error('Java input directory required')
    summary = scan(args.root, args.output, args.dry_run)
    print(json.dumps({k:v for k,v in summary.items() if k != 'results'}, ensure_ascii=False, indent=2))
    sys.exit(bool(summary['syntax_errors'] or summary['failed']))
