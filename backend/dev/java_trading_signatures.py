"""Public 1.21.1 payment model signatures; component/codec/UI calls remain blocked."""
PREFIX='net.minecraft.world.item.trading.'
STACK='net.minecraft.world.item.ItemStack'
OFFER=PREFIX+'MerchantOffer'
COST=PREFIX+'ItemCost'
OFFERS=PREFIX+'MerchantOffers'
TYPES=(COST,OFFER,OFFERS)

def resolve(base,name,arity,actuals):
    if base not in TYPES:return None
    if base==COST:
        table={'count':('int',[]),'itemStack':(STACK,[]),'test':('boolean',[STACK]),
               'item':('net.minecraft.core.Holder<net.minecraft.world.item.Item>',[])}
    elif base==OFFERS:
        table={'getRecipeFor':(OFFER,[STACK,STACK,'int']),'copy':(OFFERS,[]),
               'add':('boolean',[OFFER]),'get':(OFFER,['int']),'size':('int',[]),'isEmpty':('boolean',[]),'clear':('void',[])}
    else:
        table={name:('int',[]) for name in ('getUses','getMaxUses','getDemand','getSpecialPriceDiff','getXp')}
        table.update({name:('boolean',[]) for name in ('isOutOfStock','needsRestock','shouldRewardExp')})
        table.update({name:('void',[]) for name in ('resetUses','increaseUses','updateDemand','resetSpecialPriceDiff','setToOutOfStock')})
        table.update({name:('void',['int']) for name in ('addToSpecialPriceDiff','setSpecialPriceDiff')})
        table.update({name:(STACK,[]) for name in ('getBaseCostA','getCostA','getCostB','getResult','assemble')})
        table.update({'getItemCostA':(COST,[]),'getItemCostB':('java.util.Optional<'+COST+'>',[]),
                      'getPriceMultiplier':('float',[]),'copy':(OFFER,[]),
                      'satisfiedBy':('boolean',[STACK,STACK]),'take':('boolean',[STACK,STACK])})
    row=table.get(name)
    if row and len(row[1])==arity:
        for actual,formal in zip(actuals,row[1]):
            if actual==formal or formal=='int' and actual=='java.lang.Integer' or actual=='<null>' and formal not in ('int','float','boolean'):continue
            raise ValueError('Trading argument type is not reviewed: '+str(actual)+' -> '+formal)
        return {'return_type':row[0],'parameters':row[1],'receiver_kind':'game_api'}
    raise ValueError('Trading method requires a reviewed adapter: '+name)

def constructor(identity,actuals):
    if identity==OFFERS:
        if actuals:raise ValueError('MerchantOffers exposes only public zero-argument construction')
        return []
    if identity==COST:
        if len(actuals) not in (1,2) or actuals[0] not in ('<null>','net.minecraft.world.item.Item','net.minecraft.world.item.BlockItem','net.minecraft.world.level.ItemLike') or len(actuals)==2 and actuals[1] not in ('int','java.lang.Integer'):
            raise ValueError('ItemCost requires reviewed ItemLike and optional int count; components are not reviewed')
        return [actuals[0]]+(['int'] if len(actuals)==2 else [])
    if identity==OFFER:
        if len(actuals)!=5 or actuals[0] not in (COST,'<null>') or actuals[1] not in (STACK,'<null>') or any(t not in ('int','java.lang.Integer') for t in actuals[2:4]) or actuals[4] not in ('int','float'):
            raise ValueError('MerchantOffer source construction currently reviews only ItemCost/ItemStack/int/int/float')
        return [COST,STACK,'int','int',actuals[4]]
    return None
