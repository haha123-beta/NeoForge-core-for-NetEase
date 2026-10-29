"""Compile-time project static imports and demand-driven candidate sets."""
import ast
from java_integer_literals import INTEGER_KINDS, literal_value


def constants(ir, cls):
    result = {}
    data = ir['source_utf8'].encode('utf-8')
    for member in cls['fields']:
        node = member.get('initializer')
        if not (member['static'] and member['final'] and node): continue
        raw = data[node['span'][0]:node['span'][1]].decode('utf-8')
        kind, declared = node['kind'], member['declared_type']
        try:
            if declared == 'int' and kind in INTEGER_KINDS:
                value, width = literal_value(node, raw, ValueError)
                if width != 32: continue
                code = str(value)
            elif declared == 'boolean' and kind in ('true','false'):
                code = 'True' if kind == 'true' else 'False'
            elif declared in ('String','java.lang.String') and kind == 'string_literal' and '\\' not in raw:
                code = '_nc_String(' + repr(ast.literal_eval(raw)) + ')'
            else: continue
        except (ValueError, TypeError): continue
        result[member['name']] = {'type': 'java.lang.String' if declared == 'String' else declared, 'code': code}
    return result


def plan(ir, project_types, error_type):
    """Keep field/method namespaces and single/on-demand import precedence apart."""
    result = {}
    def add(name, slot, binding, explicit, item):
        bucket = result.setdefault(name, {})
        mode = slot + '_explicit'
        if bucket.get(mode) and not explicit: return
        if explicit and not bucket.get(mode): bucket[slot] = []
        bucket[mode] = bool(explicit or bucket.get(mode))
        values = bucket.setdefault(slot, [])
        if not any(value['owner'] == binding['owner'] for value in values): values.append(binding)
        if slot == 'constants' and explicit and len(values) > 1:
            raise error_type(item, 'Conflicting explicit static field imports: ' + name)

    for item in ir['imports']:
        if not item['static']: continue
        explicit = not item['wildcard']
        identity = item['name'].removesuffix('.*') if not explicit else item['name'].rpartition('.')[0]
        records = project_types.get(identity, [])
        if len(records) != 1:
            raise error_type(item, 'Static import requires one project source owner: ' + identity)
        record = records[0]; owner = record.get('inheritance_metadata', {})
        if (not record['layout_matches_package'] or len(record['attribute_chain']) != 1
                or not owner.get('package') or record['kind'] != 'class_declaration' or 'public' not in owner.get('modifiers', [])):
            raise error_type(item, 'Static import owner layout/access/kind requires lowering: ' + identity)
        if owner.get('superclass'):
            raise error_type(item, 'Inherited static import lookup requires declaring-owner resolution')
        def importable(member):
            modifiers = member.get('modifiers', [])
            return member.get('static') and ('public' in modifiers or
                (owner['package'] == ir.get('package') and 'private' not in modifiers))
        if explicit:
            names = [item['name'].rsplit('.', 1)[-1]]
        else:
            names = sorted({member['name'] for member in owner['methods'] + owner['fields']
                if importable(member) and not member.get('constructor')})
        for name in names:
            found = False
            methods = [method for method in owner['methods'] if not method['constructor'] and method['name'] == name]
            accessible = [method for method in methods if importable(method)]
            if accessible:
                # Preserve the original declaring context, but only expose the
                # accessible static candidates to import resolution.
                binding = {'owner': identity, 'declaration': dict(owner, external=True),
                    'methods': accessible, 'name': name, 'item': item}
                add(name, 'methods', binding, explicit, item); found = True
            fields = [member for member in owner['fields'] if member['name'] == name and importable(member)]
            if fields:
                constant = record.get('static_import_constants', {}).get(name)
                binding = dict(constant or {}, owner=identity, item=item)
                if len(fields) != 1 or constant is None:
                    binding['error'] = 'Static import nonliteral/mutable field requires lowering: ' + name
                elif constant['type'] == 'java.lang.String' and fields[0]['declared_type'] == 'String':
                    other = any(not imp['static'] and not imp['wildcard'] and imp['name'].endswith('.String')
                        and imp['name'] != 'java.lang.String' for imp in owner.get('imports', []))
                    if other or owner['package'] + '.String' in project_types:
                        binding['error'] = 'Static String constant type is shadowed and requires resolution'
                add(name, 'constants', binding, explicit, item); found = True
            if explicit and not found:
                raise error_type(item, 'Static import member is missing or inaccessible: ' + name)
    return result
