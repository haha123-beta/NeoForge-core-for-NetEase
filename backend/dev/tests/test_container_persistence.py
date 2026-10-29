import json
import os
import sys
import unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
pkg=Package()
b=pkg.load("minecraft.block_entity")
i=pkg.load("minecraft.item")
r=pkg.load("minecraft.registries")
n=pkg.load("minecraft.nbt")
c=pkg.load("minecraft.core")
storage=pkg.load("minecraft.entity_storage")

class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.item=i.Item(i.Item.Properties()).setRegistryName("test:stored")
        self.stack=i.ItemStack(self.item,6)
        self.stack.setCustomData({"kind":"user-defined","nested":[{"value":1}]})
        self.stack._display_name=c.Component.translatable("test.name",c.Component.literal("argument"))
        self.stack._native_item_data={"itemName":"test:stored","count":6,"userData":{"extra":[1,2]}}
        self.stack._native_item_components={"itemName":"test:stored","userData":{"extra":[1,2]}}
        self.source=b.NonNullList.withSize(2,i.ItemStack())
        self.source.set(1,self.stack)
    def save_and_read(self,lookup=None):
        tag=n.CompoundTag();b.ContainerHelper.saveAllItems(tag,self.source,lookup)
        encoded=storage.encode_tag(tag)
        restored_tag=storage.decode_tag(json.loads(json.dumps(encoded)))
        target=b.NonNullList.withSize(2,i.ItemStack())
        b.ContainerHelper.loadAllItems(restored_tag,target,lookup)
        return target.get(1)
    def test_registry_restores_actual_item_and_all_metadata(self):
        lookup=r.HolderLookup();lookup.register("minecraft:item","test:stored",self.item)
        restored=self.save_and_read(lookup)
        self.assertIs(restored.getItem(),self.item)
        self.assertEqual(restored.getCount(),6)
        self.assertEqual(restored.getCustomData(),self.stack.getCustomData())
        self.assertEqual(restored._native_item_data,self.stack._native_item_data)
        self.assertEqual(restored._display_name.kind,"translatable")
        self.assertEqual(restored._display_name.args[0].getString(),"argument")
    def test_unresolved_survives_copy_and_resave(self):
        restored=self.save_and_read()
        self.assertEqual(restored.getRestoredId(),"test:stored")
        clone=restored.copyWithCount(4)
        self.assertEqual(clone.getRestoredId(),"test:stored")
        self.assertEqual(clone.getCount(),4)
        clone.getCustomData()["nested"][0]["value"]=2
        self.assertEqual(restored.getCustomData()["nested"][0]["value"],1)
        slots=b.NonNullList.withSize(1,i.ItemStack());slots.set(0,clone)
        tag=n.CompoundTag();b.ContainerHelper.saveAllItems(tag,slots)
        self.assertEqual(tag.getList("Items")[0]["id"],"test:stored")
    def test_different_unresolved_ids_cannot_merge(self):
        tag=n.CompoundTag();tag.putList("Items",[{"Slot":0,"id":"test:a","count":1},{"Slot":1,"id":"test:b","count":1}])
        slots=b.NonNullList.withSize(2,i.ItemStack());b.ContainerHelper.loadAllItems(tag,slots)
        self.assertFalse(slots.get(0).isSameItemSameComponents(slots.get(1)))
    def test_legacy_plain_mapping_is_readable(self):
        self.assertEqual(storage.decode_tag({"data":[1,2]}),{"data":[1,2]})
    def test_different_names_do_not_merge(self):
        other=self.stack.copy();other._display_name=c.Component.literal("different")
        self.assertFalse(self.stack.isSameItemSameComponents(other))

if __name__=="__main__":unittest.main()
