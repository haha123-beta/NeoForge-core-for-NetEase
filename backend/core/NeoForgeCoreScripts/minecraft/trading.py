# -*- coding: utf-8 -*-
"""Reviewed 1.21.1 offer/payment model; no codecs, trade screen or engine transaction."""
from __future__ import absolute_import
import math
import struct
from java_stdlib.lang import NullPointerException, UnsupportedOperationException
from java_stdlib.primitives import Int32
from java_stdlib.util import JavaOptional, JavaList
from minecraft.item import ItemStack
from minecraft.registries import Holder


def _required(value):
    if value is None:raise NullPointerException()
    return value


def _float32(value):
    try:return struct.unpack('f',struct.pack('f',float(value)))[0]
    except OverflowError:return float('-inf') if value<0 else float('inf')


def _floor_float(value):
    # Mth.floor(float): Java narrowing conversion, then wrapped int subtraction.
    truncated=0 if math.isnan(value) else 2147483647 if value>=2147483647 else -2147483648 if value<=-2147483648 else int(value)
    return Int32.wrap(truncated-1) if value<truncated else truncated


class ItemCost(object):
    """ItemLike constructors and empty component predicate only."""
    def __init__(self,item,count=1):
        item=_required(item).asItem()
        self._holder=Holder.direct(item)
        self._count=Int32.wrap(count)
        self._stack=ItemStack(item,self._count)
    def item(self):return self._holder
    def count(self):return self._count
    def itemStack(self):return self._stack
    def test(self,stack):return _required(stack).getItem() is self._holder.value()
    def components(self):
        raise UnsupportedOperationException('ItemCost component predicate API is not reviewed')
    def withComponents(self,operator):
        raise UnsupportedOperationException('ItemCost component predicate editing is not reviewed')


class MerchantOffer(object):
    def __init__(self,*args):
        if len(args)==5:
            cost,result,max_uses,xp,multiplier=args
            second=JavaOptional.empty();uses=0;demand=0
        elif len(args) in (6,7,8):
            cost,second,result=args[:3]
            if not isinstance(second,JavaOptional):raise TypeError('MerchantOffer requires Optional<ItemCost>')
            if len(args)==6:
                max_uses,xp,multiplier=args[3:];uses=0;demand=0
            else:
                uses,max_uses,xp,multiplier=args[3:7];demand=args[7] if len(args)==8 else 0
        else:raise TypeError('Unreviewed MerchantOffer constructor')
        self._cost_a=cost;self._cost_b=second;self._result=result
        self._uses=Int32.wrap(uses);self._max_uses=Int32.wrap(max_uses)
        self._xp=Int32.wrap(xp);self._multiplier=_float32(multiplier)
        self._demand=Int32.wrap(demand);self._special=0;self._reward_exp=True
    def getBaseCostA(self):return _required(self._cost_a).itemStack()
    def _modified_count(self):
        base=_required(self._cost_a).count()
        surcharge=max(0,_floor_float(_float32(_float32(Int32.wrap(base*self._demand))*self._multiplier)))
        value=Int32.wrap(Int32.wrap(base+surcharge)+self._special)
        maximum=self._cost_a.itemStack().getMaxStackSize()
        return min(max(value,1),maximum)
    def getCostA(self):return self.getBaseCostA().copyWithCount(self._modified_count())
    def getCostB(self):return self._cost_b.get().itemStack() if self._cost_b.isPresent() else ItemStack.EMPTY
    def getItemCostA(self):return self._cost_a
    def getItemCostB(self):return self._cost_b
    def getResult(self):return self._result
    def assemble(self):return _required(self._result).copy()
    def getUses(self):return self._uses
    def resetUses(self):self._uses=0
    def getMaxUses(self):return self._max_uses
    def increaseUses(self):self._uses=Int32.wrap(self._uses+1)
    def getDemand(self):return self._demand
    def updateDemand(self):self._demand=Int32.wrap(Int32.wrap(self._demand+self._uses)-Int32.wrap(self._max_uses-self._uses))
    def addToSpecialPriceDiff(self,value):self._special=Int32.wrap(self._special+value)
    def resetSpecialPriceDiff(self):self._special=0
    def getSpecialPriceDiff(self):return self._special
    def setSpecialPriceDiff(self,value):self._special=Int32.wrap(value)
    def getPriceMultiplier(self):return self._multiplier
    def getXp(self):return self._xp
    def isOutOfStock(self):return self._uses>=self._max_uses
    def setToOutOfStock(self):self._uses=self._max_uses
    def needsRestock(self):return self._uses>0
    def shouldRewardExp(self):return self._reward_exp
    def satisfiedBy(self,first,second):
        if not _required(self._cost_a).test(first) or first.getCount()<self._modified_count():return False
        if self._cost_b.isPresent():
            cost=self._cost_b.get()
            return cost.test(second) and second.getCount()>=cost.count()
        return _required(second).isEmpty()
    def take(self,first,second):
        if not self.satisfiedBy(first,second):return False
        first.shrink(self.getCostA().getCount())
        if not self.getCostB().isEmpty():second.shrink(self.getCostB().getCount())
        return True
    def copy(self):
        clone=MerchantOffer(self._cost_a,self._cost_b,_required(self._result).copy(),self._uses,self._max_uses,self._xp,self._multiplier,self._demand)
        clone._special=self._special;clone._reward_exp=self._reward_exp
        return clone


class MerchantOffers(JavaList):
    def __init__(self):JavaList.__init__(self)
    def getRecipeFor(self,first,second,hint):
        if hint>0 and hint<self.size():
            offer=self.get(hint)
            return offer if _required(offer).satisfiedBy(first,second) else None
        for offer in self:
            if _required(offer).satisfiedBy(first,second):return offer
        return None
    def copy(self):
        clone=MerchantOffers()
        for offer in self:clone.add(_required(offer).copy())
        return clone


JAVA_MAP={
    'net.minecraft.world.item.trading.ItemCost':ItemCost,
    'net.minecraft.world.item.trading.MerchantOffer':MerchantOffer,
    'net.minecraft.world.item.trading.MerchantOffers':MerchantOffers,
}
