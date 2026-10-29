# -*- coding: utf-8 -*-
"""Registration phase contracts; runs directly on Python 2.7 and Python 3."""
from __future__ import absolute_import
import os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
root=os.environ.get('NEOCORE_SCRIPTS_ROOT')
if root is None:
    from workspace_paths import SCRIPTS_ROOT
    root=str(SCRIPTS_ROOT)
sys.path.insert(0,root)
from neoforge import registries as r
from java_stdlib.lang import NullPointerException
from java_stdlib._base import IllegalStateException

class RegistryLifecycle093Tests(unittest.TestCase):
    def setUp(self):r.reset_registries()
    def test_unbound_reads_never_invoke_supplier(self):
        seen=[];reg=r.DeferredRegister.create(r.ResourceKey('minecraft:item'), 'sample')
        h=reg.register('one',lambda:seen.append(1) or object())
        self.assertFalse(h.isBound())
        self.assertRaises(NullPointerException,h.get)
        self.assertRaises(NullPointerException,h.value)
        self.assertFalse(h.isBound());self.assertEqual(seen,[])
        reg.freeze_and_register(r.BUILT_IN_REGISTRIES.ITEM)
        self.assertTrue(h.isBound());self.assertIs(h.get(),h.value())
        self.assertEqual(seen,[1])
    def test_insertion_order_and_previous_entry_dependency(self):
        seen=[];reg=r.DeferredRegister.create(r.ResourceKey('minecraft:item'), 'sample')
        first=reg.register('z',lambda:seen.append('z') or object())
        second=reg.register('a',lambda:seen.append('a') or first.get())
        self.assertEqual(reg.getEntries(),[first,second])
        reg.freeze_and_register(r.BUILT_IN_REGISTRIES.ITEM)
        self.assertEqual(seen,['z','a']);self.assertIs(first.get(),second.get())
    def test_forward_reference_fails_without_recursive_creation(self):
        seen=[];reg=r.DeferredRegister.create(r.ResourceKey('minecraft:item'), 'sample')
        reg.register('first',lambda:later.get())
        later=reg.register('later',lambda:seen.append('later') or object())
        self.assertRaises(NullPointerException,reg.freeze_and_register)
        self.assertEqual(seen,[]);self.assertFalse(later.isBound())
        self.assertRaises(IllegalStateException,reg.register,'late',object)
    def test_failed_supplier_does_not_continue_or_bind(self):
        seen=[];reg=r.DeferredRegister.create(r.ResourceKey('minecraft:item'), 'sample')
        def fail():raise ValueError('supplier failure')
        broken=reg.register('broken',fail)
        after=reg.register('after',lambda:seen.append('after') or object())
        self.assertRaises(ValueError,reg.freeze_and_register)
        self.assertFalse(broken.isBound());self.assertFalse(after.isBound())
        self.assertEqual(seen,[])
    def test_same_or_different_bus_cannot_be_attached_twice(self):
        class Bus(object):
            def __init__(self):self.registries=[]
            def register_registry(self,reg):self.registries.append(reg)
        a,b=Bus(),Bus();reg=r.DeferredRegister.create(r.ResourceKey('minecraft:item'), 'sample')
        reg.register_event_bus(a)
        self.assertRaises(IllegalStateException,reg.register_event_bus,a)
        self.assertRaises(IllegalStateException,reg.register_event_bus,b)
        self.assertEqual(a.registries,[reg]);self.assertEqual(b.registries,[])
    def test_other_holder_can_bind_to_existing_registry_entry(self):
        reg=r.DeferredRegister.create(r.ResourceKey('minecraft:item'), 'other');value=object()
        reg.register('entry',lambda:value)
        mirror=r.DeferredHolder(r.ResourceKey('minecraft:item'),r.ResourceLocation('other','entry'))
        self.assertFalse(mirror.isBound())
        reg.freeze_and_register(r.BUILT_IN_REGISTRIES.ITEM)
        self.assertTrue(mirror.isBound());self.assertIs(mirror.get(),value)
    def test_null_value_rejected_without_binding(self):
        reg=r.DeferredRegister.create(r.ResourceKey('minecraft:item'), 'sample');h=reg.register('empty',lambda:None)
        self.assertRaises(NullPointerException,reg.freeze_and_register)
        self.assertFalse(h.isBound());self.assertRaises(NullPointerException,h.bindValue,None)
    def test_missing_registry_error_is_distinct(self):
        h=r.DeferredHolder(r.ResourceKey('other:absent'),r.ResourceLocation('other','missing'))
        self.assertFalse(h.isBound());self.assertRaises(IllegalStateException,h.get)

if __name__=='__main__':unittest.main()
