"""Reviewed ImmutableMap factories. Generic source libraries remain separate."""
MAP='com.google.common.collect.ImmutableMap';BUILDER=MAP+'.Builder'

def resolve(raw,base,name,arity,actual,canonical):
    if base not in (MAP,BUILDER):return None
    from java_library_signatures import generic_arguments
    args=generic_arguments(raw)
    parameters=[canonical(a) for a in args]
    suffix='<'+','.join(parameters)+'>' if len(parameters)==2 else ''
    static=base==MAP and name in ('of','copyOf','builder');row=None
    if base==MAP and name=='of' and arity==0:
        return {'return_type':MAP,'parameters':[],'receiver_kind':'game_api','static_owner':MAP,'polymorphic_empty_collection':'map'}
    if base==MAP and name=='copyOf' and arity==1 and actual[0]:
        if actual[0]=='<poly-empty-map>':return {'return_type':MAP,'parameters':['java.util.Map'],'receiver_kind':'game_api','static_owner':MAP,'polymorphic_empty_collection':'map'}
        source=actual[0];source_base=source.split('<',1)[0]
        if source_base not in ('java.util.Map','java.util.HashMap','java.util.LinkedHashMap',MAP):raise ValueError('ImmutableMap.copyOf requires a typed reviewed map')
        types=generic_arguments(source)
        if len(types)!=2:raise ValueError('ImmutableMap.copyOf needs two concrete type arguments')
        suffix='<'+','.join(canonical(a) for a in types)+'>'
        row=(MAP+suffix,[source])
    elif base==MAP and name=='builder' and not arity:row=(BUILDER,[])
    elif base==BUILDER and name in ('build','buildOrThrow') and not arity:row=(MAP+suffix,[])
    elif base==BUILDER and name=='put' and len(parameters)==2:row=(BUILDER+suffix,parameters)
    elif base==BUILDER and name=='putAll' and len(parameters)==2:row=(BUILDER+suffix,['java.util.Map'+suffix])
    elif base==MAP:
        result=parameters[1] if len(parameters)==2 else 'java.lang.Object'
        row={'size':('int',[]),'isEmpty':('boolean',[]),'get':(result,['java.lang.Object']),'getOrDefault':(result,['java.lang.Object',result]),'containsKey':('boolean',['java.lang.Object']),'containsValue':('boolean',['java.lang.Object']),'equals':('boolean',['java.lang.Object']),'hashCode':('int',[])}.get(name)
    if row is None:raise ValueError('Guava ImmutableMap API requires review: '+name)
    result,formal=row
    if arity!=len(formal) or any(a!=f and a!='<null>' and f!='java.lang.Object' for a,f in zip(actual,formal)):raise ValueError('ImmutableMap argument signature mismatch: '+name)
    data={'return_type':result,'parameters':formal,'receiver_kind':'game_api'}
    if static:data['static_owner']=MAP
    return data
