"""Compile-time overload identities and strict fixed-arity invocation selection."""
from java_value_types import BOXES,UNBOXES,widens as primitive_widens
PRIMITIVES = {'boolean','byte','short','char','int','long','float','double','void'}
JAVA_LANG = {'Object','String','Integer','Boolean','Long','Double','Float','Number','Character','Short','Byte','Class'}

BUILTIN_PARENTS = {'java.lang.Exception': 'java.lang.Throwable', 'java.lang.Error': 'java.lang.Throwable', 'java.lang.RuntimeException': 'java.lang.Exception', 'java.lang.AssertionError': 'java.lang.Error', 'java.io.IOException': 'java.lang.Exception', 'java.lang.CloneNotSupportedException': 'java.lang.Exception', 'java.lang.IllegalArgumentException': 'java.lang.RuntimeException', 'java.lang.IllegalStateException': 'java.lang.RuntimeException', 'java.lang.NullPointerException': 'java.lang.RuntimeException', 'java.lang.IndexOutOfBoundsException': 'java.lang.RuntimeException', 'java.lang.ArrayIndexOutOfBoundsException': 'java.lang.IndexOutOfBoundsException', 'java.lang.StringIndexOutOfBoundsException': 'java.lang.IndexOutOfBoundsException', 'java.lang.NumberFormatException': 'java.lang.IllegalArgumentException', 'java.lang.UnsupportedOperationException': 'java.lang.RuntimeException', 'java.lang.ArithmeticException': 'java.lang.RuntimeException', 'java.lang.ClassCastException': 'java.lang.RuntimeException', 'java.lang.NegativeArraySizeException': 'java.lang.RuntimeException', 'java.lang.ArrayStoreException': 'java.lang.RuntimeException', 'java.util.NoSuchElementException': 'java.lang.RuntimeException', 'java.util.ConcurrentModificationException': 'java.lang.RuntimeException'}

BUILTIN_PARENTS.update({BOXES[p]:'java.lang.Number' for p in ('byte','short','int','long','float','double')})


def canonical(name, owner, unit):
    if name is None:
        return None
    name = name.strip()
    if name.startswith('@methodvar:'):return name
    if name in owner.get('_method_type_bindings',{}):return owner['_method_type_bindings'][name]
    if name in PRIMITIVES or name in ('<null>','<poly-empty-map>'):
        return name
    if owner.get('type_parameters'):
        from java_source_generics import parameters
        bounds=parameters(owner['type_parameters'])
        if name in bounds:
            bound=bounds[name]
            if bound==name:raise ValueError('Cyclic generic parameter bound requires review')
            return canonical(bound,dict(owner,type_parameters=None),unit)
    if name.endswith('[]'):return canonical(name[:-2],owner,unit)+'[]'
    if '<' in name or '?' in name:
        return canonical_return(name, owner, unit)
    if '.' in name:
        context=owner if owner.get('external') else unit
        first,rest=name.split('.',1)
        imported=next((row['name'] for row in context.get('imports',[]) if not row['static'] and not row['wildcard'] and row['name'].rsplit('.',1)[-1]==first),None)
        return imported+'.'+rest if imported else name
    context = owner if owner.get('external') else unit
    explicit = [row['name'] for row in context.get('imports', []) if not row['static'] and not row['wildcard'] and row['name'].rsplit('.',1)[-1] == name]
    if len(explicit) == 1:
        return explicit[0]
    local = next((row for row in unit.get('_classes', []) if row['name']==name),None)
    if local is not None:
        return local['java_name']
    own_identity='.'.join(filter(None,(context.get('package'),name)))
    if own_identity in unit.get('_project_types',{}):return own_identity
    return 'java.lang.'+name if name in JAVA_LANG or 'java.lang.'+name in unit.get('known_java_lang_api_types',[]) else '.'.join(filter(None,(context.get('package'),name)))

def signature(method,owner,unit):
    if method.get('type_parameters'):
        from java_method_generics import context
        owner=context(owner,method,unit)
    return tuple(canonical_return(parameter['declared_type'],owner,unit) for parameter in method['parameters'])

def erased_signature(method,owner,unit):
    """Compare JVM parameter erasures while keeping full types for invocation."""
    import re
    from java_library_signatures import generic_arguments
    bounds={}
    for declaration in (owner.get('type_parameters'),method.get('type_parameters')):
        if not declaration:continue
        for value in generic_arguments('_'+declaration,allow_wildcards=True):
            parts=re.split(r'\s+extends\s+',value.strip(),maxsplit=1)
            bounds[parts[0]]=parts[1].split('&',1)[0].strip() if len(parts)==2 else 'java.lang.Object'
    def erase(kind,seen):
        kind=kind.strip()
        if kind.endswith('[]'):return erase(kind[:-2],seen)+'[]'
        depth=0;erased=[]
        for character in kind:
            if character=='<':depth+=1
            elif character=='>':depth-=1
            elif depth==0:erased.append(character)
        base=''.join(erased).strip()
        if base in bounds:
            if base in seen:raise ValueError('Cyclic generic parameter bound requires review')
            return erase(bounds[base],seen|{base})
        return canonical(base,owner,unit)
    return tuple(erase(p['declared_type'],set()) for p in method['parameters'])

