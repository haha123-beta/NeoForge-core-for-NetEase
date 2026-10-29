"""Reviewed project inheritance graph. External runtime classes require a separate ABI."""

def runtime_declaration(identity, contract, name, line=1):
    methods=[]
    for entry in contract['methods']:
        methods.append(dict(entry, constructor=False, modifiers=[entry['visibility']] + (['final'] if entry.get('final') else []),
            parameters=[{'name':'arg'+str(index),'declared_type':kind,'varargs':False}
                for index,kind in enumerate(entry['parameters'])], has_body=not entry['abstract'], line=line))
    for parameters in contract['constructors']:
        methods.append(dict(name=identity.rsplit('.',1)[-1], constructor=True, static=False,
            parameters=[{'name':'arg'+str(index),'declared_type':kind,'varargs':False} for index,kind in enumerate(parameters)],
            modifiers=[contract.get('constructor_visibility','protected')], return_type=None, has_body=True, line=line))
    return dict(name=name, java_name=identity, kind='class_declaration', runtime_contract=contract,
        external=True, line=line, superclass=None, interfaces=None, fields=[dict(f) for f in contract.get('fields',[])], methods=methods,
        initialization_order=[], review=[], imports=[], package=identity.rpartition('.')[0],
        modifiers=['abstract'] if contract.get('abstract') else [])
def runtime_interface_declaration(identity,contract,name,line=1):
    row=runtime_declaration(identity,dict(contract,constructors=[]),name,line)
    for method in row['methods']:
        if method['has_body']:method['modifiers'].append('default')
    row.pop('runtime_contract')
    row.update(kind='interface_declaration',runtime_interface_contract=contract)
    return row

