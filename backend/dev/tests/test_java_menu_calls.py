import os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as arrays_test
pkg=arrays_test.pkg
m=pkg.load('minecraft.menu');b=pkg.load('minecraft.block_entity');i=pkg.load('minecraft.item')

class JavaMenuCalls(unittest.TestCase):
    def compile(self,body):
        source='import net.minecraft.world.inventory.AbstractContainerMenu;import net.minecraft.world.inventory.DataSlot;public class Logic {'+body+'}'
        namespace,result=arrays_test.ArrayTests().python(source)
        return namespace['Logic'],result
    def test_menu_return_types_feed_original_java_integer_operations(self):
        cls,result=self.compile('public static int advance(AbstractContainerMenu menu){menu.suppressRemoteUpdates();int before=menu.getStateId();menu.resumeRemoteUpdates();return before+menu.incrementStateId();}')
        menu=m.AbstractContainerMenu()
        self.assertEqual(cls.advance(menu),1);self.assertEqual(cls.advance(menu),3)
        self.assertEqual(menu.getStateId(),2)
    def test_data_slot_get_and_set_keep_java_overflow(self):
        cls,result=self.compile('public static boolean change(DataSlot slot){int before=slot.get();slot.set(before+1);return slot.checkAndClearUpdateFlag();}')
        data=m.DataSlot.standalone();data.set(2147483647)
        self.assertTrue(cls.change(data));self.assertEqual(data.get(),-2147483648)
        self.assertIn('neocore.runtime.Int32@',str(result['required_runtime_helpers']))
    def test_generic_menu_item_list_return_supports_original_chain(self):
        cls,_=self.compile('public static int size(AbstractContainerMenu menu){return menu.getItems().size()+1;}')
        menu=m.AbstractContainerMenu();c=b.SimpleContainer(2)
        menu.addSlot(m.Slot(c,0));menu.addSlot(m.Slot(c,1));self.assertEqual(cls.size(menu),3)
    def test_data_slot_factory_retains_typed_chain(self):
        cls,_=self.compile('public static int create(){DataSlot value=DataSlot.standalone();value.set(3);return value.get()+2;}')
        self.assertEqual(cls.create(),5)

    def test_null_receiver_checks_after_argument_side_effects(self):
        cls,_=self.compile('public static int count;private static int argument(){count+=1;return 3;}public static void invoke(DataSlot slot){slot.set(argument());}')
        with self.assertRaises(pkg.load('java_stdlib.lang').NullPointerException):cls.invoke(None)
        oracle=arrays_test.ArrayTests().java('class Eval {static int count;static int argument(){count++;return 3;}static void run(java.util.concurrent.atomic.AtomicInteger receiver){receiver.set(argument());}}','try{Eval.run(null);}catch(NullPointerException e){}System.out.print(Eval.count);')
        self.assertEqual(str(cls.count),oracle);self.assertEqual(cls.count,1)
    def test_argument_exception_wins_over_receiver_null(self):
        cls,_=self.compile('private static int argument(){throw new IllegalStateException();}public static void invoke(DataSlot slot){slot.set(argument());}')
        with self.assertRaises(pkg.load('java_stdlib.lang').IllegalStateException):cls.invoke(None)
        oracle=arrays_test.ArrayTests().java('class Eval {static int argument(){throw new IllegalStateException();}static void run(java.util.concurrent.atomic.AtomicInteger receiver){receiver.set(argument());}}','try{Eval.run(null);}catch(RuntimeException e){System.out.print(e.getClass().getSimpleName());}')
        self.assertEqual(oracle,'IllegalStateException')

if __name__=='__main__':unittest.main()
