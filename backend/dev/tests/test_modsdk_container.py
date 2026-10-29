import copy
import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
pkg=Package()
m=pkg.load("minecraft.modsdk_container")
b=pkg.load("minecraft.block_entity")
i=pkg.load("minecraft.item")
c=pkg.load("minecraft.core")
menu=pkg.load("minecraft.menu")

class SDK(object):
    def __init__(self):
        self.slots=[None,None,None]
        self.calls=[]
        self.fail=-1
        self.loaded=True
    def GetEngineCompFactory(self): return self
    def GetLevelId(self): return "level"
    def CreateItem(self, key): return self
    def GetContainerSize(self, pos, dimension): return len(self.slots) if self.loaded else -1
    def GetContainerItem(self, pos, index, dimension, user):
        self.calls.append(("read",pos,index,dimension,user))
        return copy.deepcopy(self.slots[index])
    def SpawnItemToContainer(self, data, index, pos, dimension):
        self.calls.append(("write",index,pos,dimension,copy.deepcopy(data)))
        if index==self.fail:return False
        self.slots[index]=copy.deepcopy(data) or None
        return True

class NativeTests(unittest.TestCase):
    def setUp(self):
        self.item=i.Item(i.Item.Properties())
        self.codec=m.NativeItemCodec().register(self.item,"test:item")
        self.sdk=SDK()
        self.container=m.ModSdkContainer(self.sdk,c.BlockPos(1,2,3),7,self.codec,lambda p,pos,d:p=="allowed")
    def native(self,count=8):return {"itemName":"test:item","auxValue":0,"count":count,"userData":{"a":[1,2]},"enchantData":[[1,2]],"extraId":"id"}
    def test_roundtrip_metadata_and_mutation_flush(self):
        self.sdk.slots[0]=self.native()
        stack=self.container.getItem(0)
        stack.shrink(2)
        self.assertEqual(self.sdk.slots[0]["count"],8)
        self.container.setChanged()
        self.assertEqual(self.sdk.slots[0],dict(self.native(),count=6))
        self.assertIn(("read",(1,2,3),0,7,True),self.sdk.calls)
    def test_split_preserves_native_data_and_copy_independence(self):
        self.sdk.slots[0]=self.native()
        taken=self.container.removeItem(0,3)
        self.assertEqual(self.codec.encode(taken),dict(self.native(),count=3))
        clone=taken.copy();clone._native_item_data["userData"]["a"].append(9)
        self.assertEqual(taken._native_item_data["userData"]["a"],[1,2])
        self.assertEqual(self.sdk.slots[0]["count"],5)
    def test_remove_all_without_64_limit(self):
        self.sdk.slots[0]=self.native(90)
        changes=self.container.change_count
        taken=self.container.removeItemNoUpdate(0)
        self.assertEqual(taken.getCount(),90)
        self.assertIsNone(self.sdk.slots[0])
        self.assertEqual(self.container.change_count,changes)
    def test_external_change_rejected(self):
        self.sdk.slots[0]=self.native()
        self.container.getItem(0).shrink(1)
        self.sdk.slots[0]["count"]=4
        with self.assertRaises(m.ContainerWriteError):self.container.setChanged()
        self.assertEqual(self.sdk.slots[0]["count"],4)
    def test_partial_commit_explicit_and_retry(self):
        self.sdk.slots[:2]=[self.native(),self.native()]
        for index in (0,1):self.container.getItem(index).shrink(1)
        self.sdk.fail=1
        with self.assertRaises(m.ContainerWriteError) as error:self.container.setChanged()
        self.assertEqual(error.exception.applied_slots,[0])
        self.assertEqual([x["count"] for x in self.sdk.slots[:2]],[7,8])
        self.sdk.fail=-1;self.container.setChanged()
        self.assertEqual([x["count"] for x in self.sdk.slots[:2]],[7,7])
    def test_invalid_unknown_components_and_limits(self):
        with self.assertRaises(Exception):self.container.getItem(-1)
        with self.assertRaises(Exception):self.codec.decode({"itemName":"unknown:x","count":1})
        stack=i.ItemStack(self.item,1);stack.setCustomData({"unsupported":1})
        with self.assertRaises(Exception):self.container.setItem(0,stack)
        with self.assertRaises(Exception):self.container.setItem(0,i.ItemStack(self.item,99))
        self.assertFalse([x for x in self.sdk.calls if x[0]=="write"])
    def test_close_and_validity(self):
        self.assertTrue(self.container.stillValid("allowed"))
        self.assertFalse(self.container.stillValid("denied"))
        self.sdk.slots[0]=self.native()
        self.container.getItem(0).shrink(1)
        self.assertEqual(self.container.close(),[0])
        self.assertEqual(self.sdk.slots[0]["count"],8)
        self.assertFalse(self.container.stillValid("allowed"))
        with self.assertRaises(Exception):self.container.getItem(0)
    def test_unload_is_not_empty(self):
        self.sdk.loaded=False
        with self.assertRaises(Exception):self.container.isEmpty()
        self.assertFalse(self.container.stillValid("allowed"))
    def test_clear_partial_failure_keeps_remaining(self):
        self.sdk.slots[:2]=[self.native(),self.native()]
        self.sdk.fail=1
        with self.assertRaises(m.ContainerWriteError) as error:self.container.clearContent()
        self.assertEqual(error.exception.applied_slots,[0])
        self.assertIsNone(self.sdk.slots[0])
        self.assertEqual(self.sdk.slots[1]["count"],8)
    def test_ender_chest_player_isolation(self):
        sdk=self.sdk
        sdk.slots=[None]*27
        sdk.GetEnderChestItem=lambda player,index,user: sdk.GetContainerItem(None,index,0,user)
        sdk.SpawnItemToEnderChest=lambda data,index: sdk.SpawnItemToContainer(data,index,None,0)
        availability={"player":True}
        chest=m.ModSdkEnderChest(sdk,"player",self.codec,lambda key:availability.get(key,False))
        chest.setItem(26,i.ItemStack(self.item,2))
        self.assertEqual(chest.getContainerSize(),27)
        self.assertEqual(chest.getItem(26).getCount(),2)
        self.assertTrue(chest.stillValid("player"))
        self.assertFalse(chest.stillValid("other"))
        availability["player"]=False
        with self.assertRaises(Exception):chest.getItem(0)
    def test_metadata_prevents_merge(self):
        left=self.codec.decode(self.native())
        data=self.native();data["enchantData"]=[[1,3]]
        right=self.codec.decode(data)
        self.assertFalse(left.isSameItemSameComponents(right))
    def test_same_state_write_skipped(self):
        self.sdk.slots[0]=self.native()
        self.container.setItem(0,self.container.getItem(0).copy())
        self.assertFalse([x for x in self.sdk.calls if x[0]=="write"])