def plan(classes, error_type, project_types=None, unit=None):
    from java_method_overloads import signature, canonical
    project_types = project_types or {}
    unit = dict(unit or {'package': None, 'imports': []}, _classes=classes, _project_types=project_types)
    local_by_java = {row['java_name']: row for row in classes}
    local_by_name = {row['name']: row for row in classes}
    parents, ordered, external = {}, [], []
    unit['_external_classes']=external
    visiting, visited, cached = set(), set(), {}
    visiting_erased=set()
    def parent_row(base, context, origin):
        if not base:
            return None
        if base in local_by_java:
            return local_by_java[base]
        head=base.split('<',1)[0].strip()
        first,separator,tail=head.partition('.')
        explicit=[item['name'] for item in context.get('imports',[]) if not item['static'] and not item['wildcard'] and item['name'].rsplit('.',1)[-1]==first]
        if len(set(explicit))>1:
            raise error_type(origin,'Conflicting superclass single-type imports: '+first)
        identity=(explicit[0]+('.'+tail if separator else '')) if explicit else (head if separator else '.'.join(filter(None,(context.get('package'),head))))
        if not explicit and not separator:
            if head in local_by_name and context is unit:identity=local_by_name[head]['java_name']
            elif identity not in project_types and (head in ('Object','Enum') or 'java.lang.'+head in unit.get('known_java_lang_api_types',[])):identity='java.lang.'+head
        if '<' in base and identity in unit.get('runtime_generic_interfaces',{}):
            from java_library_signatures import generic_arguments
            import copy
            arguments=[canonical(a.strip(),origin,unit) for a in generic_arguments(base.replace(' ',''))]
            template=copy.deepcopy(unit['runtime_generic_interfaces'][identity]);names=template['type_parameters']
            if len(arguments)!=len(names) or any(any(c in a for c in '<>[]?') for a in arguments):raise error_type(origin,'Runtime generic interface requires concrete reference type arguments')
            mapping=dict(zip(names,arguments))
            from java_generic_contracts import proves_bound,specialize
            if any(not proves_bound(mapping[key],mapping.get(bound,bound),unit,project_types) for key,bound in template.get('type_bounds',{}).items()):raise error_type(origin,'Generic bound specialization needs reviewed subtype proof')
            template=specialize(template,arguments);identity=template['java_name']
            if identity not in cached:
                row=runtime_interface_declaration(identity,template,'_nc_super_'+str(len(external)),origin['line']);cached[identity]=row;external.append(row)
            return cached[identity]
        specialization=None
        if '<' in base and len(project_types.get(identity,[]))==1:
            from java_library_signatures import generic_arguments
            from java_source_generics import specialize
            arguments=[canonical(a.strip(),origin,unit) for a in generic_arguments(base)]
            specialization=specialize(project_types[identity][0]['inheritance_metadata'],arguments,unit,project_types,error_type,origin)
        if '<' in base and specialization is None:
            raise error_type(origin,'Generic superclass type substitution requires lowering: '+identity+base[base.index('<'):],
                {'category':'generic_superclass','resolved_name':identity,'source_type':base,
                 'declaring_type':origin.get('java_name'), 'context_package':context.get('package')})
        if identity in local_by_java and specialization is None:
            return local_by_java[identity]
        records = project_types.get(identity, [])
        if not records and base in ('Object', 'java.lang.Object'):
            return None
        if not records and base in local_by_name and context is unit:
            return local_by_name[base]
        interface_contract=unit.get('runtime_interface_contracts',{}).get(identity) if not records else None
        if interface_contract is not None:
            if identity not in cached:
                row=runtime_interface_declaration(identity,interface_contract,'_nc_super_'+str(len(external)),origin['line'])
                cached[identity]=row;external.append(row)
            return cached[identity]
        contract = unit.get('runtime_superclasses', {}).get(identity) if not records else None
        if contract is not None:
            if identity in cached:return cached[identity]
            if contract.get('abi') != 1 or contract.get('java_name') != identity:
                raise error_type(origin, 'Unreviewed runtime superclass contract: ' + identity)
            row=runtime_declaration(identity,contract,'_nc_super_'+str(len(external)),origin['line'])
            if row['name'] in local_by_name:
                raise error_type(origin,'Generated runtime superclass binding collides with source class')
            cached[identity]=row;external.append(row)
            return row
        if len(records) != 1:
            raise error_type(origin, 'Unresolved/ambiguous superclass ABI: ' + identity,
                {'category':'EXTERNAL_ABI_REQUIRED','symbol':identity,'operation':'inheritance'})
        record = records[0]
        if not record['layout_matches_package'] or len(record['attribute_chain']) != 1 or record['kind'] not in ('class_declaration','interface_declaration'):
            raise error_type(origin, 'Superclass layout/kind requires lowering: ' + identity)
        cache_identity=specialization['java_name'] if specialization is not None else identity
        if cache_identity in cached:
            return cached[cache_identity]
        metadata = specialization or record.get('inheritance_metadata')
        if metadata is None:
            raise error_type(origin, 'Superclass declaration metadata is unavailable: ' + identity)
        constructors = [method for method in metadata['methods'] if method['constructor']]
        remaining_review = set(metadata['review']) - {'Inheritance resolution pending', 'Initializer block order needs semantic lowering'}
        if len({signature(method, metadata, unit) for method in constructors}) == len(constructors):
            remaining_review.discard('Overload dispatch and type erasure pending')
        if remaining_review:
            raise error_type(origin, 'Superclass declaration has unresolved semantics: ' + identity)
        row = dict(metadata, name='_nc_super_' + str(len(external)), external=True,
                   initialization_order=[], record=record)
        if row['name'] in local_by_name:
            raise error_type(origin, 'Generated superclass binding collides with source class')
        cached[cache_identity] = row
        external.append(row)
        return row
    def visit(row, context):
        identity = row['java_name']
        erased_identity=row.get('erased_java_name',identity)
        if identity in visiting or erased_identity in visiting_erased:
            raise error_type(row, 'Cyclic superclass hierarchy')
        if identity in visited:
            return
        visiting.add(identity)
        visiting_erased.add(erased_identity)
        if row['kind']=='interface_declaration':
            if row.get('superclass') or set(row.get('review',[]))-{'Overload dispatch and type erasure pending'} or any(not f['static'] or not f['final'] for f in row['fields']):
                raise error_type(row,'Unreviewed interface declaration semantics')
            if any(m.get('constructor') or
                   ('private' in m.get('modifiers',[]) and not (m.get('body') is not None or m.get('has_body'))) or
                   (not m['static'] and (m.get('body') is not None or m.get('has_body')) and not {'default','private'}&set(m.get('modifiers',[]))) for m in row['methods']):
                raise error_type(row,'Invalid interface method access/body')
        raw_interfaces=(row.get('interface_extends') if row['kind']=='interface_declaration' else row.get('interfaces')) or ''
        raw_interfaces=raw_interfaces.removeprefix('extends').removeprefix('implements').strip()
        runtime_interfaces=[]
        source_interfaces=[]
        if raw_interfaces:
            from java_library_signatures import generic_arguments
            interface_names=generic_arguments('_<'+raw_interfaces.replace(' ','')+'>')
            runtime_interfaces=[canonical(name.strip(),row,unit) for name in interface_names]
            if any(name not in ('java.lang.AutoCloseable','java.io.Closeable') for name in runtime_interfaces):
                if any(name in ('java.lang.AutoCloseable','java.io.Closeable') for name in runtime_interfaces):
                    raise error_type(row,'Mixed runtime/source interfaces require lowering')
                for name in interface_names:
                    interface=parent_row(name.strip(),context,row)
                    if interface is None or interface['kind']!='interface_declaration':
                        raise error_type(row,'Source interface declaration required')
                    if any(previous['java_name']==interface['java_name'] for previous in source_interfaces):
                        raise error_type(row,'Duplicate implemented interface')
                    visit(interface,interface if interface.get('external') else unit)
                    source_interfaces.append(interface)
                runtime_interfaces=[]
        row['runtime_interfaces']=runtime_interfaces
        row['source_interfaces']=source_interfaces
        parent = parent_row(row.get('superclass'), context, row)
        if parent is not None and parent.get('record_components') is not None:raise error_type(row,'Cannot extend a final record')
        if parent is not None and parent['kind']=='interface_declaration':
            raise error_type(row,'Class cannot extend an interface')
        if parent is not None:
            visit(parent, parent if parent.get('external') else unit)
            ancestor = parent
            names = {member['name'] for member in row['fields']}
            own_methods = {method['name'] for method in row['methods'] if not method['constructor']}
            while ancestor is not None:
                ancestor_fields = {member['name'] for member in ancestor['fields']}
                if {m.get('storage_name',m['name']) for m in row['fields']} & {m.get('storage_name',m['name']) for m in ancestor['fields']}:
                    raise error_type(row,'Inherited field storage layout requires declaring-owner separation')
                ancestor_methods = {method['name'] for method in ancestor['methods'] if not method['constructor']}
                if own_methods & ancestor_fields or names & ancestor_methods:
                    raise error_type(row, 'Inherited Java field/method namespaces collide in Python')
                if names & ancestor_fields:
                    raise error_type(row, 'Hidden Java fields require declaring-owner storage')
                if any('private' in method.get('modifiers', []) for method in ancestor['methods'] if not method['constructor']):
                    raise error_type(row, 'Private inherited method binding requires lowering')
                ancestor = parents.get(ancestor['name'])
        if runtime_interfaces:
            declaring=row
            close=None
            while declaring is not None and close is None:
                close=next((method for method in declaring['methods'] if method['name']=='close' and not method.get('constructor') and not method['parameters']),None)
                declaring=parent if declaring is row else parents.get(declaring['name'])
            if close is None or close['static'] or close['return_type']!='void' or 'public' not in close.get('modifiers',[]) or (close.get('body') is None and not close.get('has_body')):
                raise error_type(row,'AutoCloseable requires a concrete public void close() declaration')
        parents[row['name']] = parent
        generic_views={};pending=[row];seen=set()
        while pending:
            view=pending.pop()
            if view is None or id(view) in seen:continue
            seen.add(id(view));erased_view=view.get('erased_java_name',view['java_name'])
            previous=generic_views.setdefault(erased_view,view['java_name'])
            if previous!=view['java_name']:raise error_type(row,'Conflicting generic ancestor arguments: '+erased_view)
            pending.extend(view.get('source_interfaces',[]));pending.append(parents.get(view['name']))
        from java_source_generics import runtime_signature
        from java_method_overloads import family
        generic_ancestors=[];cursor=parent
        while cursor is not None:
            generic_ancestors.append(cursor);cursor=parents.get(cursor['name'])
        generic_ancestors.extend(source_interfaces)
        for ancestor in generic_ancestors:
            for inherited in ancestor['methods']:
                if inherited.get('constructor') or runtime_signature(inherited,ancestor,unit)==signature(inherited,ancestor,unit):continue
                if any(m['name']==inherited['name'] and signature(m,row,unit)==signature(inherited,ancestor,unit) for m in row['methods']) and len(family(row,inherited['name'],parents,unit))>1:
                    raise error_type(row,'Generic bridge with overload family requires lowering: '+inherited['name'])
        from java_source_interfaces import bind
        if row['kind']=='interface_declaration':row['interface_method_bindings']=[]
        else:bind(row,parents,unit,error_type)
        if not row.get('runtime_contract'):
            ancestor=parent
            runtime_ancestors=[]
            while ancestor is not None:
                if ancestor.get('runtime_contract'):runtime_ancestors.append(ancestor)
                ancestor=parents.get(ancestor['name'])
            for runtime in runtime_ancestors:
                own_names={member['name'] for member in row['fields']+row['methods']}
                if own_names & set(runtime['runtime_contract']['reserved_members']):
                    raise error_type(row,'Source member collides with runtime superclass private storage')
                from java_method_overloads import family
                for base_method in runtime['methods']:
                    if base_method.get('constructor'):continue
                    candidates=family(row,base_method['name'],parents,unit)
                    tag=signature(base_method,runtime,unit)
                    selected=next(((owner,method) for owner,method in candidates if signature(method,owner,unit)==tag),None)
                    if selected is None:continue
                    owner,method=selected
                    if 'abstract' not in row.get('modifiers',[]) and base_method.get('abstract') and (method.get('abstract') or not (method.get('body') or method.get('has_body'))):
                        raise error_type(row,'Runtime superclass abstract method requires source implementation: '+base_method['name'])
                    if owner is not runtime and base_method.get('final'):
                        raise error_type(method,'Cannot override final runtime superclass method: '+base_method['name'])
                    if owner is not runtime and (method['static']!=base_method['static'] or
                            canonical(method['return_type'],owner,unit)!=canonical(base_method['return_type'],runtime,unit) or not (set(method.get('modifiers',[])) & ({'public'} if base_method.get('visibility')=='public' else {'public','protected'}))):
                        raise error_type(method,'Runtime superclass override signature/access mismatch: '+base_method['name'])
        # Concrete descendants must implement deferred source abstract methods,
        # even if no interface or native superclass contributes that requirement.
        if row['kind']!='interface_declaration' and 'abstract' not in row.get('modifiers',[]):
            seen_methods=set();ancestor=row
            while ancestor is not None:
                for method in ancestor['methods']:
                    if method.get('constructor') or method['static'] or 'private' in method.get('modifiers',[]):continue
                    key=(method['name'],signature(method,ancestor,unit))
                    if key in seen_methods:continue
                    seen_methods.add(key)
                    if method.get('abstract') or not (method.get('body') or method.get('has_body')):
                        raise error_type(row,'Concrete class has unimplemented abstract method: '+method['name'])
                ancestor=parents.get(ancestor['name'])
        visiting.remove(identity)
        visiting_erased.remove(erased_identity)
        visited.add(identity)
        if not row.get('external'):
            ordered.append(row)
    for row in classes:
        visit(row, unit)
    return ordered, parents, external
