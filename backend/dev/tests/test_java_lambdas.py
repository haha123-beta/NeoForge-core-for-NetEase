import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from java_frontend import parse_source,api_index
from java_codegen import generate,NeedsLowering
pkg=Package();api=pkg.load("core.java_api")
JAVA=Path(r"E:\Java\jdk-21.0.10\bin\java.exe");JAVAC=JAVA.with_name("javac.exe")

class LambdaTests(unittest.TestCase):
    def python(self,source):
        known,_=api_index();result=generate(parse_source(source,known_types=known))
        scope=api.JavaApiImports(sys).install(api.collect_java_api())
        try:
            namespace={};exec(result["python_source"],namespace);return namespace,result
        finally:scope.close()
    def java(self,source,body):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"Probe.java";path.write_text(source+'\npublic class Probe {public static void main(String[] args){'+body+'}}',encoding="utf-8")
            compiled=subprocess.run([str(JAVAC),"-encoding","UTF-8",str(path)],capture_output=True,text=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            result=subprocess.run([str(JAVA),"-cp",directory,"Probe"],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);return result.stdout.strip()
    def test_reference_capture_vs_lambda_deferred_receiver(self):
        source='import java.util.function.Supplier;class Cell {int value=4;int read(){return value;}}class A {Cell cell=new Cell();int calls;Cell receiver(){calls++;return cell;}Supplier<Integer> bound(){return receiver()::read;}Supplier<Integer> deferred(){return () -> receiver().read();}void replace(){cell=new Cell();cell.value=9;}}'
        namespace,_=self.python(source);obj=namespace["A"]();bound=obj.bound();deferred=obj.deferred();obj.replace()
        actual=str(obj.calls)+","+str(bound.get())+","+str(deferred.get())+","+str(obj.calls)
        expected=self.java(source,'A a=new A();Supplier<Integer>b=a.bound();Supplier<Integer>d=a.deferred();a.replace();System.out.print(a.calls+","+b.get()+","+d.get()+","+a.calls);')
        self.assertEqual(actual,expected);self.assertEqual(actual,"1,4,9,2")
    def test_local_capture_frozen_fields_live_and_block_scope(self):
        source='import java.util.function.Supplier;class A {int value=2;Supplier<Integer> ref(int n){int offset=3;return () -> {int local=n+offset;return value+local;};}}'
        namespace,result=self.python(source);obj=namespace["A"]();ref=obj.ref(4);obj.value=9
        self.assertEqual(str(ref.get()),self.java(source,'A a=new A();Supplier<Integer>s=a.ref(4);a.value=9;System.out.print(s.get());'))
        self.assertEqual(ref.get(),16)
        self.assertIn("neocore.runtime.Functional@2",result["required_runtime_helpers"])
    def test_typed_function_and_predicate_boxed_integer(self):
        source='import java.util.function.Function;import java.util.function.Predicate;class A {Function<Integer,Integer> add(){return n -> {int result=n+2;return result;};}Predicate<Integer> positive(){return n -> n>0;}}'
        namespace,_=self.python(source);obj=namespace["A"]()
        box=pkg.load('java_stdlib.function').Functional.boxInt
        actual=str(obj.add().apply(box(5)))+","+str(obj.positive().test(box(-1))).lower()+","+str(obj.positive().test(box(1))).lower()
        self.assertEqual(actual,self.java(source,'A a=new A();System.out.print(a.add().apply(5)+","+a.positive().test(-1)+","+a.positive().test(1));'))
        lang=pkg.load("java_stdlib.lang")
        with self.assertRaises(lang.NullPointerException):obj.add().apply(None)
        with self.assertRaises(lang.ClassCastException):obj.add().apply("bad")
        with self.assertRaises(lang.ClassCastException):obj.add().apply(5)
    def test_nested_lambda_captures_outer_argument(self):
        source='import java.util.function.Function;import java.util.function.Supplier;class A {Function<Integer,Supplier<Integer>> factory(){return n -> () -> n;}}'
        namespace,_=self.python(source);obj=namespace["A"]();first=obj.factory().apply(4);second=obj.factory().apply(9)
        actual=str(first.get())+","+str(second.get())
        self.assertEqual(actual,self.java(source,'A a=new A();Supplier<Integer>x=a.factory().apply(4);Supplier<Integer>y=a.factory().apply(9);System.out.print(x.get()+","+y.get());'))
        self.assertEqual(actual,"4,9")
    def test_runnable_block_delays_mutation(self):
        source='class A {int calls;Runnable work(){return () -> {calls++;calls++;};}}'
        namespace,_=self.python(source);obj=namespace["A"]();work=obj.work();self.assertEqual(obj.calls,0);work.run()
        self.assertEqual(str(obj.calls),self.java(source,'A a=new A();Runnable r=a.work();r.run();System.out.print(a.calls);'))
    def test_listener_explicit_type_and_event_filter(self):
        source='import net.neoforged.neoforge.event.entity.EntityJoinLevelEvent;import net.neoforged.bus.api.IEventBus;class A {int calls;void bind(IEventBus bus){bus.addListener((EntityJoinLevelEvent event) -> {calls++;});}}'
        namespace,_=self.python(source);obj=namespace["A"]();events=pkg.load("neoforge.event");bus=events.IEventBus("test")
        obj.bind(bus);bus.post(events.Event());self.assertEqual(obj.calls,0)
        bus.post(events.EntityJoinLevelEvent(None,None));self.assertEqual(obj.calls,1)
    def test_mutable_captures_unknown_argument_types_and_uninitialized_locals_rejected(self):
        sources=['import java.util.function.Supplier;class A {Supplier<Integer> ref(){int n=0;n++;return () -> n;}}','import java.util.function.Supplier;class A {Supplier<Integer> ref(int n){n=2;return () -> n;}}','class A {void bind(Object bus){bus.call(event -> event);}}','import java.util.function.Supplier;class A {void f(){Supplier<Integer>s=()->s.get();}}']
        known,_=api_index()
        for source in sources:
            with self.subTest(source=source),self.assertRaises(NeedsLowering):generate(parse_source(source,known_types=known))
    def test_known_method_target_and_parenthesized_conditional(self):
        source='import java.util.function.Function;import java.util.function.Supplier;class A {int apply(Function<Integer,Integer>f){return f.apply(5);}int result(){return apply(n->n+2);}Supplier<Integer>choose(boolean flag){return flag ? (() -> 3) : (() -> 4);}}'
        namespace,_=self.python(source);obj=namespace["A"]()
        actual=str(obj.result())+","+str(obj.choose(False).get())
        self.assertEqual(actual,self.java(source,'A a=new A();System.out.print(a.result()+","+a.choose(false).get());'))
        self.assertEqual(actual,"7,4")
    def test_source_integer_class_is_not_java_lang_integer(self):
        source='import java.util.function.Function;class Integer {}class A {Function<Integer,Integer>identity(){return value->value;}}'
        namespace,_=self.python(source);obj=namespace["Integer"]();self.assertIs(namespace["A"]().identity().apply(obj),obj)
    def test_helper_abi_three_required_for_boxed_return(self):
        source='import java.util.function.Supplier;class A {Supplier<Integer> ref(){return () -> 1;}}'
        _,result=self.python(source);helper=pkg.load("java_stdlib.function").Functional
        previous=helper.ABI_VERSION;scope=api.JavaApiImports(sys).install(api.collect_java_api())
        try:
            helper.ABI_VERSION=2
            with self.assertRaisesRegex(RuntimeError,"Functional ABI 9"):exec(result["python_source"],{})
        finally:helper.ABI_VERSION=previous;scope.close()

if __name__=="__main__":unittest.main()
