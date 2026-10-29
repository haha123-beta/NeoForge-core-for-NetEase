# -*- coding: utf-8 -*-
"""Minecraft 1.21.1 TieredItem data behavior, verified against original bytecode."""
from __future__ import absolute_import
from minecraft.item import Item
from minecraft.official_interfaces import _invoke
from java_stdlib.lang import NullPointerException


class TieredItem(Item):
    def __init__(self, tier, properties):
        if tier is None or properties is None:raise NullPointerException()
        Item.__init__(self, properties.durability(_invoke(tier, 'getUses')))
        self._tier = tier

    def getTier(self):return self._tier

    def getEnchantmentValue(self):return _invoke(self._tier, 'getEnchantmentValue')

    def isValidRepairItem(self, stack, material):
        ingredient = _invoke(self._tier, 'getRepairIngredient')
        if ingredient is None:raise NullPointerException()
        return ingredient.test(material) or Item.isValidRepairItem(self, stack, material)


JAVA_MAP = {'net.minecraft.world.item.TieredItem': TieredItem}


class DiggerItem(TieredItem):
    def __init__(self, tier, tag, properties):
        if tier is None or properties is None:raise NullPointerException()
        properties._tool_component = _invoke(tier, 'createToolProperties', (tag,),
            ('net.minecraft.tags.TagKey<net.minecraft.world.level.block.Block>',))
        TieredItem.__init__(self, tier, properties)

    def hurtEnemy(self, stack, target, attacker):return True


JAVA_MAP['net.minecraft.world.item.DiggerItem'] = DiggerItem


class SwordItem(TieredItem):
    def __init__(self,tier,properties):
        if properties is None:raise NullPointerException()
        from minecraft.tool_rules import Tool,Rule
        from minecraft.block import BLOCKS
        from minecraft.block_extra import BlockTags
        from java_stdlib.util import ImmutableList
        properties._tool_component=Tool(ImmutableList([
            Rule._mines_blocks([BLOCKS.COBWEB],15.0),
            Rule.overrideSpeed(BlockTags.SWORD_EFFICIENT,1.5)],reject_null=True),1.0,2)
        TieredItem.__init__(self,tier,properties)

    def hurtEnemy(self,stack,target,attacker):return True


JAVA_MAP['net.minecraft.world.item.SwordItem']=SwordItem
