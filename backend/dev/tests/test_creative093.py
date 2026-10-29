# -*- coding: utf-8 -*-
"""Local event semantics only; no native creative menu is claimed."""
from __future__ import absolute_import
import os, sys, unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
root=os.environ.get('NEOCORE_SCRIPTS_ROOT')
if root is None:
    from workspace_paths import SCRIPTS_ROOT
    root=str(SCRIPTS_ROOT)
sys.path.insert(0,root)
from neoforge.creative import CreativeModeTabs, BuildCreativeModeTabContentsEvent
from neoforge.registries import ResourceKey, ResourceLocation
from neoforge.event.server import ServerStartingEvent, ServerLifecycleEvent
from minecraft.item import Item, ItemStack
from java_stdlib.lang import IllegalArgumentException, NullPointerException


class Creative093Tests(unittest.TestCase):
    def test_key_identity_and_both_entry_sets(self):
        key=ResourceKey.create(ResourceKey('minecraft:creative_mode_tab'),ResourceLocation('minecraft','ingredients'))
        self.assertIs(key,CreativeModeTabs.INGREDIENTS)
        self.assertEqual(key.registry(),'minecraft:creative_mode_tab')
        self.assertEqual(key.location().toString(),'minecraft:ingredients')
        event=BuildCreativeModeTabContentsEvent._for_bridge(key)
        self.assertIs(event.getTabKey(),key)
        first,second=ItemStack(Item()),ItemStack(Item())
        event.accept(first);event.accept(second)
        self.assertEqual(event._parent.values,[first,second])
        self.assertEqual(event._search.values,[first,second])

    def test_duplicate_count_and_null_fail(self):
        event=BuildCreativeModeTabContentsEvent._for_bridge(CreativeModeTabs.INGREDIENTS)
        item=Item();event.accept(ItemStack(item))
        self.assertRaises(IllegalArgumentException,event.accept,ItemStack(item))
        self.assertRaises(IllegalArgumentException,event.accept,ItemStack(Item(),2))
        self.assertRaises(NullPointerException,event.accept,None)
        self.assertEqual(len(event._parent.values),1)

    def test_server_event_keeps_exact_server_reference(self):
        server=object();event=ServerStartingEvent(server)
        self.assertIs(event.getServer(),server)
        self.assertIsInstance(event,ServerLifecycleEvent)
        self.assertRaises(TypeError,ServerLifecycleEvent,server)


if __name__=='__main__':unittest.main()
