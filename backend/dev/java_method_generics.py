"""Bounded source method inference with scoped variables, never bound erasure.

Only exact reference constraints and independently bounded variables are solved.
No LUB, raw argument, wildcard capture, generic overload or target-only inference.
"""
import copy,re
from java_source_generics import parameters

PREFIX='@methodvar:'

def readonly_local_type(name,declared,actual,body,canonical):
    from java_entity_signatures import HOLDER,DEFERRED_BLOCK,DEFERRED_ITEM
    base=canonical(declared)
    if base not in (HOLDER,DEFERRED_BLOCK,DEFERRED_ITEM) or not actual or actual.split('<',1)[0]!=base or '<' not in actual:return None
    def reassigned(node):
        if not node:return False
        if node['kind'] in ('assignment_expression','update_expression'):
            children=node.get('children',[])
            if any(child.get('text')==name for child in children):return True
        return any(reassigned(child) for child in node.get('children',[]))
    return None if reassigned(body) else actual

def context(owner,method,unit):
    from java_method_overloads import canonical
    names=parameters(method.get('type_parameters'))
    if not names:return owner
    if method.get('constructor'):raise ValueError('Generic constructor inference requires lowering')
    bindings={name:PREFIX+owner['java_name']+'#'+method['name']+':'+str(method.get('line',0))+':'+name for name in names}
    result=dict(owner,_method_type_bindings=bindings)
    for name,bound in names.items():
        if any(re.search(r'\b'+re.escape(v)+r'\b',bound) for v in names) or '<' in bound or '?' in bound:
            raise ValueError('Dependent, generic or recursive method bounds require lowering')
        unit.setdefault('_method_type_bounds',{})[bindings[name]]=canonical(bound,dict(owner,_method_type_bindings={}),unit)
    return result

def instantiate(owner,method,actuals,unit,parents,poly):
    from java_method_overloads import canonical_return,subtype,erased_signature,PRIMITIVES
    from java_library_signatures import generic_arguments
    from java_entity_signatures import generic_parents
    scope=context(owner,method,unit);variables=set(scope['_method_type_bindings'].values());bindings={}
    formals=[canonical_return(p['declared_type'],scope,unit) for p in method['parameters']]
    if len(formals)!=len(actuals) or any(p.get('varargs') for p in method['parameters']):raise ValueError('Generic fixed-arity method inference requires matching arguments')
    def contains(value):return any(v in value for v in variables)
    def constrain(formal,actual):
        if not contains(formal):return
        if actual is None or actual=='<null>' or actual in PRIMITIVES or '?' in actual:
            raise ValueError('Method type variable requires an exact known reference constraint')
        if formal in variables:
            if formal in bindings and bindings[formal]!=actual:raise ValueError('Conflicting method constraints require common-supertype inference')
            bindings[formal]=actual;return
        if formal.startswith('? extends '):return constrain(formal[10:],actual)
        if formal.startswith('?'):raise ValueError('Method wildcard constraint requires capture inference')
        if '<' not in formal:raise ValueError('Unsupported method type constraint')
        base=formal.split('<',1)[0];views=[actual];seen=set()
        while views:
            view=views.pop()
            if view in seen:continue
            seen.add(view)
            if view.split('<',1)[0]==base and '<' in view:
                fs=generic_arguments(formal,allow_wildcards=True);vs=generic_arguments(view,allow_wildcards=True)
                if len(fs)!=len(vs):raise ValueError('Method generic argument count differs')
                for f,a in zip(fs,vs):constrain(f,a)
                return
            views.extend(generic_parents(view,lambda a,b:subtype(a,b,parents,unit)))
        raise ValueError('Raw or unrelated generic argument cannot prove a method constraint')
    effective=list(actuals)
    for index,formal in enumerate(formals):
        if effective[index] is None:effective[index]=poly(index,formal)
        constrain(formal,effective[index])
    if set(bindings)!=variables:raise ValueError('Unconstrained method type parameter requires target inference')
    for variable,value in bindings.items():
        if not subtype(value,unit['_method_type_bounds'][variable],parents,unit):raise ValueError('Method type argument violates its declared bound')
    def replace(value):
        for key in sorted(bindings,key=len,reverse=True):value=value.replace(key,bindings[key])
        return value
    result=copy.deepcopy(method);result['type_parameters']=None
    result['_nc_runtime_signature']=erased_signature(method,owner,unit)
    result['_nc_generic_inference']={k:bindings[v] for k,v in scope['_method_type_bindings'].items()}
    for p,formal in zip(result['parameters'],formals):p['declared_type']=replace(formal)
    result['return_type']=replace(canonical_return(method['return_type'],scope,unit))
    return result,effective
