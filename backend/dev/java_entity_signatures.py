"""Reviewed entity factory/build/registration calls, independent of any mod ID."""
ENTITY='net.minecraft.world.entity.Entity'
TYPE='net.minecraft.world.entity.EntityType'
BUILDER=TYPE+'.Builder'
FACTORY=TYPE+'.EntityFactory'
REGISTER='net.neoforged.neoforge.registries.DeferredRegister'
HOLDER='net.neoforged.neoforge.registries.DeferredHolder'
ITEM='net.minecraft.world.item.Item'
ITEMS=REGISTER+'.Items'
DEFERRED_ITEM='net.neoforged.neoforge.registries.DeferredItem'
BLOCK='net.minecraft.world.level.block.Block'
BLOCKS=REGISTER+'.Blocks'
DEFERRED_BLOCK='net.neoforged.neoforge.registries.DeferredBlock'
BLOCK_ITEM='net.minecraft.world.item.BlockItem'
CORE_HOLDER='net.minecraft.core.Holder'
PARENTS={DEFERRED_BLOCK:[HOLDER,'net.minecraft.world.level.ItemLike'],BLOCKS:[REGISTER],DEFERRED_ITEM:[HOLDER,'net.minecraft.world.level.ItemLike'],ITEMS:[REGISTER]}
BUS='net.neoforged.bus.api.IEventBus'
CATEGORY='net.minecraft.world.entity.MobCategory'
CATEGORIES={'MONSTER','CREATURE','AMBIENT','WATER_CREATURE','WATER_AMBIENT','UNDERGROUND_WATER_CREATURE','AXOLOTLS','MISC'}

def generic_parents(raw,proves):
    """Pinned NeoForge 21.1.233 ancestry; R and T remain distinct."""
    from java_library_signatures import generic_arguments
    base=raw.split('<',1)[0]
    if base not in (DEFERRED_BLOCK,DEFERRED_ITEM,HOLDER) or '<' not in raw:return []
    values=generic_arguments(raw,allow_wildcards=True)
    if any(value in ('boolean','byte','short','char','int','long','float','double','void','<null>') for value in values):return []
    if base in (DEFERRED_BLOCK,DEFERRED_ITEM) and len(values)==1:
        if not proves(values[0],BLOCK if base==DEFERRED_BLOCK else ITEM):return []
        return [HOLDER+'<'+(BLOCK if base==DEFERRED_BLOCK else ITEM)+','+values[0]+'>']
    if base==HOLDER and len(values)==2:
        if not proves(values[1],values[0]):return []
        return [CORE_HOLDER+'<'+values[0]+'>','java.util.function.Supplier<'+values[1]+'>']
    return []

