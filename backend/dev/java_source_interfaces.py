"""Java class precedence and independent source-interface contracts, before Python MRO."""
from java_method_overloads import canonical, signature, canonical_return


def bind(row, parents, unit, error_type):
    def resolved_return(method,owner):
        try:return canonical_return(method['return_type'],owner,unit)
        except ValueError as error:raise error_type(row,'Generic interface return requires lowering: '+str(error))
    chain=[];cursor=row
    while cursor is not None:
        chain.append(cursor);cursor=parents.get(cursor['name'])
    interfaces={}
    def add(interface):
        if interface['java_name'] in interfaces:return
        interfaces[interface['java_name']]=interface
        for ancestor in interface.get('source_interfaces',[]):add(ancestor)
    for owner in chain:
        for interface in owner.get('source_interfaces',[]):
            add(interface)
    row['interface_method_bindings']=[]
    row['deferred_interface_methods']=[]
    if not interfaces:return
    abstract_class='abstract' in row.get('modifiers',[])
    classes={};field_names=set()
    for owner in chain:
        field_names.update(f['name'] for f in owner['fields'] if not f.get('storage_name'))
        for method in owner['methods']:
            if not method.get('constructor'):
                key=(method['name'],signature(method,owner,unit))
                classes.setdefault(key,(owner,method))
    requirements={};families={}
    for interface in interfaces.values():
        for method in interface['methods']:
            if method.get('constructor') or method['static'] or 'private' in method.get('modifiers',[]):continue
            key=(method['name'],signature(method,interface,unit))
            requirements.setdefault(key,[]).append((interface,method))
            families.setdefault(method['name'],set()).add(key[1])
            if method['name'] in field_names:
                raise error_type(row,'Interface method collides with Java field storage: '+method['name'])
    for key,providers in requirements.items():
        from java_method_overloads import subtype
        providers=[entry for entry in providers if not any(other[0]['java_name']!=entry[0]['java_name'] and subtype(other[0]['java_name'],entry[0]['java_name'],parents,unit) for other in providers)]
        returns={resolved_return(method,owner) for owner,method in providers}
        implementation=classes.get(key)
        if implementation is not None:
            owner,method=implementation
            if method['static'] or (not abstract_class and not (method.get('body') or method.get('has_body'))) or 'public' not in method.get('modifiers',[]) or not all(return_matches(resolved_return(method,owner),expected,parents,unit) for expected in returns):
                raise error_type(row,'Interface implementation signature/access mismatch: '+key[0])
            continue
        if not any(all(return_matches(candidate,expected,parents,unit) for expected in returns) for candidate in returns):raise error_type(row,'Interface return contracts conflict: '+key[0])
        defaults=[entry for entry in providers if entry[1].get('body') or entry[1].get('has_body')]
        if not defaults:
            if abstract_class:
                row['deferred_interface_methods'].append(next(entry for entry in providers if all(return_matches(resolved_return(entry[1],entry[0]),expected,parents,unit) for expected in returns)))
                continue
            raise error_type(row,'Unimplemented abstract interface method: '+key[0])
        if len(providers)!=1:
            raise error_type(row,'Unrelated interface defaults require an explicit class override: '+key[0])
        row['interface_method_bindings'].append(defaults[0])


def return_matches(actual,expected,parents,unit):
    if actual==expected:return True
    from java_method_overloads import subtype
    if '<' not in actual and '<' not in expected and subtype(actual,expected,parents,unit):return True
    if '<? extends ' not in expected or '<' not in actual:return False
    base,bound=expected.split('<? extends ',1)
    if not bound.endswith('>') or actual.split('<',1)[0]!=base:return False
    value=actual[len(base)+1:-1]
    if any(c in value for c in '<>,?'):return False
    return subtype(value,bound[:-1],parents,unit)
