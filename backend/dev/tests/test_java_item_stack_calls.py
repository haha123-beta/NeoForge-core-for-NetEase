import os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
from java_codegen import NeedsLowering
pkg=helper.pkg
i=pkg.load('minecraft.item');b=pkg.load('minecraft.block_entity');m=pkg.load('minecraft.menu')

class ItemStackCalls(unittest.TestCase):
    def compile(self,body):
        namespace,result=helper.ArrayTests().python('import net.minecraft.world.item.ItemStack;import net.minecraft.world.inventory.AbstractContainerMenu;class Logic {'+body+'}')
        return namespace['Logic'],result
    def stack(self,count=5):
        return i.ItemStack(i.ITEMS.DIAMOND,count)
    def test_empty_copy_returns_shared_empty(self):
        for value in (i.ItemStack(),self.stack(0),self.stack(-1),i.ItemStack(i.ITEMS.AIR,3)):
            self.assertIs(value.copy(),i.ItemStack.EMPTY)
    def test_empty_copy_with_count_does_not_resurrect_item(self):
        for value in (i.ItemStack.EMPTY,self.stack(0),self.stack(-1)):
            self.assertIs(value.copyWithCount(7),i.ItemStack.EMPTY)
            self.assertEqual(value.copyWithCount(7).getCount(),0)
    def test_nonempty_copy_keeps_independent_mutable_metadata(self):
        value=self.stack();value.setCustomData({'nested':[1]})
        value._native_item_components={'nested':[2]}
        copied=value.copy();self.assertIsNot(copied,value);self.assertIs(copied.getItem(),value.getItem())
        copied.getCustomData()['nested'].append(9);copied._native_item_components['nested'].append(9)
        self.assertEqual(value.getCustomData(),{'nested':[1]});self.assertEqual(value._native_item_components,{'nested':[2]})
    def test_negative_split_retains_original_vanilla_behavior(self):
        value=self.stack();part=value.split(-2)
        self.assertEqual(value.getCount(),7);self.assertEqual(part.getCount(),0)
        # The returned copy retains its item even though its count is negative.
        part.setCount(1);self.assertIs(part.getItem(),i.ITEMS.DIAMOND)
    def test_zero_split_is_an_empty_copy_that_retains_item(self):
        value=self.stack();part=value.split(0)
        self.assertEqual(value.getCount(),5);self.assertEqual(part.getCount(),0)
        self.assertIsNot(part,i.ItemStack.EMPTY);part.setCount(2)
        self.assertIs(part.getItem(),i.ITEMS.DIAMOND)
    def test_split_empty_uses_exposed_count_then_shrinks(self):
        value=self.stack(0);part=value.split(-2)
        self.assertIs(part,i.ItemStack.EMPTY);self.assertEqual(value.getCount(),2)
    def test_oversized_split_takes_only_available(self):
        value=self.stack(3);part=value.split(9)
        self.assertEqual(part.getCount(),3);self.assertTrue(value.isEmpty())
    def test_copy_with_zero_count_retains_item_for_later_assignment(self):
        value=self.stack();copied=value.copyWithCount(0)
        self.assertIsNot(copied,i.ItemStack.EMPTY);copied.setCount(4)
        self.assertIs(copied.getItem(),value.getItem());self.assertEqual(value.getCount(),5)
    def test_original_count_chain_keeps_java_int_overflow(self):
        cls,result=self.compile('static int count(ItemStack value){return value.getCount()+1;}')
        self.assertEqual(cls.count(self.stack(2147483647)),-2147483648)
        self.assertIn('neocore.runtime.Int32@',str(result['required_runtime_helpers']))
    def test_menu_generic_return_chain_keeps_stack_type(self):
        cls,_=self.compile('static int count(AbstractContainerMenu menu){return menu.getItems().get(0).getCount()+1;}')
        menu=m.AbstractContainerMenu();container=b.SimpleContainer(1);container.setItem(0,self.stack(4))
        menu.addSlot(m.Slot(container,0));self.assertEqual(cls.count(menu),5)
    def test_original_copy_split_and_mutation_calls(self):
        cls,_=self.compile('static int count(ItemStack value){ItemStack copied=value.copyWithCount(9);copied.shrink(1);copied.grow(2);ItemStack part=copied.split(3);value.setCount(4);return part.getCount()+copied.getCount()+value.getCount();}')
        self.assertEqual(cls.count(self.stack()),14)
    def test_original_nested_copy_chain_and_boolean(self):
        cls,_=self.compile('static int count(ItemStack value){if(value.isEmpty()){return 0;}return value.copy().copyWithCount(2).getCount()+value.getMaxStackSize();}')
        self.assertEqual(cls.count(self.stack()),66);self.assertEqual(cls.count(i.ItemStack.EMPTY),0)
    def test_null_stack_argument_evaluates_before_null_check(self):
        cls,_=self.compile('int trace;ItemStack receiver(){trace=trace*10+1;return null;}int amount(){trace=trace*10+2;return 1;}void run(){receiver().split(amount());}')
        value=cls()
        with self.assertRaises(pkg.load('java_stdlib.lang').NullPointerException):value.run()
        self.assertEqual(value.trace,12)
    def test_instance_stack_method_via_type_is_diagnosed(self):
        with self.assertRaises(NeedsLowering):self.compile('static int run(){return ItemStack.getCount();}')

if __name__=='__main__':unittest.main()
