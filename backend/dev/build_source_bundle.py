from workspace_paths import SCRIPTS_ROOT as _PROJECT_SCRIPTS
"""Build a source snapshot without modifying original package paths or copying NeoCore into content."""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import re

SCRIPTS = Path(_PROJECT_SCRIPTS)


def collect_sources(root):
    root = Path(root).resolve()
    sources = {}
    for path in sorted(root.rglob('*.py')):
        if root not in path.resolve().parents:
            raise ValueError('Source link escapes input tree: ' + str(path))
        relative = path.relative_to(root)
        parts = list(relative.with_suffix('').parts)
        package = parts[-1] == '__init__'
        if package:
            parts.pop()
        if not parts:
            continue
        if any(not re.fullmatch(r'[^\W\d]\w*', part) for part in parts):
            raise ValueError('Invalid Python module path: ' + str(relative))
        name = '.'.join(parts)
        if name in sources:
            raise ValueError('Module/package collision: ' + name)
        raw = path.read_bytes()
        sources[name] = {'source': raw.decode('utf-8-sig'), 'is_package': package,
            'origin': relative.as_posix(), 'sha256': hashlib.sha256(raw).hexdigest()}
    return sources


def content_bundle(root, entrypoints, side='BOTH'):
    spec = importlib.util.spec_from_file_location('_bundle_metadata', SCRIPTS / 'core/alpha_neoforge.py')
    metadata = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(metadata)
    index = metadata.extracted_mod_index(str(root), entrypoints, side)
    sources = collect_sources(root)
    from java_mixin_weave import validate as validate_source_weave
    adaptation=validate_source_weave(root,sources)
    if adaptation and len(index['mods']) != 1:
        raise ValueError('Source weaving requires one explicit content owner')
    for row in index['mods']:
        if adaptation:
            reviewed={config['file'] for config in adaptation['configs']}
            row['compatibility_issues']=[issue for issue in row.get('compatibility_issues',[])
                if not (issue.get('kind')=='mixin' and issue.get('source') in reviewed)]
            row['source_mixin_adaptation']={'scope':adaptation['scope'],
                'configs':sorted(reviewed),'injections':len(adaptation['injections']),
                'reference_maps':[dict(config=record['file'],**record['reference_map']) for record in adaptation['configs']],
                'jvm_execution':False,'native_engine_injection':False}
            native_entries=[entry for binding in adaptation.get('native_bindings',[]) for entry in binding['entries']]
            if native_entries:row['runtime_mixin_bindings']=native_entries
        row['source_folder'] = Path(root).name
        module, separator, attribute = row['entrypoint'].partition(':')
        if not separator or module not in sources:
            raise ValueError('Translated entrypoint source is missing: ' + row['entrypoint'])
    bundle={'schema_version': 1, 'kind': 'neocore_content_sources',
            'mods': index['mods'], 'sources': sources}
    requirement_spec=importlib.util.spec_from_file_location('_requirements_metadata',SCRIPTS/'core/runtime_requirements.py')
    requirement_module=importlib.util.module_from_spec(requirement_spec);requirement_spec.loader.exec_module(requirement_module)
    path=Path(root)/requirement_module.MANIFEST_FILE
    if path.exists():
        requirements=json.loads(path.read_text(encoding='utf-8-sig'))
        issues=requirement_module.validate(requirements,sources)
        if issues:raise ValueError('Invalid/stale generated runtime requirements: '+json.dumps(issues,ensure_ascii=False))
        bundle['runtime_requirements']=requirements
    return bundle


def core_bundle(root=SCRIPTS):
    """Package only the static/dynamic dependencies of the public runtime, not legacy disk loaders."""
    all_sources = collect_sources(root)
    tree = ast.parse(all_sources['core.java_api_catalog']['source'])
    catalog = next(ast.literal_eval(node.value) for node in tree.body
                   if isinstance(node, ast.Assign) and any(
                       isinstance(target, ast.Name) and target.id == 'API_MODULES' for target in node.targets))
    pending = list(catalog) + ['core.java_api', 'core.translated_loader',
        'core.content_registry', 'core.modsdk_entity', 'core.modsdk_network', 'core.content_events', 'core.bundled_mods',
        'core.resource_content']
    selected = {}
    while pending:
        name = pending.pop()
        if name in selected or name not in all_sources:
            continue
        record = all_sources[name]
        selected[name] = record
        parts = name.split('.')
        pending.extend('.'.join(parts[:n]) for n in range(1, len(parts)))
        source = record['source']
        tree = ast.parse(source)
        for node in ast.walk(tree):
            candidates = []
            if isinstance(node, ast.Import):
                candidates = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ''
                if node.level:
                    package = name if record['is_package'] else name.rpartition('.')[0]
                    prefix = package.split('.')[:len(package.split('.')) - node.level + 1]
                    base = '.'.join(prefix + ([base] if base else []))
                if base:
                    candidates = [base] + [base + '.' + alias.name for alias in node.names if alias.name != '*']
            for candidate in candidates:
                if candidate.split('.')[0] in ('os', 'sys', 'importlib'):
                    raise ValueError('Forbidden runtime dependency: ' + name + ' -> ' + candidate)
                if candidate in all_sources:
                    pending.append(candidate)
    return {'schema_version': 1, 'kind': 'neocore_core_sources', 'sources': selected,
            'engine_verified': False}


def write_bundle(bundle, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Bundle output already exists')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root')
    parser.add_argument('output')
    parser.add_argument('--entry', action='append', required=True, help='mod_id=package.module:start')
    parser.add_argument('--side', choices=['BOTH', 'SERVER', 'CLIENT'], default='BOTH')
    args = parser.parse_args()
    entries = dict(value.split('=', 1) for value in args.entry)
    write_bundle(content_bundle(args.root, entries, args.side), args.output)
