import os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
from java_codegen import NeedsLowering
pkg=helper.pkg;i=pkg.load('minecraft.item');lang=pkg.load('java_stdlib.lang');util=pkg.load('java_stdlib.util')

class ItemComparisons(unittest.TestCase):
    def stack(self,count=3):return i.ItemStack(i.ITEMS.DIAMOND,count)
    def compile(self,body):
        namespace,result=helper.ArrayTests().python('import net.minecraft.world.item.ItemStack;import net.minecraft.world.item.Item;import java.util.List;class Logic {'+body+'}')
        return namespace['Logic']
    def test_object_identity_distinguishes_same_content(self):
        a=self.stack();b=self.stack()
        self.assertTrue(a.equals(a));self.assertFalse(a.equals(b));self.assertFalse(a==b)
        self.assertFalse(i.ItemStack().equals(i.ItemStack()))
    def test_hash_is_stable_across_mutation_and_within_java_int(self):
        a=self.stack();before=a.hashCode();values={a:'stored'}
        a.setCount(1);a.setCustomData({'changed':True})
        self.assertEqual(a.hashCode(),before);self.assertEqual(values[a],'stored')
        self.assertTrue(-2147483648<=before<=2147483647)
    def test_java_collections_keep_distinct_stack_objects(self):
        a=self.stack();b=self.stack();values=util.JavaList([a])
        self.assertFalse(values.contains(b));self.assertTrue(values.contains(a))
    def test_matches_includes_count_while_same_components_does_not(self):
        a=self.stack(1);b=self.stack(2)
        self.assertFalse(i.ItemStack.matches(a,b));self.assertTrue(i.ItemStack.isSameItemSameComponents(a,b))
        b.setCount(1);self.assertTrue(i.ItemStack.matches(a,b))
    def test_matches_null_identity_fast_path_and_mixed_null(self):
        self.assertTrue(i.ItemStack.matches(None,None))
        with self.assertRaises(lang.NullPointerException):i.ItemStack.matches(None,self.stack())
        with self.assertRaises(lang.NullPointerException):i.ItemStack.matches(self.stack(),None)
    def test_empty_item_and_component_comparisons_use_exposed_air(self):
        a=self.stack(0);b=i.ItemStack(i.ITEMS.STONE,-2)
        a.setCustomData({'ignored':'empty'});b.setCustomData({'different':'empty'})
        self.assertTrue(i.ItemStack.isSameItem(a,b));self.assertTrue(i.ItemStack.isSameItemSameComponents(a,b));self.assertTrue(i.ItemStack.matches(a,b))
        self.assertTrue(getattr(a,'is')(i.ITEMS.AIR));self.assertFalse(getattr(a,'is')(i.ITEMS.DIAMOND))
    def test_components_remain_part_of_nonempty_comparison(self):
        a=self.stack();b=self.stack();a.setCustomData({'different':1})
        self.assertFalse(i.ItemStack.matches(a,b));self.assertTrue(i.ItemStack.isSameItem(a,b))
    def test_static_list_matches_order_count_and_size(self):
        a=self.stack();b=self.stack();c=i.ItemStack(i.ITEMS.STONE,3)
        self.assertTrue(i.ItemStack.listMatches(util.JavaList([a]),util.JavaList([b])))
        self.assertFalse(i.ItemStack.listMatches([a,c],[c,a]));self.assertFalse(i.ItemStack.listMatches([a],[]))
    def test_original_static_calls_retain_names_and_boolean_types(self):
        cls=self.compile('static boolean run(ItemStack a,ItemStack b){return ItemStack.isSameItem(a,b) && ItemStack.isSameItemSameComponents(a,b) && ItemStack.matches(a,b);}')
        self.assertTrue(cls.run(self.stack(),self.stack()));self.assertFalse(cls.run(self.stack(1),self.stack(2)))
    def test_original_keyword_is_does_not_rename_source_method(self):
        cls=self.compile('static boolean run(ItemStack value,Item item){return value.is(item);}')
        self.assertTrue(cls.run(self.stack(),i.ITEMS.DIAMOND));self.assertTrue(cls.run(self.stack(0),i.ITEMS.AIR))
        with self.assertRaises(lang.NullPointerException):cls.run(None,i.ITEMS.AIR)
    def test_unreviewed_is_overload_and_wrong_static_arity_diagnose(self):
        with self.assertRaises(NeedsLowering):self.compile('static boolean run(ItemStack a){return a.is(a);}')
        with self.assertRaises(NeedsLowering):self.compile('static boolean run(ItemStack a){return a.matches(a);}')
    def test_original_list_matches_static_declaration(self):
        cls=self.compile('static boolean run(List<ItemStack> a,List<ItemStack> b){return ItemStack.listMatches(a,b);}')
        self.assertTrue(cls.run(util.JavaList([self.stack()]),util.JavaList([self.stack()])))
    def test_static_expression_qualifier_is_null_and_still_runs_once(self):
        cls=self.compile('int trace;ItemStack receiver(){trace=trace*10+1;return null;}ItemStack left(){trace=trace*10+2;return null;}ItemStack right(){trace=trace*10+3;return null;}boolean run(){return receiver().matches(left(),right());}')
        obj=cls();self.assertTrue(obj.run());self.assertEqual(obj.trace,123)
    def test_original_equals_and_hash_calls(self):
        cls=self.compile('static boolean equal(ItemStack a,ItemStack b){return a.equals(b);}static int hash(ItemStack a){return a.hashCode()+1;}')
        a=self.stack();self.assertTrue(cls.equal(a,a));self.assertFalse(cls.equal(a,self.stack()))
        expected=((a.hashCode()+1+2147483648)%4294967296)-2147483648
        self.assertEqual(cls.hash(a),expected)
    def test_unresolved_storage_items_do_not_guess_java_identity(self):
        b=pkg.load('minecraft.block_entity');n=pkg.load('minecraft.nbt')
        tag=n.CompoundTag();tag.putList('Items',[{'Slot':0,'id':'missing:a','count':1},{'Slot':1,'id':'missing:b','count':1}])
        slots=b.NonNullList.withSize(2,i.ItemStack.EMPTY);b.ContainerHelper.loadAllItems(tag,slots)
        self.assertFalse(slots.get(0).isSameItemSameComponents(slots.get(1)))
        with self.assertRaises(pkg.load('java_stdlib._base').IllegalStateException):i.ItemStack.isSameItem(slots.get(0),slots.get(1))
    def test_list_matches_uses_virtual_size_and_get_in_vanilla_order(self):
        trace=[]
        class Spy(object):
            def __init__(self,name):self.name=name
            def size(self):trace.append(self.name+'s');return 1
            def get(self,index):trace.append(self.name+'g');return None
            def __len__(self):raise AssertionError('Java uses size()')
            def __iter__(self):raise AssertionError('Java uses indexed get()')
        actual=str(i.ItemStack.listMatches(Spy('L'),Spy('R'))).lower()+':'+''.join(trace)
        source='class S extends java.util.AbstractList<Object>{static String trace="";String name;S(String n){name=n;}public int size(){trace+=name+"s";return 1;}public Object get(int n){trace+=name+"g";return null;}public java.util.Iterator<Object> iterator(){throw new IllegalStateException();}}class A{static boolean run(java.util.List<Object>a,java.util.List<Object>b){if(a.size()!=b.size())return false;for(int n=0;n<a.size();n++){if(a.get(n)!=b.get(n))return false;}return true;}}'
        oracle=helper.ArrayTests().java(source,'System.out.print(A.run(new S("L"),new S("R"))+":"+S.trace);')
        self.assertEqual(actual,oracle);self.assertEqual(actual,'true:LsRsLsLgRgLs')
    def test_list_matches_null_right_after_left_size(self):
        trace=[]
        class Spy(object):
            def size(self):trace.append('size');return 0
        with self.assertRaises(lang.NullPointerException):i.ItemStack.listMatches(Spy(),None)
        self.assertEqual(trace,['size'])
    def test_list_matches_short_circuits_mismatch(self):
        trace=[]
        class Spy(object):
            def __init__(self,value):self.value=value
            def size(self):return 2
            def get(self,index):trace.append(index);return self.value
        self.assertFalse(i.ItemStack.listMatches(Spy(self.stack(1)),Spy(self.stack(2))))
        self.assertEqual(trace,[0,0])

if __name__=='__main__':unittest.main()
