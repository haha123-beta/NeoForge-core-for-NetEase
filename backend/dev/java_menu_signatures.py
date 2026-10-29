"""Reviewed menu factory subset, with concrete generic result and parameter identities."""
MENU='net.minecraft.world.inventory.AbstractContainerMenu';TYPE='net.minecraft.world.inventory.MenuType'
FACTORY='net.neoforged.neoforge.network.IContainerFactory';EXTENSION='net.neoforged.neoforge.common.extensions.IMenuTypeExtension'
INV='net.minecraft.world.entity.player.Inventory';BUFFER='net.minecraft.network.RegistryFriendlyByteBuf'
def resolve(raw,base,name,arity,actual,canonical_generic,generic_arguments,canonical):
    row=None;static=False;call_name=None
    if base==EXTENSION and name=='create' and arity==1:
        if not actual[0]:raise ValueError('Menu factory type argument requires a concrete factory or constructor-reference target')
        factory=canonical_generic(actual[0],canonical)
        if factory.split('<',1)[0]!=FACTORY:raise ValueError('Menu extension creation requires IContainerFactory<T>')
        args=generic_arguments(factory)
        if len(args)!=1:raise ValueError('Menu factory requires one concrete type argument')
        row=(TYPE+'<'+args[0]+'>',[factory]);static=True;call_name='_nc_createType'
    elif base==TYPE:
        args=generic_arguments(raw)
        if name=='create' and len(args)==1 and arity in (2,3):row=(canonical_generic(args[0],canonical),['int',INV]+([BUFFER] if arity==3 else []))
        elif name=='requiredFeatures' and arity==0:row=('net.minecraft.world.flag.FeatureFlagSet',[])
        elif name=='isEnabled' and arity==1:row=('boolean',['net.minecraft.world.flag.FeatureFlagSet'])
        if row is None:return None
    if row is None:return None
    result,formal=row
    if len(formal)!=arity or any(a!=f and a!='<null>' and not(base==EXTENSION and a is not None and canonical_generic(a,canonical)==f) for a,f in zip(actual,formal)):raise ValueError('Menu factory argument type mismatch: '+name)
    data={'return_type':result,'parameters':formal,'receiver_kind':'game_api','functional_abi':7}
    if static:data['static_owner']=base
    if call_name:data['call_name']=call_name
    return data
