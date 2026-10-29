# -*- coding: utf-8 -*-
"""Reviewed tab key and append-to-both-lists event subset, not a native GUI."""
from __future__ import absolute_import
from neoforge.registries import ResourceKey, ResourceLocation
from neoforge.event.base import Event
from minecraft.item import ItemStack
from java_stdlib.lang import NullPointerException, IllegalArgumentException


class CreativeModeTabs(object):
    BUILDING_BLOCKS = ResourceKey.create(ResourceKey('minecraft:creative_mode_tab'),
                                    ResourceLocation('minecraft','building_blocks'))
    INGREDIENTS = ResourceKey.create(ResourceKey('minecraft:creative_mode_tab'),
                                    ResourceLocation('minecraft','ingredients'))

    def __init__(self):
        raise TypeError('CreativeModeTabs is a static API')


class _Entries(object):
    """Internal bridge storage with item+component identity and stable order."""
    def __init__(self):
        self.values = []

    def contains(self, stack):
        return any(ItemStack.isSameItemSameComponents(value,stack) for value in self.values)

    def add(self, stack):
        self.values.append(stack)


class BuildCreativeModeTabContentsEvent(Event):
    def __init__(self, tab, tab_key, parameters, parent_entries, search_entries):
        Event.__init__(self)
        self._tab, self._tab_key, self._parameters = tab, tab_key, parameters
        self._parent, self._search = parent_entries, search_entries

    @classmethod
    def _for_bridge(cls, tab_key):
        # Explicit internal event creation, not an automatic engine event.
        return cls(None,tab_key,None,_Entries(),_Entries())

    def getTabKey(self):
        return self._tab_key

    def accept(self, entry):
        if entry is None:
            raise NullPointerException('Creative entry is null')
        if not isinstance(entry,ItemStack):
            from neoforge.registries import DeferredBlock, DeferredItem
            if isinstance(entry,(DeferredBlock,DeferredItem)):
                entry=ItemStack(entry.asItem())
            else:raise IllegalArgumentException('Reviewed accept requires ItemStack or registered ItemLike holder')
        if entry.getCount() != 1:
            raise IllegalArgumentException('The stack count must be 1')
        # Official Output.accept(stack) selects PARENT_AND_SEARCH_TABS.
        if self._parent.contains(entry):
            raise IllegalArgumentException('Entry already exists in parent tab')
        self._parent.add(entry)
        if self._search.contains(entry):
            raise IllegalArgumentException('Entry already exists in search tab')
        self._search.add(entry)


JAVA_MAP = {'net.minecraft.world.item.CreativeModeTabs':CreativeModeTabs,
            'net.neoforged.neoforge.event.BuildCreativeModeTabContentsEvent':BuildCreativeModeTabContentsEvent}
