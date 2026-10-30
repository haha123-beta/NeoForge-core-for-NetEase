# -*- coding: utf-8 -*-
"""The registry contract is executable on Python 2.7 and Python 3."""
from __future__ import absolute_import
import os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
root=os.environ.get('NEOCORE_SCRIPTS_ROOT')
if root is None:
    from workspace_paths import SCRIPTS_ROOT
    root=str(SCRIPTS_ROOT)
sys.path.insert(0,root)
from neoforge import registries as r
from java_stdlib.lang import UnsupportedOperationException
from java_stdlib.util import ConcurrentModificationException

class RegistryKeys100(unittest.TestCase):
    def setUp(self):r.reset_registries()

    def test_entry_key_is_interned_distinct_from_registry_without_binding(self):
        seen=[];a=r.DeferredRegister.createItems('one');b=r.DeferredRegister.createBlocks('one')
        item=a.register('value',lambda:seen.append(1));block=b.register('value',lambda:seen.append(2))
        self.assertIs(item.getKey(),r.ResourceKey.create(a.registry_key,item.getId()))
        self.assertIsNot(item.getKey(),a.registry_key)
        self.assertIsNot(item.getKey(),block.getKey())
        self.assertEqual(item.getKey().location().toString(),'one:value')
        self.assertEqual(item.getKey().registry(),'minecraft:item')
        self.assertFalse(item.isBound());self.assertEqual(seen,[])
        mirror=r.DeferredHolder(a.registry_key,item.getId())
        self.assertTrue(item.equals(mirror));self.assertEqual(item.hashCode(),mirror.hashCode())
        self.assertFalse(item.equals(block));self.assertFalse(item.equals(object()))
        self.assertEqual(seen,[])

    def test_entries_view_is_stable_live_ordered_and_unmodifiable(self):
        reg=r.DeferredRegister.createItems('view');view=reg.getEntries()
        self.assertIs(view,reg.getEntries());self.assertEqual(view.size(),0)
        first=reg.register('z',lambda:None);it=view.iterator()
        second=reg.register('a',lambda:None)
        self.assertEqual(list(view),[first,second]);self.assertEqual(view.size(),2)
        self.assertTrue(view.contains(first))
        from java_stdlib.util import JavaSet
        self.assertTrue(view.equals(JavaSet([second,first])))
        self.assertRaises(ConcurrentModificationException,it.next)
        for method,args in [('add',(first,)),('addAll',([],)),('clear',()),('remove',(first,)),('removeAll',([],)),('retainAll',([],)),('removeIf',(lambda x:False,))]:
            self.assertRaises(UnsupportedOperationException,getattr(view,method),*args)
        it=view.iterator();self.assertIs(it.next(),first)
        self.assertRaises(UnsupportedOperationException,it.remove)
        seen=[];view.forEach(lambda h:seen.append(h.getId().toString()))
        self.assertEqual(seen,['view:z','view:a'])
        self.assertFalse(first.isBound());self.assertFalse(second.isBound())

if __name__=='__main__':unittest.main()
