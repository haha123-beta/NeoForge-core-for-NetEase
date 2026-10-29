import os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
from java_codegen import NeedsLowering
lang=helper.pkg.load('java_stdlib.lang');menu=helper.pkg.load('minecraft.menu')

class ApiInvocationTests(unittest.TestCase):
    def compare_null(self,source,expected,exception=None):
        namespace,_=helper.ArrayTests().python(source);obj=namespace['A']()
        with self.assertRaises(exception or lang.NullPointerException):obj.run()
        actual=str(obj.trace)
        oracle=helper.ArrayTests().java(source,'A a=new A();try{a.run();}catch(RuntimeException e){}System.out.print(a.trace);')
        self.assertEqual(actual,oracle);self.assertEqual(actual,str(expected))
    def test_list_receiver_then_all_arguments_before_null_check(self):
        self.compare_null('import java.util.List;class A {int trace;List<String> receiver(){trace=trace*10+1;return null;}int index(){trace=trace*10+2;return 0;}String value(){trace=trace*10+3;return "x";}void run(){receiver().set(index(),value());}}',123)
    def test_list_argument_failure_preempts_receiver_null(self):
        self.compare_null('import java.util.List;class A {int trace;List<String> receiver(){trace=trace*10+1;return null;}int index(){trace=trace*10+2;throw new IllegalStateException();}String value(){trace=trace*10+3;return "x";}void run(){receiver().set(index(),value());}}',12,lang.IllegalStateException)
    def test_remove_overload_keyword_does_not_skip_argument(self):
        self.compare_null('import java.util.List;class A {int trace;List<String> receiver(){trace=trace*10+1;return null;}int index(){trace=trace*10+2;return 0;}void run(){receiver().remove(index());}}',12)
    def test_boxing_argument_runs_before_receiver_null_check(self):
        self.compare_null('import java.util.List;class A {int trace;List<Integer> receiver(){trace=trace*10+1;return null;}int value(){trace=trace*10+2;return 7;}void run(){receiver().add(value());}}',12)
    def test_memory_stream_write_argument_runs_before_null_check(self):
        self.compare_null('import java.io.ByteArrayOutputStream;class A {int trace;ByteArrayOutputStream receiver(){trace=trace*10+1;return null;}int value(){trace=trace*10+2;return 7;}void run(){receiver().write(value());}}',12)
    def test_throwable_cause_expression_runs_before_receiver_null_check(self):
        self.compare_null('class A {int trace;Exception receiver(){trace=trace*10+1;return null;}Exception cause(){trace=trace*10+2;return new Exception("cause");}void run(){receiver().initCause(cause());}}',12)
    def test_throwable_argument_failure_preempts_receiver_null(self):
        self.compare_null('class A {int trace;Exception receiver(){trace=trace*10+1;return null;}Exception cause(){trace=trace*10+2;throw new IllegalArgumentException();}void run(){receiver().initCause(cause());}}',12,lang.IllegalArgumentException)
    def test_receiver_is_captured_once_before_argument_changes_owner_field(self):
        source='import java.util.List;class A {int trace;List<String> target;A(List<String> value){target=value;}List<String> receiver(){trace=trace*10+1;return target;}int index(){trace=trace*10+2;target=null;return 0;}String value(){trace=trace*10+3;return "x";}void run(){receiver().set(index(),value());}}'
        namespace,_=helper.ArrayTests().python(source);values=helper.pkg.load('java_stdlib.util').JavaList(['old'])
        obj=namespace['A'](values);obj.run();actual=str(values.get(0))+':'+str(obj.trace)
        oracle=helper.ArrayTests().java(source,'java.util.List<String> values=new java.util.ArrayList<>(java.util.List.of("old"));A a=new A(values);a.run();System.out.print(values.get(0)+":"+a.trace);')
        self.assertEqual(actual,oracle);self.assertEqual(actual,'x:123');self.assertIsNone(obj.target)
    def test_source_method_also_checks_null_after_argument(self):
        self.compare_null('class B {int take(int value){return value;}}class A {int trace;B receiver(){trace=trace*10+1;return null;}int argument(){trace=trace*10+2;return 3;}void run(){receiver().take(argument());}}',12)
    def test_source_method_argument_exception_preempts_null(self):
        self.compare_null('class B {int take(int value){return value;}}class A {int trace;B receiver(){trace=trace*10+1;return null;}int argument(){trace=trace*10+2;throw new IllegalStateException();}void run(){receiver().take(argument());}}',12,lang.IllegalStateException)
    def test_source_static_variable_shadowing_type_is_still_evaluated(self):
        source='class B {static int value(int n){return n+1;}}class A {int trace;B receiver(){trace++;return null;}int run(){B B=receiver();return B.value(trace);}}'
        namespace,_=helper.ArrayTests().python(source);obj=namespace['A']();actual=str(obj.run())+':'+str(obj.trace)
        oracle=helper.ArrayTests().java(source,'A a=new A();System.out.print(a.run()+":"+a.trace);')
        self.assertEqual(actual,oracle);self.assertEqual(actual,'2:1')
    def test_source_variable_like_another_class_uses_its_declared_type(self):
        source='class B {int f(String n){return 1;}}class C {int f(int n){return 2;}}class A {int run(C B){return B.f(3);}}'
        namespace,_=helper.ArrayTests().python(source);actual=namespace['A']().run(namespace['C']())
        oracle=helper.ArrayTests().java(source,'System.out.print(new A().run(new C()));')
        self.assertEqual(str(actual),oracle);self.assertEqual(actual,2)
    def compile_game(self,body):
        namespace,result=helper.ArrayTests().python('import net.minecraft.world.inventory.DataSlot;import net.minecraft.world.inventory.ContainerData;class A {'+body+'}')
        return namespace['A'],result
    def test_static_null_expression_qualifier_is_evaluated_once_and_allowed(self):
        cls,result=self.compile_game('int trace;DataSlot receiver(){trace+=1;return null;}DataSlot run(){return receiver().standalone();}')
        obj=cls();self.assertIsInstance(obj.run(),menu.DataSlot);self.assertEqual(obj.trace,1)
        oracle=helper.ArrayTests().java('class A {int trace;Integer receiver(){trace++;return null;}Integer run(){return receiver().valueOf(1);}}','A a=new A();a.run();System.out.print(a.trace);')
        self.assertEqual(str(obj.trace),oracle)
    def test_static_qualifier_and_arguments_keep_order(self):
        cls,_=self.compile_game('int trace;DataSlot receiver(){trace=trace*10+1;return null;}ContainerData container(){trace=trace*10+2;return null;}int index(){trace=trace*10+3;return 0;}DataSlot run(){return receiver().forContainer(container(),index());}')
        obj=cls();self.assertIsInstance(obj.run(),menu.DataSlot);self.assertEqual(obj.trace,123)
        oracle=helper.ArrayTests().java('class Factory {static Object build(Object x,int n){return new Object();}}class A {int trace;Factory receiver(){trace=trace*10+1;return null;}Object container(){trace=trace*10+2;return null;}int index(){trace=trace*10+3;return 0;}Object run(){return receiver().build(container(),index());}}','A a=new A();a.run();System.out.print(a.trace);')
        self.assertEqual(str(obj.trace),oracle)
    def test_static_dispatch_uses_declared_owner_not_runtime_subtype(self):
        cls,_=self.compile_game('DataSlot run(DataSlot value){return value.standalone();}')
        class Shadow(menu.DataSlot):
            @staticmethod
            def standalone():raise AssertionError('Dynamic subtype static dispatch is wrong')
        self.assertIsInstance(cls().run(Shadow()),menu.DataSlot)
        oracle=helper.ArrayTests().java('class Parent {static int value(){return 1;}}class Child extends Parent {static int value(){return 2;}}','Parent value=new Child();System.out.print(value.value());')
        self.assertEqual(oracle,'1')
    def test_variable_named_like_type_is_an_expression_receiver(self):
        cls,_=self.compile_game('DataSlot run(DataSlot DataSlot){return DataSlot.standalone();}int read(DataSlot DataSlot){return DataSlot.get()+1;}')
        obj=cls();self.assertIsInstance(obj.run(None),menu.DataSlot)
        with self.assertRaises(lang.NullPointerException):obj.read(None)
    def test_static_factory_inline_chain_keeps_return_type(self):
        cls,_=self.compile_game('int run(){return DataSlot.standalone().get()+1;}')
        self.assertEqual(cls().run(),1)
    def test_qualified_parameter_type_gets_reviewed_static_owner_import(self):
        namespace,result=helper.ArrayTests().python('class A {int run(net.minecraft.world.inventory.DataSlot value){return value.standalone().get()+1;}}')
        self.assertEqual(namespace['A']().run(None),1)
        self.assertIn('net.minecraft.world.inventory.DataSlot',result['required_api_types'])
    def test_instance_call_through_class_name_is_diagnosed(self):
        with self.assertRaises(NeedsLowering):self.compile_game('int run(){return DataSlot.get();}')

if __name__=='__main__':unittest.main()