class ModelTests(unittest.TestCase):
    def setUp(self):self.item=i.Item(i.Item.Properties())
    def test_remove_components_negative_and_no_update(self):
        container=b.SimpleContainer(2)
        stack=i.ItemStack(self.item,8);stack.setCustomData({"nested":[1]})
        container.setItem(0,stack)
        before=container.change_count
        self.assertTrue(container.removeItem(0,-3).isEmpty())
        self.assertEqual(container.change_count,before)
        taken=container.removeItem(0,3)
        taken.getCustomData()["nested"].append(2)
        self.assertEqual(container.getItem(0).getCustomData(),{"nested":[1]})
        self.assertEqual(container.getItem(0).getCount(),5)
        container.getItem(0).setCount(99)
        before=container.change_count
        self.assertEqual(container.removeItemNoUpdate(0).getCount(),99)
        self.assertEqual(container.change_count,before)
        self.assertTrue(container.isEmpty())
    def test_add_item_merge_remainder_no_input_mutation(self):
        container=b.SimpleContainer(2)
        container.setItem(0,i.ItemStack(self.item,60))
        source=i.ItemStack(self.item,70)
        remainder=container.addItem(source)
        self.assertEqual([s.getCount() for s in container.items],[64,64])
        self.assertEqual(remainder.getCount(),2)
        self.assertEqual(source.getCount(),70)
    def test_menu_move_and_slot_capacity(self):
        container=b.SimpleContainer(3)
        container.setItem(0,i.ItemStack(self.item,60))
        view=menu.AbstractContainerMenu()
        slots=[view.addSlot(menu.Slot(container,index)) for index in range(3)]
        self.assertEqual(slots[2].index,2)
        source=i.ItemStack(self.item,9)
        self.assertTrue(view.moveItemStackTo(source,0,3,True))
        self.assertEqual([s.getCount() for s in container.items],[64,0,5])
        self.assertTrue(source.isEmpty())
        with self.assertRaises(Exception):view.getSlot(-1)
    def test_data_initial_delta_explicit_resync_and_snapshot(self):
        container=b.SimpleContainer(1);view=menu.AbstractContainerMenu()
        view.addSlot(menu.Slot(container,0));data=menu.ContainerData(2)
        view.addDataSlots(data)
        events=[]
        class Sync(object):
            fail=False
            def sendInitialData(self,v,slots,carried,values):events.append(("initial",slots,values))
            def sendSlotChange(self,v,index,stack):
                if self.fail:raise RuntimeError("send failed")
                events.append(("slot",index,stack))
            def sendDataChange(self,v,index,value):events.append(("data",index,value))
            def sendCarriedChange(self,v,stack):events.append(("carried",stack))
        sync=Sync();view.setSynchronizer(sync)
        view.broadcastChanges();self.assertEqual(len(events),1)
        container.setItem(0,i.ItemStack(self.item,3));data.set(1,70000)
        sync.fail=True
        with self.assertRaises(RuntimeError):view.broadcastChanges()
        sync.fail=False;view.broadcastChanges()
        self.assertEqual(events[-1],("data",1,70000))
        # Java commits remote snapshots before calling the sender; failed sends do not auto-retry.
        self.assertFalse([event for event in events if event[0]=="slot"])
        view.sendAllDataToRemote()
        full=events[-1];self.assertEqual(full[0],"initial")
        container.getItem(0).shrink(1)
        self.assertEqual(full[1][0].getCount(),3)
        view.broadcastChanges();self.assertEqual(events[-1][2].getCount(),2)
        view.removed(None);self.assertIsNone(view._synchronizer)
    def test_unsupported_drop_does_not_delete(self):
        access=pkg.load("minecraft.level_access").ILevelAccess()
        level=pkg.load("minecraft.level").Level.wrap(access)
        container=b.SimpleContainer(1);container.setItem(0,i.ItemStack(self.item,3))
        with self.assertRaises(Exception):menu.Containers.dropContents(level,c.BlockPos(0,0,0),container)
        self.assertEqual(container.getItem(0).getCount(),3)
    def test_player_inventory_slots_and_menu_transfer(self):
        inventory=pkg.load("minecraft.entity").Inventory()
        self.assertEqual(inventory.getContainerSize(),41)
        inventory.setItem(36,i.ItemStack(self.item,1))
        self.assertIs(inventory.getItem(36),inventory.armor[0])
        inventory.setItem(40,i.ItemStack(self.item,2))
        self.assertIs(inventory.getItem(-1),inventory.getItem(40))
        view=menu.AbstractContainerMenu()
        view.addSlot(menu.Slot(inventory,0))
        source=i.ItemStack(self.item,4)
        self.assertTrue(view.moveItemStackTo(source,0,1,False))
        self.assertEqual(inventory.getItem(0).getCount(),4)
        self.assertGreater(inventory.change_count,0)
        self.assertEqual(inventory.removeItem(0,2).getCount(),2)
        inventory.clearContent();self.assertTrue(inventory.isEmpty())
    def test_java_constructor(self):
        kind=menu.MenuType()
        view=menu.AbstractContainerMenu(kind,9)
        self.assertEqual(view.containerId,9)
        self.assertIs(view.getType(),kind)

if __name__=="__main__":unittest.main()
