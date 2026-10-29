"""Normalize Java declarations from parser tree IR, preserving source names and scopes."""
TYPE_KINDS = {'class_declaration', 'interface_declaration', 'record_declaration', 'enum_declaration',
              'annotation_type_declaration'}


def declarations(ir):
    if ir['parse_status'] != 'PARSED':
        raise ValueError('Cannot normalize an IR containing syntax errors')
    data = ir['source_utf8'].encode('utf-8')
    classes = []
    def source(node):
        return data[node['span'][0]:node['span'][1]].decode('utf-8') if node else None
    def field(node, name):
        return next((child for child in node.get('children', []) if child.get('field') == name), None)
    def tokens(node):
        if not node:
            return []
        if 'text' in node:
            return [node['text']]
        return [text for child in node.get('children', []) for text in tokens(child)]
    def modifiers(node):
        mods = next((child for child in node.get('children', []) if child['kind'] == 'modifiers'), None)
        return tokens(mods)
    def visit(node, owners):
        if node['kind'] not in TYPE_KINDS:
            return
        name = source(field(node, 'name'))
        if name is None:
            raise ValueError('Type declaration missing its source name')
        chain = owners + [name]
        prefix = [ir['package']] if ir.get('package') else []
        row = {'name': name, 'java_name': '.'.join(prefix + chain), 'kind': node['kind'],
            'owner': '.'.join(prefix + owners) if owners else None,
            'line': node['line'], 'modifiers': modifiers(node), 'fields': [], 'methods': [], 'review': [],
            'superclass': (source(field(node, 'superclass')).removeprefix('extends').strip() if field(node, 'superclass') else None),
            'interfaces': source(field(node, 'interfaces')), 'initialization_order': []}
        row['interface_extends']=next((source(c) for c in node.get('children',[]) if c['kind']=='extends_interfaces'),None)
        row['type_parameters']=next((source(c) for c in node.get('children',[]) if c['kind']=='type_parameters'),None)
        components=ir.get('source_lowerings',{}).get('records',{}).get(name)
        row['record_components']=components
        row['anonymous_codec']=ir.get('source_lowerings',{}).get('anonymous_codecs',{}).get(name)
        classes.append(row)
        if node['kind'] in ('record_declaration', 'enum_declaration'):
            row['review'].append('Generated record/enum members need semantic lowering')
        if field(node, 'superclass') or field(node, 'interfaces'):
            row['review'].append('Inheritance resolution pending')
        body = field(node, 'body')
        for member in body.get('children', []) if body else []:
            if member['kind'] in TYPE_KINDS:
                visit(member, chain)
            elif member['kind'] in ('field_declaration', 'constant_declaration'):
                flags = modifiers(member)
                if node['kind']=='interface_declaration':flags=list(dict.fromkeys(flags+['public','static','final']))
                for declarator in member.get('children', []):
                    if declarator['kind'] == 'variable_declarator':
                        row['fields'].append({'name': source(field(declarator, 'name')),
                            'declared_type': source(field(member, 'type')) + (source(field(declarator, 'dimensions')) or ''), 'static': 'static' in flags or node['kind'] == 'interface_declaration',
                            'final': 'final' in flags or node['kind'] == 'interface_declaration', 'modifiers': flags, 'initializer': field(declarator, 'value'),
                            'line': declarator['line']})
                        row['initialization_order'].append({'kind': 'field', 'member': row['fields'][-1], 'static': row['fields'][-1]['static']})
            elif member['kind'] in ('method_declaration', 'constructor_declaration'):
                flags = modifiers(member)
                if node['kind']=='interface_declaration' and 'private' not in flags and 'public' not in flags:
                    flags.append('public')
                parameters = field(member, 'parameters')
                args = []
                for argument in parameters.get('children', []) if parameters else []:
                    if argument['kind'] in ('formal_parameter', 'spread_parameter'):
                        name_node, type_node = field(argument, 'name'), field(argument, 'type')
                        if argument['kind'] == 'spread_parameter':
                            declarator = next((child for child in argument.get('children', [])
                                if child['kind'] == 'variable_declarator'), None)
                            name_node = field(declarator, 'name') if declarator else None
                            type_node = next((child for child in argument.get('children', [])
                                if child['kind'] not in ('modifiers', '...', 'variable_declarator')), None)
                        args.append({'name': source(name_node), 'declared_type': (source(type_node) + (source(field(argument, 'dimensions')) or '') + ('[]' if argument['kind']=='spread_parameter' else '')) if type_node else None,
                            'varargs': argument['kind'] == 'spread_parameter'})
                        if name_node is None or type_node is None:
                            row['review'].append('Unresolved parameter declaration shape')
                row['methods'].append({'name': source(field(member, 'name')),
                    'type_parameters':next((source(c) for c in member.get('children',[]) if c['kind']=='type_parameters'),None),
                    'constructor': member['kind'] == 'constructor_declaration',
                    'static': 'static' in flags, 'parameters': args, 'modifiers': flags,
                    'return_type': source(field(member, 'type')), 'body': field(member, 'body'),
                    'line': member['line']})
            elif member['kind'] in ('static_initializer', 'block'):
                row['review'].append('Initializer block order needs semantic lowering')
                initializer = member if member['kind'] == 'block' else next((child for child in member.get('children', []) if child['kind'] == 'block'), None)
                row['initialization_order'].append({'kind': 'block', 'body': initializer, 'static': member['kind'] == 'static_initializer'})
        if components is not None:
            for component in components:
                member=next(f for f in row['fields'] if f['name']==component['name'] and not f['static'])
                member['storage_name']=component['storage']
                member['record_component']=True
        if components is not None:
            for method_name,return_type,params in (('equals','boolean',[{'name':'other','declared_type':'java.lang.Object','varargs':False}]),('hashCode','int',[]),('toString','java.lang.String',[])):
                if not any(m['name']==method_name and len(m['parameters'])==len(params) for m in row['methods']):
                    row['methods'].append(dict(name=method_name,constructor=False,static=False,parameters=params,modifiers=['public','final'],return_type=return_type,body={'kind':'block','children':[],'line':row['line']},line=row['line'],record_generated=method_name))
        groups = {}
        for method in row['methods']:
            groups.setdefault(method['name'], []).append(method)
        method_groups = {}
        for method in row['methods']:
            if not method['constructor']:
                method_groups.setdefault(method['name'], []).append(method)
        row['method_overloaded_names'] = sorted(name for name, methods in method_groups.items() if len(methods) > 1)
        # Java permits a private field and a method to share a spelling. Give
        # private instance storage a stable name in both indexing and generation.
        reserved={f['name'] for f in row['fields']}|set(method_groups)
        for index,member in enumerate(row['fields']):
            if member['name'] not in method_groups or member.get('storage_name') or member['static'] or 'private' not in member['modifiers']:continue
            storage='_nc_field_'+row['java_name'].encode('utf-8').hex()+'_'+str(index)
            while storage in reserved:storage+='_' 
            member['storage_name']=storage;reserved.add(storage)
        row['overloaded_names'] = sorted(name for name, methods in groups.items() if len(methods) > 1)
        if row['overloaded_names']:
            row['review'].append('Overload dispatch and type erasure pending')
    for node in ir['tree'].get('children', []):
        visit(node, [])
    return {'schema_version': 1, 'origin': ir['origin'], 'package': ir['package'],
        'imports': ir['imports'], 'classes': classes, 'source_sha256': ir['source_sha256'],
        'status': 'DECLARATIONS_ONLY', 'semantic_resolution': 'PENDING', 'python_generated': False}
