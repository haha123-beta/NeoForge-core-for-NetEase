"""Conservative source annotation identities; metadata is not runtime instrumentation."""
POLICIES = {
    'net.neoforged.fml.common.EventBusSubscriber': ('RUNTIME','AUTOMATIC_EVENT_SUBSCRIBER'),
    'net.neoforged.bus.api.SubscribeEvent': ('RUNTIME','EVENT_METHOD_REGISTRATION'),
    'net.neoforged.fml.common.Mod': ('RUNTIME','MOD_CONSTRUCTOR_ENTRYPOINT'),
    'org.jetbrains.annotations.NotNull': ('CLASS', 'NULLABILITY_INSTRUMENTATION_REVIEW_REQUIRED'),
    'org.jetbrains.annotations.Nullable': ('CLASS', 'NULLABILITY_METADATA_REVIEW_REQUIRED'),
    'javax.annotation.Nullable': ('RUNTIME', 'NULLABILITY_RUNTIME_METADATA_REVIEW_REQUIRED'),
    'java.lang.FunctionalInterface': ('RUNTIME', 'SINGLE_ABSTRACT_METHOD_CONTRACT'),
    'java.lang.SuppressWarnings': ('SOURCE', 'COMPILER_WARNING_METADATA'),
    'java.lang.Override': ('SOURCE', 'OVERRIDE_CONTRACT_REVIEW_REQUIRED'),
    'java.lang.Deprecated': ('RUNTIME','DEPRECATION_METADATA_ONLY'),
    'org.jetbrains.annotations.ApiStatus.Internal': ('CLASS','API_STATUS_METADATA_ONLY'),
    'org.jetbrains.annotations.ApiStatus.Experimental': ('CLASS','API_STATUS_METADATA_ONLY'),
}
DECLARATIONS = {'class_declaration', 'interface_declaration', 'enum_declaration',
                'record_declaration', 'annotation_type_declaration'}


def inspect_annotations(ir, project_types, error_type):
    data = ir['source_utf8'].encode('utf-8')
    def text(node):
        return data[node['span'][0]:node['span'][1]].decode('utf-8') if node else ''
    def field(node, name):
        return next((c for c in node.get('children', []) if c.get('field') == name), None)
    def walk(node, ancestors=()):
        yield node, ancestors
        for child in node.get('children', []):
            yield from walk(child, ancestors + (node,))
    nodes = list(walk(ir['tree']))
    local_types = {text(field(node, 'name')) for node, _ in nodes if node['kind'] in DECLARATIONS}
    imports = {}
    for row in ir['imports']:
        if not row['static'] and not row['wildcard']:
            names = imports.setdefault(row['name'].rsplit('.', 1)[-1], [])
            if row['name'] not in names:
                names.append(row['name'])
    records = []
    functional_declarations=set()
    for node, ancestors in nodes:
        if node['kind'] not in ('annotation', 'marker_annotation'):
            continue
        name = text(field(node, 'name'))
        identity = name if '.' in name else None
        if '.' in name:
            first,tail=name.split('.',1)
            explicit=imports.get(first,[])
            if first in local_types:identity=None
            elif len(explicit)==1:identity=explicit[0]+'.'+tail
        if identity is None and name not in local_types:
            explicit = imports.get(name, [])
            if len(explicit) == 1:
                identity = explicit[0]
            elif not explicit and name in ('SuppressWarnings', 'Override', 'FunctionalInterface','Deprecated') and not any(r['wildcard'] for r in ir['imports']):
                same_package = '.'.join(filter(None, (ir.get('package'), name)))
                if same_package not in project_types:
                    identity = 'java.lang.' + name
        if identity not in POLICIES or identity in project_types:
            raise error_type(node, 'Annotation semantics require lowering: ' + name,
                {'category': 'annotation', 'name': name, 'resolved_name': identity, 'source': text(node)})
        if identity=='javax.annotation.Nullable':
            arguments=field(node,'arguments')
            if arguments and text(arguments).strip()!='()':raise error_type(node,'javax.annotation.Nullable has no annotation elements')
        if identity.startswith('org.jetbrains.annotations.ApiStatus.'):
            arguments=field(node,'arguments')
            if arguments and text(arguments).strip()!='()':raise error_type(node,'ApiStatus marker has no annotation elements')
            target=next((a['kind'] for a in reversed(ancestors) if a['kind']!='modifiers'),None)
            if target not in DECLARATIONS|{'method_declaration','constructor_declaration','field_declaration','constant_declaration','package_declaration'}:raise error_type(node,'ApiStatus annotation target is not permitted: '+str(target))
        if identity=='java.lang.FunctionalInterface':
            declaration=next((a for a in reversed(ancestors) if a['kind'] in DECLARATIONS or a['kind'] in ('method_declaration','field_declaration','formal_parameter')),None)
            if declaration is None or declaration['kind']!='interface_declaration':
                raise error_type(node,'FunctionalInterface requires an interface declaration')
            key=tuple(declaration['span'])
            if key in functional_declarations:raise error_type(node,'Repeated FunctionalInterface annotation is not permitted')
            functional_declarations.add(key)
            arguments=field(node,'arguments')
            if arguments and text(arguments).strip()!='()':
                raise error_type(node,'FunctionalInterface has no annotation elements')
            from java_symbols import declarations
            from java_method_overloads import signature,canonical
            owner=next(row for row in declarations(ir)['classes'] if row['name']==text(field(declaration,'name')) and row['line']==declaration['line'])
            if owner['review'] or owner.get('interfaces'):
                raise error_type(node,'Functional interface inheritance/generics require lowering')
            abstract=[]
            for method in owner['methods']:
                if method['static'] or method.get('body') is not None or 'private' in method['modifiers']:continue
                tag=signature(method,owner,ir)
                if (method['name'],tag,canonical(method['return_type'],owner,ir)) in (
                    ('equals',('java.lang.Object',),'boolean'),('hashCode',(),'int'),('toString',(),'java.lang.String')):continue
                abstract.append((method['name'],tag))
            if len(set(abstract))!=1:
                raise error_type(node,'FunctionalInterface requires exactly one abstract method',{'category':'functional_interface','abstract_methods':abstract})
        retention, strategy = POLICIES[identity]
        target = next((a['kind'] for a in reversed(ancestors) if a['kind'] != 'modifiers'), None)
        records.append({'name': name, 'java_name': identity, 'line': node['line'],
            'span': list(node['span']), 'source': text(node), 'target_kind': target,
            'retention': retention, 'strategy': strategy})
    skipped_imports = {r['name'] for r in ir['imports'] if r['name'] in POLICIES or any(record['java_name'].startswith(r['name']+'.') for record in records)}
    for node, ancestors in nodes:
        if any(a['kind'] in ('annotation', 'marker_annotation', 'import_declaration') for a in ancestors):
            continue
        if text(node) in POLICIES:
            raise error_type(node, 'Annotation type used as runtime value/type requires lowering',
                             {'category': 'annotation_runtime_use', 'source': text(node)})
        if node['kind'] in ('identifier', 'type_identifier') and any(
                text(node) == name.rsplit('.', 1)[-1] for name in skipped_imports):
            raise error_type(node, 'Annotation type used as runtime value/type requires lowering',
                             {'category': 'annotation_runtime_use', 'source': text(node)})
    return records, skipped_imports