def family(owner,name,parents,unit):
    entries={};chain=[]
    while owner is not None:
        chain.append(owner)
        for method in owner['methods']:
            if not method['constructor'] and method['name']==name:
                entries.setdefault(signature(method,owner,unit),(owner,method))
        owner=parents.get(owner['name'])
    for owner in chain:
        if owner['kind']=='interface_declaration':
            pending=list(owner.get('source_interfaces',[]));seen=set()
            while pending:
                interface=pending.pop(0)
                if interface['java_name'] in seen:continue
                seen.add(interface['java_name']);pending.extend(interface.get('source_interfaces',[]))
                for method in interface['methods']:
                    if method['name']==name and not method['static'] and 'private' not in method.get('modifiers',[]):
                        entries.setdefault(signature(method,interface,unit),(interface,method))
        for declaring,method in owner.get('interface_method_bindings',[]):
            if method['name']==name:entries.setdefault(signature(method,declaring,unit),(declaring,method))
        for declaring,method in owner.get('deferred_interface_methods',[]):
            if method['name']==name:entries.setdefault(signature(method,declaring,unit),(declaring,method))
    return list(entries.values())

def subtype(left,right,parents,unit):
    if left==right:return True
    if left in unit.get('_method_type_bounds',{}):
        return subtype(unit['_method_type_bounds'][left],right,parents,unit)
    if right in unit.get('_method_type_bounds',{}):return False
    from java_entity_signatures import generic_parents
    if left and any(subtype(parent,right,parents,unit) for parent in generic_parents(left,lambda a,b:subtype(a,b,parents,unit))):
        return True
    if left=='<poly-empty-map>':return right=='java.lang.Object' or right.split('<',1)[0] in ('java.util.Map','com.google.common.collect.ImmutableMap')
    if left=='<poly-empty-optional>':return right=='java.lang.Object' or right.split('<',1)[0]=='java.util.Optional'
    native=unit.get('runtime_superclasses',{});ancestor=left;seen=set()
    while ancestor in native and ancestor not in seen:
        seen.add(ancestor);ancestor=native[ancestor].get('superclass')
        if ancestor==right:return True
    if right in unit.get('runtime_interface_contracts',{}).get(left,{}).get('superinterfaces',[]):return True
    if left and '<' in left and right and '<' not in right:
        erased = canonical(left.split('<',1)[0], {}, unit)
        if erased == right:return True
    if left and right and '<' in left and '<' in right:
        from java_library_signatures import generic_arguments
        left_base=canonical(left.split('<',1)[0],{},unit);right_base=canonical(right.split('<',1)[0],{},unit)
        if left_base==right_base:
            left_args=generic_arguments(left,allow_wildcards=True);right_args=generic_arguments(right,allow_wildcards=True)
            if len(left_args)==len(right_args):
                def compatible(actual,formal):
                    actual=canonical_return(actual,{},unit);formal=canonical_return(formal,{},unit)
                    if formal=='?':return actual not in PRIMITIVES
                    if formal.startswith('? extends '):return subtype(actual,formal[10:],parents,unit)
                    if formal.startswith('? super '):return subtype(formal[8:],actual,parents,unit)
                    return actual==formal
                if all(compatible(a,f) for a,f in zip(left_args,right_args)):return True
    if left=='java.io.Closeable' and right=='java.lang.AutoCloseable':return True
    if left=='<null>':return right not in PRIMITIVES
    if left in PRIMITIVES or right in PRIMITIVES:return False
    if right=='java.lang.Object':return True
    if left and right and left.endswith('[]') and right.endswith('[]'):
        a,b=left[:-2],right[:-2]
        return a==b if a in PRIMITIVES or b in PRIMITIVES else subtype(a,b,parents,unit)
    ancestor=BUILTIN_PARENTS.get(left)
    while ancestor:
        if ancestor==right:return True
        ancestor=BUILTIN_PARENTS.get(ancestor)
    from java_official_type_hierarchy import PARENTS as OFFICIAL_PARENTS
    from java_official_event_hierarchy import PARENTS as EVENT_PARENTS
    from java_entity_signatures import PARENTS as REGISTRY_PARENTS
    pending=[left.split('<',1)[0] if left and '<' not in right else left];seen=set()
    while pending:
        identity=pending.pop()
        if identity in seen:continue
        seen.add(identity)
        for parent in tuple(OFFICIAL_PARENTS.get(identity,()))+tuple(EVENT_PARENTS.get(identity,()))+tuple(REGISTRY_PARENTS.get(identity,())):
            if parent==right:return True
            pending.append(parent)
    rows=list(unit.get('_classes',[]))+list(unit.get('_external_classes',[]))
    owner=next((row for row in rows if row['java_name']==left),None)
    if owner is None and left in unit.get('_project_types',{}) and unit.get('_resolve_type') is not None:
        owner=unit['_resolve_type'](left)
    pending=[owner];visited=set()
    while pending:
        owner=pending.pop()
        if owner is None or owner['java_name'] in visited:continue
        visited.add(owner['java_name'])
        if owner['java_name']==right:return True
        native_parent=owner.get('runtime_contract',{}).get('superclass')
        if native_parent and subtype(native_parent,right,parents,unit):return True
        if right in owner.get('runtime_interface_contract',{}).get('superinterfaces',[]):return True
        if right in owner.get('runtime_interfaces',[]):return True
        if right=='java.lang.AutoCloseable' and 'java.io.Closeable' in owner.get('runtime_interfaces',[]):return True
        pending.extend(owner.get('source_interfaces',[]))
        pending.append(parents.get(owner['name']))
    return False

