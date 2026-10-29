import os,sys,subprocess,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from test_container_java_contract import m,b,i,lang

class MenuStateTests(unittest.TestCase):
    def menu(self,size=2):
        container=b.SimpleContainer(size);menu=m.AbstractContainerMenu(m.MenuType(),4)
        for index in range(size):menu.addSlot(m.Slot(container,index))
        return menu,container
    def test_state_rollover_and_received_state_are_distinct(self):
        menu,_=self.menu();self.assertEqual(menu.getStateId(),0)
        stack=i.ItemStack(i.Item(),2);menu.setItem(0,32767,stack)
        self.assertEqual(menu.getStateId(),32767);self.assertEqual(menu.incrementStateId(),0)
        menu.setItem(0,-5,stack);self.assertEqual(menu.getStateId(),-5)
        self.assertEqual(menu.incrementStateId(),32764)
    def test_slot_write_failure_does_not_commit_received_state(self):
        menu,_=self.menu();menu.setItem(0,8,i.ItemStack())
        with self.assertRaises(lang.IllegalArgumentException):menu.setItem(9,12,i.ItemStack())
        self.assertEqual(menu.getStateId(),8)
    def test_initial_contents_preserve_references_and_java_write_order(self):
        menu,container=self.menu();item=i.Item();first=i.ItemStack(item,2);carried=i.ItemStack(item,1)
        menu.initializeContents(14,[first],carried)
        self.assertIs(container.getItem(0),first);self.assertIs(menu.getCarried(),carried)
        second=i.ItemStack(item,3)
        with self.assertRaises(lang.IllegalArgumentException):menu.initializeContents(20,[second,first,first],i.ItemStack())
        self.assertIs(container.getItem(0),second);self.assertEqual(menu.getStateId(),14)
        self.assertIs(menu.getCarried(),carried)
    def test_get_items_new_list_with_original_stack_references(self):
        menu,container=self.menu();stack=i.ItemStack(i.Item(),3);container.setItem(0,stack)
        items=menu.getItems();self.assertIs(items.get(0),stack)
        items.set(0,i.ItemStack());self.assertIs(container.getItem(0),stack)
        stack.grow(1);self.assertEqual(menu.getItems().get(0).getCount(),4)
    def test_java_slot_predicate_is_not_a_permission_guard(self):
        menu,_=self.menu()
        for index in [-1000,-999,-2,-1,0,1]:self.assertTrue(menu.isValidSlotIndex(index))
        for index in [2,3,100]:self.assertFalse(menu.isValidSlotIndex(index))
    def test_unimplemented_recipe_or_factory_never_claim_success(self):
        with self.assertRaises(lang.UnsupportedOperationException):m.MenuType().create(4,None)
        with self.assertRaises(lang.UnsupportedOperationException):m.AbstractContainerMenu().quickMoveStack(None,0)
        with self.assertRaises(lang.UnsupportedOperationException):m.AbstractContainerMenu().stillValid(None)
        menu=m.RecipeBookMenu()
        with self.assertRaises(lang.UnsupportedOperationException):menu.fillCraftSlotsStackedContents(None)
        with self.assertRaises(lang.UnsupportedOperationException):menu.handlePlacement(False,None,None)
    def test_target_bytecode_confirms_state_mask_and_content_write_order(self):
        dev=Path(__file__).resolve().parents[1]
        result=subprocess.run([r"E:\Java\jdk-21.0.10\bin\javap.exe",'-classpath',str(dev/'references/minecraft-1.21.1/client.jar'),'-c','-p','cpu'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        increment=result.stdout.split('public int k();',1)[1].split('private ',1)[0]
        self.assertIn('32767',increment);self.assertIn('iand',increment)
        update=result.stdout.split('public void a(int, int, cuq);',1)[1].split('public ',1)[0]
        self.assertLess(update.index('Method crq.f:'),update.index('Field r:I'))
        init=result.stdout.split('public void a(int, java.util.List<cuq>, cuq);',1)[1].split('public ',1)[0]
        self.assertLess(init.index('Method crq.f:'),init.index('Field n:Lcuq;'))
        self.assertLess(init.index('Field n:Lcuq;'),init.index('Field r:I'))

if __name__=='__main__':unittest.main()
