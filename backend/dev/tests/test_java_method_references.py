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

class ReferenceTests(unittest.TestCase):
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
    def test_bound_receiver_is_evaluated_once_at_creation(self):
        source='import java.util.function.Supplier; class Cell {int value=4;int read(){return value;}} class A {Cell cell=new Cell();int calls=0;Cell receiver(){calls++;return cell;}Supplier<Integer> ref(){return receiver()::read;}void replace(){cell=new Cell();cell.value=9;}}'
        namespace,result=self.python(source);obj=namespace["A"]();ref=obj.ref();obj.replace()
        actual=str(obj.calls)+","+str(ref.get())
        self.assertEqual(actual,self.java(source,'A a=new A();Supplier<Integer>s=a.ref();a.replace();System.out.print(a.calls+","+s.get());'))
        self.assertEqual(actual,"1,4")
        self.assertIn("neocore.runtime.Functional@9",result["required_runtime_helpers"])
    def test_null_bound_receiver_throws_at_creation(self):
        source='import java.util.function.Supplier;class Cell {int read(){return 2;}}class A {Cell cell;int calls;Cell receiver(){calls++;return cell;}Supplier<Integer> ref(){return receiver()::read;}}'
        namespace,_=self.python(source);obj=namespace["A"]()
        null_type=pkg.load("java_stdlib.lang").NullPointerException
        with self.assertRaises(null_type):obj.ref()
        self.assertEqual(str(obj.calls),self.java(source,'A a=new A();try {a.ref();}catch(NullPointerException e){}System.out.print(a.calls);'))
    def test_constructor_static_and_unbound_references(self):
        source='import java.util.function.Supplier;import java.util.function.Function;class Cell {int n;Cell(){n=3;}Cell(int value){n=value;}int read(){return n;}static int constant(){return 7;}}class A {Supplier<Cell> constructor(){return Cell::new;}Function<Integer,Cell> parameterized(){return Cell::new;}Function<Cell,Integer> unbound(){return Cell::read;}Supplier<Integer> statik(){return Cell::constant;}}'
        namespace,_=self.python(source);obj=namespace["A"]()
        boxed=pkg.load('java_stdlib.function').Functional.box('int',5)
        actual=",".join(str(v) for v in (obj.constructor().get().read(),obj.parameterized().apply(boxed).read(),obj.unbound().apply(namespace["Cell"](8)),obj.statik().get()))
        self.assertEqual(actual,self.java(source,'A a=new A();System.out.print(a.constructor().get().read()+","+a.parameterized().apply(5).read()+","+a.unbound().apply(new Cell(8))+","+a.statik().get());'))
        self.assertEqual(actual,"3,5,8,7")
    def test_super_reference_is_nonvirtual(self):
        source='import java.util.function.Supplier;class A {int read(){return 1;}}class B extends A {int read(){return 2;}Supplier<Integer> parent(){return super::read;}Supplier<Integer> current(){return this::read;}}'
        namespace,_=self.python(source);obj=namespace["B"]()
        actual=str(obj.parent().get())+","+str(obj.current().get())
        self.assertEqual(actual,self.java(source,'B b=new B();System.out.print(b.parent().get()+","+b.current().get());'))
    def test_listener_parameter_type_is_preserved(self):
        source='import net.neoforged.neoforge.event.entity.EntityJoinLevelEvent;class Listener {int calls;void onJoin(EntityJoinLevelEvent event){calls++;}Object reference(){return this::onJoin;}}'
        # Object is not a functional target in Java; use an untyped argument context for the event bus.
        source='import net.neoforged.neoforge.event.entity.EntityJoinLevelEvent;import net.neoforged.bus.api.IEventBus;class Listener {int calls;void onJoin(EntityJoinLevelEvent event){calls++;}void bind(IEventBus bus){bus.addListener(this::onJoin);}}'
        namespace,_=self.python(source);listener=namespace["Listener"]();events=pkg.load("neoforge.event")
        bus=events.IEventBus("test");listener.bind(bus)
        self.assertIs(bus._listeners[0]["event_type"],events.EntityJoinLevelEvent)
        bus.post(events.Event());self.assertEqual(listener.calls,0)
        bus.post(events.EntityJoinLevelEvent(None,None));self.assertEqual(listener.calls,1)
    def test_helper_version_guard(self):
        source='import java.util.function.Supplier;class A {int read(){return 1;}Supplier<Integer> ref(){return this::read;}}'
        _,result=self.python(source);helper=pkg.load("java_stdlib.function").Functional
        previous=helper.ABI_VERSION;scope=api.JavaApiImports(sys).install(api.collect_java_api())
        try:
            helper.ABI_VERSION=0
            with self.assertRaisesRegex(RuntimeError,"Functional ABI 9"):exec(result["python_source"],{})
        finally:helper.ABI_VERSION=previous;scope.close()
    def test_incompatible_target_and_external_signature_are_diagnostics(self):
        sources=['import java.util.function.Supplier;class A {int read(int n){return n;}Supplier<Integer> ref(){return this::read;}}','class A {Object ref(){return this::missing;}}']
        known,_=api_index()
        for source in sources:
            with self.subTest(source=source),self.assertRaises(NeedsLowering):generate(parse_source(source,known_types=known))

if __name__=="__main__":unittest.main()
