"""Exact call metadata for already implemented, independently tested providers.

No new runtime classes. Unreviewed overloads still fall through to the strict
central guard. Origins: Java21 javap, FML4.0.42, bus8.0.5, NeoForge21.1.233.
"""
def resolve(base,name,arity,actual):
    from mining_verified_adapters098 import resolve as mined_signature
    mined=mined_signature(base,name,arity,actual)
    if mined is not None:return mined
    record=None
    def row(result,parameters,static=False,**extra):
        value=dict(return_type=result,parameters=parameters,receiver_kind='game_api',checked_arguments=True,**extra)
        if static:value['static_owner']=base
        return value
    if base=='net.minecraft.world.level.block.state.BlockBehaviour.Properties':
        if name=='of':record=row(base,[],True)
        elif name=='strength' and arity in (1,2):record=row(base,['float']*arity)
        elif name=='sound':record=row(base,['net.minecraft.world.level.block.SoundType'])
    elif base=='com.mojang.logging.LogUtils' and name=='getLogger':record=row('org.slf4j.Logger',[],True,caller_logger=True)
    elif base=='org.slf4j.Logger' and name=='info' and arity==1:record=row('void',['java.lang.String'])
    elif base=='net.neoforged.neoforge.event.BuildCreativeModeTabContentsEvent':
        if name=='getTabKey':record=row('net.minecraft.resources.ResourceKey',[])
        elif name=='accept' and arity==1:
            from java_entity_signatures import DEFERRED_BLOCK,DEFERRED_ITEM
            kind=actual[0] or ''
            record=row('void',[kind if kind.split('<',1)[0] in (DEFERRED_BLOCK,DEFERRED_ITEM) else 'net.minecraft.world.item.ItemStack'])
    elif base=='java.lang.Runnable' and name=='run':record=row('void',[])
    elif base=='java.util.Objects' and name=='requireNonNull' and arity in (1,2):
        # Bounded subset: known reference T and optional String message. Supplier
        # messages, boxing and null-only inference require separate contracts.
        target=actual[0]
        if target and target not in ('<null>','void','boolean','byte','short','char','int','long','float','double'):
            if arity==1 or actual[1] in ('java.lang.String','<null>'):
                record=row(target,[target]+(['java.lang.String'] if arity==2 else []),True)
    elif base=='java.util.Optional' and name=='empty':
        record=row('java.util.Optional',[],True,polymorphic_empty_optional=True)
    elif base=='java.lang.System' and name=='arraycopy':
        record=row('void',['java.lang.Object','int','java.lang.Object','int','int'],True,array_abi=1)
    elif base=='java.util.Arrays':
        if name=='asList' and arity==1 and actual[0] and actual[0].endswith('[]'):
            array=actual[0];component=array[:-2]
            if component in ('boolean','byte','short','char','int','long','float','double'):component=array
            record=row('java.util.List<'+component+'>',[array],True,array_abi=1,collection_abi=3,nonnull_arguments=[0])
        elif name in ('copyOf','copyOfRange') and actual and actual[0] and actual[0].endswith('[]'):
            record=row(actual[0],[actual[0]]+['int']*(1 if name=='copyOf' else 2),True,array_abi=1)
        elif name=='sort' and arity==1 and actual[0]=='int[]':record=row('void',['int[]'],True,array_abi=1,nonnull_arguments=[0])
    elif base=='net.neoforged.bus.api.IEventBus':
        if name=='addListener':record=row('void',['java.util.function.Consumer'],event_consumer=True)
        elif name in ('register','unregister'):record=row('void',['java.lang.Object'])
    elif base in ('net.neoforged.fml.ModContainer','net.neoforged.fml.javafmlmod.FMLModContainer') and name=='getModId':
        record=row('java.lang.String',[])
    elif base=='net.neoforged.api.distmarker.Dist' and name=='name':record=row('java.lang.String',[])
    elif base=='net.neoforged.neoforge.common.ModConfigSpec.Builder':
        if name=='comment':
            if not arity or any(t!='java.lang.String' for t in actual):raise ValueError('Config comment supports reviewed nonempty String varargs; array/ambiguous overload requires review')
            record=row(base,['java.lang.String']*arity)
        elif name=='define' and arity==2 and actual[1]=='boolean':
            record=row('net.neoforged.neoforge.common.ModConfigSpec.BooleanValue',['java.lang.String','boolean'])
        elif name=='build':record=row('net.neoforged.neoforge.common.ModConfigSpec',[])
    if record is None and name=='enqueueWork':
        from java_official_event_hierarchy import PARENTS
        pending=[base];seen=set()
        while pending:
            current=pending.pop()
            if current in seen:continue
            seen.add(current)
            if current=='net.neoforged.fml.event.lifecycle.ParallelDispatchEvent':
                record=row('java.util.concurrent.CompletableFuture<java.lang.Void>',['java.lang.Runnable'],deferred_runnable=True,statement_only=True);break
            pending.extend(PARENTS.get(current,[]))
    if record is not None and len(record['parameters'])!=arity:
        raise ValueError('Invalid reviewed API argument count: '+base+'#'+name)
    return record