def resolve(raw,base,name,arity,actuals,canonical_generic,generic_arguments,canonical,proves=None):
    if base not in (BUILDER,REGISTER,HOLDER,TYPE,ITEMS,DEFERRED_ITEM,BLOCKS,DEFERRED_BLOCK):return None
    if base==ITEMS and name=='registerSimpleBlockItem':
        # Two Holder<Block> overloads and two String/Supplier overloads. The
        # compiler checks ancestry and wildcard covariance, never raw erasure.
        if arity in (2,3) and actuals and canonical(actuals[0])=='java.lang.String':
            parameters=['java.lang.String','java.util.function.Supplier<? extends '+BLOCK+'>']
            if actuals[1] is None:parameters[1]='java.util.function.Supplier<'+BLOCK+'>'
            if arity==3:parameters.append(ITEM+'.Properties')
            poly=[1]
        elif arity in (1,2):
            parameters=[CORE_HOLDER+'<'+BLOCK+'>']
            if arity==2:parameters.append(ITEM+'.Properties')
            poly=[]
        else:raise ValueError('registerSimpleBlockItem requires a reviewed Holder or String/Supplier overload')
        return {'return_type':DEFERRED_ITEM+'<'+BLOCK_ITEM+'>','parameters':parameters,
                'receiver_kind':'game_api','checked_arguments':True,'poly_function_arguments':poly}
    # A zero-argument get only reads the declared value type. Preserve nested
    # wildcards as type identities; never use this to permit wildcard writes.
    if (base in (HOLDER,DEFERRED_ITEM,DEFERRED_BLOCK) and name=='get' and arity==0) or base in (REGISTER,ITEMS,BLOCKS):
        parameters=[canonical(v.replace('?extends','? extends ').replace('?super','? super ')) for v in generic_arguments(raw,allow_wildcards=True)]
    else:
        parameters=[canonical_generic(v,canonical) for v in generic_arguments(raw)]
    row=None;static=None;call_name=name
    if base==BUILDER:
        entity=parameters[0] if len(parameters)==1 else ENTITY
        result=BUILDER+'<'+entity+'>'
        if name=='of' and arity==2:
            row=(result,[FACTORY+'<'+entity+'>','net.minecraft.world.entity.MobCategory']);static=BUILDER
        elif name in ('sized','eyeHeight') and arity==(2 if name=='sized' else 1):row=(result,['float']*arity)
        elif name=='noSave' and arity==0:row=(result,[])
        elif name in ('clientTrackingRange','updateInterval') and arity==1:row=(result,['int'])
        elif name=='build' and arity==1:row=(TYPE+'<'+entity+'>',['java.lang.String'])
    elif base in (REGISTER,ITEMS,BLOCKS):
        entity_type=ITEM if base==ITEMS else BLOCK if base==BLOCKS else parameters[0] if len(parameters)==1 else 'java.lang.Object'
        if base==REGISTER and name=='createEntities' and arity==1:row=(REGISTER+'<'+TYPE+'>',['java.lang.String']);static=REGISTER
        elif base==REGISTER and name=='createBlocks' and arity==1:row=(BLOCKS,['java.lang.String']);static=REGISTER
        elif base==REGISTER and name=='createItems' and arity==1:row=(ITEMS,['java.lang.String']);static=REGISTER
        elif name=='register' and arity==1:
            if actuals!=[BUS]:raise ValueError('DeferredRegister.register requires an exact IEventBus expression')
            row=('void',[BUS]);call_name='register_event_bus'
        elif name=='register' and arity==2:
            if base in (ITEMS,BLOCKS) and actuals[1] and actuals[1].startswith('java.util.function.Supplier<'):
                values=generic_arguments(actuals[1])
                if len(values)!=1 or not proves or not proves(values[0],entity_type):raise ValueError('Registration supplier type must satisfy its declared bound')
                return {'return_type':(DEFERRED_ITEM if base==ITEMS else DEFERRED_BLOCK)+'<'+values[0]+'>','parameters':['java.lang.String','java.util.function.Supplier<'+values[0]+'>'],'receiver_kind':'game_api','checked_arguments':True,'target_factory_bound':entity_type}
            row=((DEFERRED_ITEM+'<'+ITEM+'>' if base==ITEMS else DEFERRED_BLOCK+'<'+BLOCK+'>' if base==BLOCKS else HOLDER+'<'+entity_type+','+entity_type+'>'),['java.lang.String','java.util.function.Supplier<'+entity_type+'>'])
    elif base in (HOLDER,DEFERRED_ITEM,DEFERRED_BLOCK):
        if name in ('get','value') and arity==0:row=(parameters[-1] if parameters else ITEM if base==DEFERRED_ITEM else BLOCK if base==DEFERRED_BLOCK else 'java.lang.Object',[])
        elif name=='asItem' and base in (DEFERRED_ITEM,DEFERRED_BLOCK) and arity==0:row=(ITEM,[])
        elif name=='getId' and arity==0:row=('net.minecraft.resources.ResourceLocation',[])
        elif name=='isBound' and arity==0:row=('boolean',[])
    elif base==TYPE:
        if name=='getWidth' and arity==0:row=('float',[])
        elif name=='getHeight' and arity==0:row=('float',[])
    if row is None:
        if base in (REGISTER,HOLDER,ITEMS,DEFERRED_ITEM,BLOCKS,DEFERRED_BLOCK):
            raise ValueError('Registration API method requires a reviewed adapter: '+base+'#'+name)
        raise ValueError('Entity registration method requires a reviewed adapter: '+name)
    for actual,formal in zip(actuals,row[1]):
        if actual==formal or formal=='float' and actual in ('int','float') or actual is None and ('EntityFactory<' in formal or formal.startswith('java.util.function.Supplier<')):continue
        if actual=='<null>' and formal not in ('float','int'):continue
        # Generic source type identities are checked by the existing expression/lambda lowering.
        if base not in (ITEMS,BLOCKS) and formal.startswith('java.util.function.Supplier<') and (actual or '').startswith('java.util.function.Supplier<'):continue
        raise ValueError('Entity registration argument differs: '+str(actual)+' -> '+formal)
    result={'return_type':row[0],'parameters':row[1],'receiver_kind':'game_api','call_name':call_name}
    if static:result['static_owner']=static
    return result

def contextual_factory_return(record,target,proves):
    """Instantiate the reviewed <I extends Item/Block> factory against its target.

    This is inference for a method invocation, never covariance for an existing
    DeferredItem/DeferredBlock reference. Supplier result <: I <: declared bound.
    """
    from java_library_signatures import generic_arguments
    bound=record.get('target_factory_bound') if record else None
    actual=record.get('return_type','') if record else ''
    if not bound or target.split('<',1)[0]!=actual.split('<',1)[0]:return None
    supplied=generic_arguments(actual);wanted=generic_arguments(target)
    if len(supplied)!=1 or len(wanted)!=1 or any('?' in x for x in supplied+wanted):return None
    if proves(supplied[0],wanted[0]) and proves(wanted[0],bound):return target
    return None