def select(entries,argument_types,parents,unit,node,error_type):
    if any(value is None for value in argument_types):
        raise error_type(node,'Overload argument compile-time type is unresolved')
    def strict(actual,formal):
        return subtype(actual,formal,parents,unit) or actual in BOXES and formal in BOXES and primitive_widens(actual,formal)
    applicable=[(owner,method) for owner,method in entries if len(method['parameters'])==len(argument_types)
        and all(strict(actual,formal) for actual,formal in zip(argument_types,signature(method,owner,unit)))]
    if not applicable:
        def loose(actual,formal):
            if actual in UNBOXES and formal in BOXES:return primitive_widens(UNBOXES[actual],formal)
            if actual in BOXES:return subtype(BOXES[actual],formal,parents,unit)
            return False
        applicable=[(owner,method) for owner,method in entries if len(method['parameters'])==len(argument_types)
            and all(strict(actual,formal) or loose(actual,formal) for actual,formal in zip(argument_types,signature(method,owner,unit)))]
    if not applicable:
        expanded=[]
        for owner,method in entries:
            parameters=method['parameters']
            if method.get('constructor') or not parameters or not parameters[-1].get('varargs'):continue
            formals=signature(method,owner,unit);fixed=len(formals)-1;component=formals[-1][:-2]
            if len(argument_types)<fixed:continue
            expected=formals[:-1]+(component,)*(len(argument_types)-fixed)
            if all(strict(a,f) or loose(a,f) for a,f in zip(argument_types,expected)):
                expanded.append((owner,dict(method,_nc_varargs_expanded=True,_nc_varargs_selection=formals[:-1]+(component,)*max(1,len(argument_types)-fixed))))
        if expanded:
            maximal=[]
            for candidate in expanded:
                own=candidate[1]['_nc_varargs_selection']
                if not any(other is not candidate and other[1]['_nc_varargs_selection']!=own and len(other[1]['_nc_varargs_selection'])==len(own) and all(strict(a,b) for a,b in zip(other[1]['_nc_varargs_selection'],own)) for other in expanded):maximal.append(candidate)
            if len(maximal)!=1:raise error_type(node,'Ambiguous variable-arity overload',{'argument_types':argument_types})
            return maximal[0]
    if not applicable:
        raise error_type(node,'No strict fixed-arity overload; boxing/widening/varargs conversion requires lowering',
                         {'argument_types':argument_types,'signatures':[list(signature(m,o,unit)) for o,m in entries]})
    maximal=[]
    for candidate in applicable:
        own=signature(candidate[1],candidate[0],unit)
        if not any(other is not candidate and signature(other[1],other[0],unit)!=own and
                   all(strict(a,b) for a,b in zip(signature(other[1],other[0],unit),own)) for other in applicable):
            maximal.append(candidate)
    if len(maximal)!=1:
        raise error_type(node,'Ambiguous overload at compile time',{'argument_types':argument_types})
    return maximal[0]


def canonical_return(name,owner,unit):
    if name is None:return None
    name=name.strip()
    if name in ('<poly-empty-map>','<poly-empty-optional>'):return name
    if name.endswith('[]'):return canonical_return(name[:-2],owner,unit)+'[]'
    if name.startswith('? extends '):return '? extends '+canonical_return(name[10:],owner,unit)
    if name.startswith('? super '):return '? super '+canonical_return(name[8:],owner,unit)
    if name=='?':return name
    if name.startswith('?'):raise ValueError('Malformed wildcard type requires lowering: '+name)
    if '<' not in name:return canonical(name,owner,unit)
    from java_library_signatures import generic_arguments
    return canonical(name.split('<',1)[0],owner,unit)+'<'+','.join(canonical_return(a.replace('WILDEXTENDS:','? extends ').replace('WILDSUPER:','? super ').replace('WILDANY:','?'),owner,unit) for a in generic_arguments(name.replace('? extends ','WILDEXTENDS:').replace('? super ','WILDSUPER:').replace('?','WILDANY:')))+'>'
