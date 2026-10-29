"""Reviewed item data methods; gameplay and placement are not stubbed."""
# DS-11（A11）：应用 DS-01 已审候选的 BlockItem.updatePlacementContext 行。
# 官方依据：pinned client.jar + client_mappings.txt，public 实例、非 static/final/abstract、
# descriptor (Lcyd;)Lcyd;、字节码 aload_1; areturn（返回入参本身）。Item 不声明该方法，
# 因此只对 BLOCK_ITEM 开放，不放宽到 Item 或其它物品子类。
ITEM='net.minecraft.world.item.Item';PROPERTIES=ITEM+'.Properties';BLOCK_ITEM='net.minecraft.world.item.BlockItem'
BLOCK_PLACE_CONTEXT='net.minecraft.world.item.context.BlockPlaceContext'
def resolve(base,name,arity,actual):
    row=None
    if base==PROPERTIES:
        row={'fireResistant':(PROPERTIES,[]),'stacksTo':(PROPERTIES,['int']),'durability':(PROPERTIES,['int']),'craftRemainder':(PROPERTIES,[ITEM])}.get(name)
        if row is None:raise ValueError('Item.Properties API requires review: '+name)
    elif base in (ITEM,BLOCK_ITEM,'net.minecraft.world.item.TieredItem','net.minecraft.world.item.DiggerItem','net.minecraft.world.item.SwordItem'):
        row={'asItem':(ITEM,[]),'getDefaultMaxStackSize':('int',[]),'getCraftingRemainingItem':(ITEM,[]),'getDefaultInstance':('net.minecraft.world.item.ItemStack',[]),'getEnchantmentValue':('int',[]),'isValidRepairItem':('boolean',['net.minecraft.world.item.ItemStack']*2)}.get(name)
        if base==BLOCK_ITEM and name=='getBlock':row=('net.minecraft.world.level.block.Block',[])
        if base==BLOCK_ITEM and name=='updatePlacementContext':row=(BLOCK_PLACE_CONTEXT,[BLOCK_PLACE_CONTEXT])
        if base in ('net.minecraft.world.item.TieredItem','net.minecraft.world.item.DiggerItem','net.minecraft.world.item.SwordItem') and name=='getTier':row=('net.minecraft.world.item.Tier',[])
        if base in ('net.minecraft.world.item.DiggerItem','net.minecraft.world.item.SwordItem') and name=='hurtEnemy':row=('boolean',['net.minecraft.world.item.ItemStack','net.minecraft.world.entity.LivingEntity','net.minecraft.world.entity.LivingEntity'])
        if row is None:return None
    if row is None:return None
    result,formal=row
    if arity!=len(formal) or any(a!=f and a!='<null>' for a,f in zip(actual,formal)):raise ValueError('Item data method argument mismatch: '+name)
    return {'return_type':result,'parameters':formal,'receiver_kind':'game_api'}
