# -*- coding: utf-8 -*-
"""Actual Python2 registration barrier tests; no native placement is simulated."""
from __future__ import absolute_import
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
root = os.environ.get('NEOCORE_SCRIPTS_ROOT')
if root is None:
    from workspace_paths import SCRIPTS_ROOT
    root = str(SCRIPTS_ROOT)
sys.path.insert(0, root)
from neoforge import registries as r
from minecraft.block import Block
from minecraft.item import Item, BlockItem
from minecraft.official_interfaces import ItemLike
from java_stdlib.function import Supplier, Function
from java_stdlib.lang import NullPointerException, ClassCastException, IllegalStateException, IllegalArgumentException


class DeferredBlocks095(unittest.TestCase):
    def setUp(self):
        r.reset_registries()

    def test_factory_runs_at_barrier_only_and_preserves_identity(self):
        for namespace in ('one', 'two'):
            seen = []
            registry = r.DeferredRegister.createBlocks(namespace)
            self.assertIsInstance(registry, r.DeferredRegister.Blocks)
            holder = registry.register('rock', Supplier(lambda: seen.append(1) or Block()))
            self.assertIsInstance(holder, r.DeferredBlock)
            self.assertIsInstance(holder, ItemLike)
            self.assertEqual(seen, [])
            self.assertFalse(holder.isBound())
            self.assertRaises(NullPointerException, holder.get)
            registry.freeze_and_register(r.BUILT_IN_REGISTRIES.BLOCK)
            self.assertEqual(seen, [1])
            self.assertIs(holder.get(), r.BUILT_IN_REGISTRIES.BLOCK.get(namespace+':rock'))
            self.assertEqual(holder.getId().toString(), namespace+':rock')

    def test_function_location_and_explicit_blockitem_link(self):
        seen = []
        registry = r.DeferredRegister.createBlocks('example')
        holder = registry.register('rock', Function(lambda key: seen.append(key.toString()) or Block()))
        registry.freeze_and_register(r.BUILT_IN_REGISTRIES.BLOCK)
        self.assertEqual(seen, ['example:rock'])
        item = BlockItem(holder.get(), Item.Properties())
        # Native/content item registration is a separate, still unconnected barrier.
        # Exercise delegation with an explicitly established link, not a fake placement.
        holder.get().setItem(item)
        self.assertIs(holder.asItem(), item)

    def test_bad_factory_and_results_never_bind(self):
        registry = r.DeferredRegister.createBlocks('example')
        self.assertRaises(NullPointerException, registry.register, 'null_factory', None)
        self.assertRaises(ClassCastException, registry.register, 'bad_factory', 7)
        self.assertEqual(registry.size(), 0)
        for value, error in ((None, NullPointerException), (Item(), ClassCastException)):
            registry = r.DeferredRegister.createBlocks('example')
            holder = registry.register('bad', lambda: value)
            self.assertRaises(error, registry.freeze_and_register)
            self.assertFalse(holder.isBound())

    def test_duplicate_and_frozen_registration_still_reject(self):
        registry = r.DeferredRegister.createBlocks('example')
        registry.register('rock', Block)
        self.assertRaises(IllegalArgumentException, registry.register, 'rock', Block)
        registry.freeze_and_register()
        self.assertRaises(IllegalStateException, registry.register, 'late', Block)


if __name__ == '__main__':
    unittest.main()
