"""Reviewed wiring for existing text providers; no substitute runtime APIs."""
COMPONENT='net.minecraft.network.chat.Component'
MUTABLE='net.minecraft.network.chat.MutableComponent'

def resolve(base,name,arity,actual):
    record=None
    if base==COMPONENT:
        if name=='literal' and arity==1:
            record=dict(return_type=MUTABLE,parameters=['java.lang.String'],static_owner=COMPONENT,nonnull_arguments=[0])
        elif name=='empty' and arity==0:
            record=dict(return_type=MUTABLE,parameters=[],static_owner=COMPONENT)
    if base in (COMPONENT,MUTABLE) and name=='getString' and arity==0:
        record=dict(return_type='java.lang.String',parameters=[],native_string_return=True)
    if base in ('net.neoforged.fml.ModContainer','net.neoforged.fml.javafmlmod.FMLModContainer') and name=='registerConfig' and arity in (2,3):
        record=dict(return_type='void',parameters=['net.neoforged.fml.config.ModConfig.Type','net.neoforged.fml.config.IConfigSpec']+(['java.lang.String'] if arity==3 else []))
    if record is not None:
        record.update(receiver_kind='game_api',checked_arguments=True)
        if record.get('static_owner')==COMPONENT:record['type_receiver_only']=True
    return record
