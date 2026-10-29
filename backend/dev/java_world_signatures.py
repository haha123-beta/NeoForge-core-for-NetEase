"""Reviewed compile-time signatures backed by existing world/config/JDK adapters."""
from java_official_type_hierarchy import PARENTS

FEATURE='net.minecraft.world.flag.FeatureElement'
FEATURE_SET='net.minecraft.world.flag.FeatureFlagSet'
# DS-10：UseOnContext 的六个零参 getter（官方 1.21.1 client.jar + client_mappings.txt）。
# BlockPlaceContext extends UseOnContext（PARENTS 已有该关系），复用 _subtype 传播，
# 不重复写父/子两套规则；BlockPlaceContext 只覆盖 getClickedPos，返回类型相同。
USE_ON_CONTEXT='net.minecraft.world.item.context.UseOnContext'
CONTEXT_GETTERS={
    'getLevel':'net.minecraft.world.level.Level',
    'getPlayer':'net.minecraft.world.entity.player.Player',
    'getClickedPos':'net.minecraft.core.BlockPos',
    'getClickedFace':'net.minecraft.core.Direction',
    'getItemInHand':'net.minecraft.world.item.ItemStack',
    'getHand':'net.minecraft.world.InteractionHand'}

def _subtype(identity,target):
    pending=[identity];seen=set()
    while pending:
        current=pending.pop()
        if current==target:return True
        if current in seen:continue
        seen.add(current);pending.extend(PARENTS.get(current,()))
    return False

def resolve(base,name,arity,actual):
    row=None
    if base=='java.lang.System' and name in ('nanoTime','currentTimeMillis'):
        # DS-11（A11）：应用 DS-03 已审候选。JDK 21 只声明 ()J；非零参数在这里显式拒绝，
        # 不落到 type-qualifier 回退生成未检查的动态调用。static_owner 使 System.nanoTime()
        # 以类型限定的静态调用生成，不虚构实例接收者。
        if arity!=0:raise ValueError('System time API requires zero arguments: '+name)
        row=('long',[])
    elif _subtype(base,'net.minecraft.core.Vec3i') and name in ('getX','getY','getZ') and arity==0:
        row=('int',[])
    elif _subtype(base,FEATURE) and name=='isEnabled' and arity==1:
        row=('boolean',[FEATURE_SET])
    elif (base=='net.neoforged.fml.event.config.ModConfigEvent' or base.startswith('net.neoforged.fml.event.config.ModConfigEvent.')) and name=='getConfig' and arity==0:
        row=('net.neoforged.fml.config.ModConfig',[])
    elif base=='net.neoforged.fml.config.ModConfig':
        if name=='getModId' and arity==0:row=('java.lang.String',[])
        elif name=='getSpec' and arity==0:row=('net.neoforged.fml.config.IConfigSpec',[])
    elif base=='net.minecraft.world.item.context.BlockPlaceContext' and name=='canPlace' and arity==0:
        row=('boolean',[])
    elif _subtype(base,USE_ON_CONTEXT) and name in CONTEXT_GETTERS:
        if arity!=0 or actual:raise ValueError('Context getter requires zero arguments: '+name)
        row=(CONTEXT_GETTERS[name],[])
    elif base=='net.minecraft.world.InteractionResult' and name=='sidedSuccess' and arity==1 and actual==['boolean']:
        row=(base,['boolean'])
    if row is None:return None
    result={'return_type':row[0],'parameters':row[1],'receiver_kind':'game_api'}
    if base=='java.lang.System' and name in ('nanoTime','currentTimeMillis'):
        result['static_owner']=base
    return result

def resolve_field(owner,name):
    if _subtype(owner,'net.minecraft.world.level.Level') and name=='isClientSide':
        return {'return_type':'boolean','receiver_kind':'game_api','call_name':'isClientSide'}
    if owner=='net.minecraft.world.InteractionResult' and name in ('SUCCESS','CONSUME','PASS','FAIL'):
        return {'return_type':owner,'receiver_kind':'game_api','static_owner':owner,'final':True}
