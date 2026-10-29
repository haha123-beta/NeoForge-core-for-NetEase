"""Reviewed feature bitset APIs; registry/codec construction is kept unresolved."""
PREFIX='net.minecraft.world.flag.'
FLAG=PREFIX+'FeatureFlag';SET=PREFIX+'FeatureFlagSet';FLAGS=PREFIX+'FeatureFlags'
def resolve(base,name,arity,actual):
    row=None;static=False;call_name=None
    if base==SET:
        if name=='of':
            static=True
            if arity==2 and actual[1] in (FLAG+'[]','<null>'):row=(SET,[FLAG,FLAG+'[]']);call_name='_of_array'
            else:row=(SET,[FLAG]*arity)
        else:row={'contains':('boolean',[FLAG]),'isEmpty':('boolean',[]),'isSubsetOf':('boolean',[SET]),'intersects':('boolean',[SET]),'join':(SET,[SET]),'subtract':(SET,[SET]),'equals':('boolean',['java.lang.Object']),'hashCode':('int',[])}.get(name)
        if row is None:raise ValueError('FeatureFlagSet API not reviewed: '+name)
    elif base==FLAGS:
        if name=='isExperimental':row=('boolean',[SET]);static=True
        else:raise ValueError('Feature registry and codec API not reviewed: '+name)
    if row is None:return None
    result,formal=row
    if len(formal)!=arity or any(a!=f and a!='<null>' and f!='java.lang.Object' for a,f in zip(actual,formal)):raise ValueError('Feature API argument mismatch: '+name)
    data={'return_type':result,'parameters':formal,'receiver_kind':'game_api'}
    if static:data['static_owner']=base
    if call_name:data['call_name']=call_name
    return data

def resolve_field(owner,name):
    target=FLAG if owner==FLAGS and name in ('VANILLA','BUNDLE','TRADE_REBALANCE') else SET if owner==FLAGS and name in ('VANILLA_SET','DEFAULT_FLAGS') else 'int' if owner==SET and name=='MAX_CONTAINER_SIZE' else None
    if target:return {'return_type':target,'static_owner':owner,'final':True,'receiver_kind':'game_api'}
    if owner in (SET,FLAGS,FLAG):raise ValueError('Feature field not reviewed: '+name)
