# -*- coding: utf-8 -*-
"""Minecraft 1.21.1 data-side merchant contract and three-slot payment container."""
from __future__ import absolute_import
from java_stdlib.lang import UnsupportedOperationException, IndexOutOfBoundsException, NullPointerException
from java_stdlib.primitives import Int32
from minecraft.item import ItemStack
from minecraft.block_entity import Container


class Merchant(object):
    """Interface identity only; concrete merchant behavior must be supplied by original content."""
    def __init__(self):
        if type(self) is Merchant:raise UnsupportedOperationException('Merchant is an interface')
    def setTradingPlayer(self,player):raise UnsupportedOperationException('Merchant.setTradingPlayer requires content implementation')
    def getTradingPlayer(self):raise UnsupportedOperationException('Merchant.getTradingPlayer requires content implementation')
    def getOffers(self):raise UnsupportedOperationException('Merchant.getOffers requires content implementation')
    def overrideOffers(self,offers):raise UnsupportedOperationException('Merchant.overrideOffers requires content implementation')
    def notifyTrade(self,offer):raise UnsupportedOperationException('Merchant.notifyTrade requires content implementation')
    def notifyTradeUpdated(self,stack):raise UnsupportedOperationException('Merchant.notifyTradeUpdated requires content implementation')
    def getVillagerXp(self):raise UnsupportedOperationException('Merchant.getVillagerXp requires content implementation')
    def overrideXp(self,xp):raise UnsupportedOperationException('Merchant.overrideXp requires content implementation')
    def showProgressBar(self):raise UnsupportedOperationException('Merchant.showProgressBar requires content implementation')
    def getNotifyTradeSound(self):raise UnsupportedOperationException('Merchant.getNotifyTradeSound requires content implementation')
    def isClientSide(self):raise UnsupportedOperationException('Merchant.isClientSide requires content implementation')
    def canRestock(self):return False
    def openTradingScreen(self,player,title,level):raise UnsupportedOperationException('Merchant trade screen bridge is not reviewed')


class MerchantContainer(Container):
    def __init__(self,merchant):
        self._merchant=merchant
        self._items=[ItemStack.EMPTY]*3
        self._active_offer=None
        self._selection_hint=0
        self._future_xp=0
    def _index(self,index):
        if index<0 or index>=3:raise IndexOutOfBoundsException('MerchantContainer slot outside 0..2')
        return index
    def getContainerSize(self):return 3
    def isEmpty(self):return all(stack.isEmpty() for stack in self._items)
    def getItem(self,index):return self._items[self._index(index)]
    def removeItem(self,index,amount):
        stack=self.getItem(index)
        if index==2 and not stack.isEmpty():return stack.split(stack.getCount())
        result=stack.split(amount) if amount>0 and not stack.isEmpty() else ItemStack.EMPTY
        if not result.isEmpty() and index in (0,1):self.updateSellItem()
        return result
    def removeItemNoUpdate(self,index):
        if index<0 or index>=3:return ItemStack.EMPTY
        stack=self._items[index];self._items[index]=ItemStack.EMPTY
        return stack
    def setItem(self,index,stack):
        index=self._index(index)
        if stack is None:raise NullPointerException()
        self._items[index]=stack
        maximum=self.getMaxStackSize(stack)
        if stack.getCount()>maximum:stack.setCount(maximum)
        if index in (0,1):self.updateSellItem()
    def stillValid(self,player):return self._merchant.getTradingPlayer() is player
    def setChanged(self):self.updateSellItem()
    def updateSellItem(self):
        self._active_offer=None
        first=self._items[0];second=self._items[1]
        if first.isEmpty():first=second;second=ItemStack.EMPTY
        if first.isEmpty():
            self.setItem(2,ItemStack.EMPTY);self._future_xp=0
            return
        offers=self._merchant.getOffers()
        if not offers.isEmpty():
            offer=offers.getRecipeFor(first,second,self._selection_hint)
            if offer is None or offer.isOutOfStock():
                self._active_offer=offer
                offer=offers.getRecipeFor(second,first,self._selection_hint)
            if offer is not None and not offer.isOutOfStock():
                self._active_offer=offer;self.setItem(2,offer.assemble());self._future_xp=offer.getXp()
            else:self.setItem(2,ItemStack.EMPTY);self._future_xp=0
        self._merchant.notifyTradeUpdated(self._items[2])
    def getActiveOffer(self):return self._active_offer
    def setSelectionHint(self,hint):self._selection_hint=Int32.wrap(hint);self.updateSellItem()
    def clearContent(self):self._items[:]=[ItemStack.EMPTY]*3
    def getFutureXp(self):return self._future_xp


JAVA_MAP={
    'net.minecraft.world.item.trading.Merchant':Merchant,
    'net.minecraft.world.inventory.MerchantContainer':MerchantContainer,
}
