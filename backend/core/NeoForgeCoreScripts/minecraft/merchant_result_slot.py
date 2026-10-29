# -*- coding: utf-8 -*-
"""Reviewed 1.21.1 result-slot data path; no engine screen or transaction bridge."""
from __future__ import absolute_import
from java_stdlib.primitives import Int32
from minecraft.menu import Slot
from neoforge.registries import ResourceLocation
from neoforge.mixin_hooks import TRADE_STAT, modify_argument

TRADED_WITH_VILLAGER = ResourceLocation('minecraft', 'traded_with_villager')


class MerchantResultSlot(Slot):
    def __init__(self, player, merchant, slots, index, x, y):
        Slot.__init__(self, slots, index, x, y)
        self.player = player
        self.merchant = merchant
        self.removeCount = 0
        self._trade_slots = slots

    def mayPlace(self, stack):
        return False

    def remove(self, amount):
        if self.hasItem():
            self.removeCount = Int32.add(self.removeCount, min(amount, self.getItem().getCount()))
        return Slot.remove(self, amount)

    def onQuickCraft(self, stack, amount):
        self.removeCount = Int32.add(self.removeCount, amount)
        self.checkTakeAchievements(stack)

    def checkTakeAchievements(self, stack):
        stack.onCraftedBy(self.player.level(), self.player, self.removeCount)
        self.removeCount = 0

    def onTake(self, player, stack):
        self.checkTakeAchievements(stack)
        offer = self._trade_slots.getActiveOffer()
        if offer is not None:
            first = self._trade_slots.getItem(0)
            second = self._trade_slots.getItem(1)
            if offer.take(first, second) or offer.take(second, first):
                self.merchant.notifyTrade(offer)
                # The original player receiver is evaluated before the modifier.
                recipient = player
                stat = modify_argument(TRADE_STAT, self, TRADED_WITH_VILLAGER)
                recipient.awardStat(stat)
                self._trade_slots.setItem(0, first)
                self._trade_slots.setItem(1, second)
            self.merchant.overrideXp(Int32.add(self.merchant.getVillagerXp(), offer.getXp()))


JAVA_MAP = {'net.minecraft.world.inventory.MerchantResultSlot': MerchantResultSlot}
