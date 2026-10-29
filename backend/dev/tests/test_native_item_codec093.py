# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
root=os.environ.get('NEOCORE_SCRIPTS_ROOT')
if root is None:
    from workspace_paths import SCRIPTS_ROOT
    root=str(SCRIPTS_ROOT)
sys.path.insert(0,root)
from minecraft.item import Item,ItemStack
from minecraft.modsdk_container import NativeItemCodec
from minecraft.modsdk_entity_access import EngineBridgeError


class NativeItemCodec093Tests(unittest.TestCase):
    def test_generated_java_int_count_roundtrips_on_actual_python2(self):
        item=Item();codec=NativeItemCodec().register(item,'sample:one')
        data=codec.encode(ItemStack(item,8))
        self.assertIs(type(data['count']),int)
        decoded=codec.decode(data)
        self.assertIs(decoded.getItem(),item)
        self.assertEqual(decoded.getCount(),8)
        try:count=long(8)
        except NameError:count=8
        self.assertEqual(codec.decode({'itemName':'sample:one','count':count}).getCount(),8)

    def test_malformed_and_out_of_java_int_counts_fail(self):
        codec=NativeItemCodec().register(Item(),'sample:one')
        for value in (True,-1,2147483648,1.5,'8'):
            self.assertRaises(EngineBridgeError,codec.decode,{'itemName':'sample:one','count':value})


if __name__=='__main__':unittest.main()
