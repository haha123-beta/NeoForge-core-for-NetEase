"""Project Java type identities mapped to the unchanged source-file module layout."""
from pathlib import PurePosixPath
from java_symbols import declarations


def validate_identities(ir, symbols, index, error_type):
    """Reject duplicate declarations/import bindings before generating Python aliases."""
    declared, bindings, ignored = {}, {}, set()
    for cls in symbols['classes']:
        if cls['owner']:
            continue
        identity = cls['java_name']
        records = index.get(identity, [])
        if cls['name'] in declared or len(records) > 1:
            raise error_type(cls, 'Duplicate project type declaration: ' + identity,
                {'category': 'duplicate_type', 'java_name': identity,
                 'candidates': records, 'origin': ir['origin']})
        declared[cls['name']] = identity
    for number, item in enumerate(ir['imports']):
        if item['static'] or item['wildcard']:
            continue
        identity = item['name']
        name = identity.rsplit('.', 1)[-1]
        previous = bindings.get(name)
        if previous and previous['name'] != identity:
            raise error_type(item, 'Conflicting single-type imports: ' + name,
                {'category': 'import_conflict', 'simple_name': name,
                 'imports': [previous, item]})
        if name in declared and declared[name] != identity:
            raise error_type(item, 'Import conflicts with declared top-level type: ' + name,
                {'category': 'import_declaration_conflict', 'declared': declared[name], 'import': identity})
        if previous or declared.get(name) == identity:
            ignored.add(number)
        bindings[name] = item
    return ignored


def add_unit(index, ir):
    if ir['parse_status'] != 'PARSED':
        return
    from java_source_lowering import lower
    ir=lower(ir)
    symbols = declarations(ir)
    relative = PurePosixPath(ir['origin'])
    module = '.'.join(relative.with_suffix('').parts)
    package_parts = tuple(ir['package'].split('.')) if ir['package'] else ()
    layout_matches = tuple(relative.parent.parts) == package_parts
    for cls in symbols['classes']:
        chain = cls['java_name'][len(ir['package']) + 1:] if ir['package'] else cls['java_name']
        record = {'module': module, 'attribute_chain': chain.split('.'), 'file': ir['origin'],
            'layout_matches_package': layout_matches, 'kind': cls['kind'],
            'source_sha256': ir['source_sha256'],
            'constant_strings': __import__('java_mod_metadata').constant_strings(ir,cls),
            'static_import_constants': __import__('java_static_imports').constants(ir,cls),
            'inheritance_metadata': {
                'java_name': cls['java_name'], 'name': cls['name'], 'kind': cls['kind'],
                'record_components':cls.get('record_components'), 'anonymous_codec':cls.get('anonymous_codec'), 'modifiers': cls['modifiers'],
                'line': cls['line'], 'superclass': cls['superclass'], 'interfaces': cls['interfaces'],
                'interface_extends':cls.get('interface_extends'),
                'type_parameters':cls.get('type_parameters'),
                'review': list(cls['review']), 'method_overloaded_names': cls['method_overloaded_names'],
                'package': ir.get('package'), 'imports': ir['imports'],
                'fields': [{key: value for key, value in member.items() if key != 'initializer'} for member in cls['fields']],
                'methods': [dict({key: value for key, value in member.items() if key != 'body'}, has_body=member.get('body') is not None) for member in cls['methods']]}}

        index.setdefault(cls['java_name'], []).append(record)
