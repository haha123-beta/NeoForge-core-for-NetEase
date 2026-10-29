import os
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
pkg=Package();b=pkg.load("minecraft.block_entity");i=pkg.load("minecraft.item");m=pkg.load("minecraft.menu");e=pkg.load("minecraft.entity");lang=pkg.load("java_stdlib.lang")

class ContractTests(unittest.TestCase):
    def test_container_capacity_99_and_item_limit(self):
        item=i.Item(i.Item.Properties().stacksTo(99));container=b.SimpleContainer(1)
        self.assertEqual(container.getMaxStackSize(),99)
        self.assertEqual(e.Inventory().getMaxStackSize(),99)
        container.setItem(0,i.ItemStack(item,95))
        self.assertEqual(container.getItem(0).getCount(),95)
        slot=m.Slot(container,0);self.assertEqual(slot.getMaxStackSize(),99)
        self.assertEqual(slot.getMaxStackSize(i.ItemStack.EMPTY),1)
    def test_fixed_non_null_list_clear_resets_default_and_set_returns_old(self):
        default=i.ItemStack.EMPTY;item=i.Item();value=i.ItemStack(item,3)
        items=b.NonNullList.withSize(3,default)
        self.assertFalse(items.isEmpty())
        self.assertIs(items.set(2,value),default)
        items.clear();self.assertIs(items.get(2),default)
        self.assertEqual(items.size(),3)
        with self.assertRaises(lang.UnsupportedOperationException):items.add(value)
        with self.assertRaises(lang.NullPointerException):items.set(0,None)
        with self.assertRaises(lang.NullPointerException):b.NonNullList.withSize(1,None)
    def test_dynamic_non_null_list_and_menu_original_java_fields(self):
        items=b.NonNullList.create();value=i.ItemStack(i.Item(),1)
        items.add(value);self.assertEqual(items.size(),1);self.assertIs(items.remove(0),value)
        items.add(value);items.clear();self.assertTrue(items.isEmpty())
        menu=m.AbstractContainerMenu(m.MenuType(),3);container=b.SimpleContainer(1)
        slot=menu.addSlot(m.Slot(container,0,8,16))
        self.assertIs(menu.slots.get(0),slot);self.assertEqual(menu.slots.size(),1)
        self.assertEqual((slot.x,slot.y),(8,16))
        changed=m.MenuType();menu.menuType=changed;self.assertIs(menu.getType(),changed)
    def test_full_split_keeps_item_before_source_becomes_empty(self):
        item=i.Item();stack=i.ItemStack(item,3);stack.setCustomData({"x":[1]})
        taken=stack.split(3)
        self.assertIs(taken.getItem(),item);self.assertEqual(taken.getCount(),3)
        self.assertTrue(stack.isEmpty());self.assertIs(stack.getItem(),i.ITEMS.AIR)
        self.assertEqual(stack.getMaxStackSize(),1)
    def test_reference_bytecode_container_default_matches_target(self):
        dev=Path(__file__).resolve().parents[1]
        jar=dev/"references/minecraft-1.21.1/client.jar"
        javap=Path(r"E:\Java\jdk-21.0.10\bin\javap.exe")
        result=subprocess.run([str(javap),"-classpath",str(jar),"-c","bqk"],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        start=result.stdout.index("public default int al_();")
        self.assertIn("bipush        99",result.stdout[start:start+140])

if __name__=="__main__":unittest.main()
