# -*- coding: utf-8 -*-
"""Typed items use the same registration barrier as every other registry."""
from __future__ import absolute_import
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
root = os.environ.get('NEOCORE_SCRIPTS_ROOT')
if root is None:
    from workspace_paths import SCRIPTS_ROOT
    root = str(SCRIPTS_ROOT)
sys.path.insert(0, root)
from neoforge import registries as r
from minecraft.item import Item, ItemStack
from minecraft.official_interfaces import ItemLike
from java_stdlib.function import Function, Supplier
from java_stdlib.lang import NullPointerException, ClassCastException


class DeferredItemsTests(unittest.TestCase):
    def setUp(self):
        r.reset_registries()

    def test_factory_type_itemlike_and_registration(self):
        seen = []
        reg = r.DeferredRegister.createItems('sample')
        self.assertIsInstance(reg, r.DeferredRegister.Items)
        holder = reg.register('one', Supplier(lambda: seen.append(1) or Item()))
        self.assertIsInstance(holder, r.DeferredItem)
        self.assertIsInstance(holder, ItemLike)
        self.assertFalse(holder.isBound())
        self.assertRaises(NullPointerException, ItemStack, holder)
        self.assertEqual(seen, [])
        registry = r.BUILT_IN_REGISTRIES.ITEM
        reg.freeze_and_register(registry)
        self.assertEqual(seen, [1])
        self.assertIs(holder.asItem(), registry.get('sample:one'))
        self.assertIs(ItemStack(holder).getItem(), holder.get())
        self.assertEqual(holder.get().getRegistryName(),'sample:one')
        self.assertEqual(holder.get().getDescriptionId(),'item.sample.one')

    def test_function_receives_real_location_at_registration(self):
        seen = []
        reg = r.DeferredRegister.createItems('other')
        h = reg.register('one', Function(lambda key: seen.append(key.toString()) or Item()))
        self.assertEqual(seen, [])
        reg.freeze_and_register()
        self.assertTrue(h.isBound())
        self.assertEqual(seen, ['other:one'])

    def test_wrong_value_never_becomes_bound(self):
        reg = r.DeferredRegister.createItems('sample')
        h = reg.register('bad', lambda: 'not an item')
        self.assertRaises(ClassCastException, reg.freeze_and_register)
        self.assertFalse(h.isBound())

    def test_null_supplier_and_result(self):
        reg = r.DeferredRegister.createItems('sample')
        self.assertRaises(NullPointerException, reg.register, 'bad', None)
        self.assertEqual(reg.size(), 0)
        h = reg.register('empty', lambda: None)
        self.assertRaises(NullPointerException, reg.freeze_and_register)
        self.assertFalse(h.isBound())

    def test_two_namespaces_reuse_one_implementation(self):
        registry = r.BUILT_IN_REGISTRIES.ITEM
        holders = []
        for name in ('sample', 'other'):
            reg = r.DeferredRegister.createItems(name)
            h = reg.register('shared_name', Item)
            reg.freeze_and_register(registry)
            holders.append(h)
        self.assertIsNot(holders[0].get(), holders[1].get())
        self.assertEqual(registry.size(), 2)
        self.assertEqual([h.getId().toString() for h in holders],
                         ['sample:shared_name', 'other:shared_name'])


if __name__ == '__main__':
    unittest.main()
