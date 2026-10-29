import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from java_frontend import parse_source,api_index
from java_codegen import generate,NeedsLowering
from harness import Package
pkg=Package();api=pkg.load("core.java_api")
JAVA=Path(r"E:\Java\jdk-21.0.10\bin\java.exe");JAVAC=JAVA.with_name("javac.exe")

class OverloadTests(unittest.TestCase):
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
    def test_declared_object_is_not_dispatched_as_runtime_string(self):
        source='class A {int choose(int n){return 1;}int choose(String n){return 2;}int choose(Object n){return 3;}int test(){Object n="text";return choose(n)*100+choose("text")*10+choose(4);}}'
        namespace,_=self.python(source);actual=str(namespace["A"]().test())
        self.assertEqual(actual,self.java(source,'System.out.print(new A().test());'));self.assertEqual(actual,"321")
        with self.assertRaisesRegex(TypeError,"Compile-time"):namespace["A"]().choose("text")
    def test_null_most_specific_and_unrelated_ambiguity(self):
        source='class A {int f(Object n){return 1;}int f(String n){return 2;}int run(){return f(null);}}'
        namespace,_=self.python(source);self.assertEqual(str(namespace["A"]().run()),self.java(source,'System.out.print(new A().run());'))
        with self.assertRaisesRegex(NeedsLowering,"Ambiguous"):
            generate(parse_source('class X {}class Y {}class A {int f(X x){return 1;}int f(Y y){return 2;}int run(){return f(null);}}'))
    def test_static_and_distinct_arity_methods(self):
        source='class A {static int f(){return 1;}static int f(int n){return n;}static int f(String n){return 7;}int run(){return f()+f(2)+A.f("x");}}'
        namespace,_=self.python(source);self.assertEqual(str(namespace["A"]().run()),self.java(source,'System.out.print(new A().run());'))
        self.assertEqual(namespace["A"].f(),1)
    def test_boxing_phase_follows_strict_reference_phase(self):
        source='class A {int f(Object n){return 1;}int f(Integer n){return 2;}int f(int n){return 3;}int result(){Integer n=null;return f(n)*10+f(4);}int boxed(Integer n){return n.intValue();}int box(){return boxed(5);}}'
        namespace,_=self.python(source);obj=namespace["A"]()
        actual=str(obj.result())+","+str(obj.box())
        self.assertEqual(actual,self.java(source,'A a=new A();System.out.print(a.result()+","+a.box());'));self.assertEqual(actual,"23,5")
    def test_unboxing_null_occurs_before_unused_parameter_body(self):
        source='class A {int f(int n){return 1;}int run(){Integer n=null;return f(n);}}'
        namespace,_=self.python(source)
        with self.assertRaises(pkg.load("java_stdlib.lang").NullPointerException):namespace["A"]().run()
        self.assertEqual(self.java(source,'try {new A().run();}catch(NullPointerException e){System.out.print("null");}'),"null")
    def test_overloaded_bound_reference_uses_target_input_type(self):
        source='import java.util.function.Function;class A {int f(Object n){return 1;}int f(String n){return 2;}Function<Object,Integer>obj(){return this::f;}Function<String,Integer>str(){return this::f;}}'
        namespace,_=self.python(source);obj=namespace["A"]()
        actual=str(obj.obj().apply("x"))+","+str(obj.str().apply("x"))
        self.assertEqual(actual,self.java(source,'A a=new A();System.out.print(a.obj().apply("x")+","+a.str().apply("x"));'));self.assertEqual(actual,"1,2")
    def test_inherited_single_signature_can_dispatch_to_complete_child_family(self):
        source='class A {int f(Object n){return 1;}int run(){Object n="x";return f(n);}}class B extends A {int f(Object n){return 2;}int f(String n){return 3;}int other(){return f("x");}}'
        namespace,_=self.python(source);obj=namespace["B"]()
        actual=str(obj.run())+","+str(obj.other())
        self.assertEqual(actual,self.java(source,'B b=new B();System.out.print(b.run()+","+b.other());'));self.assertEqual(actual,"2,3")
    def test_boxed_local_field_and_return_keep_integer_methods(self):
        source='class A {Integer field=6;Integer value(){return 7;}int run(){Integer local=5;return field.intValue()+value().intValue()+local.intValue();}}'
        namespace,_=self.python(source);actual=str(namespace["A"]().run())
        self.assertEqual(actual,self.java(source,'System.out.print(new A().run());'));self.assertEqual(actual,"18")
    def test_static_expression_qualifier_null_and_side_effects(self):
        source='class A {static int f(Object n){return 1;}}class B extends A {static int f(String n){return 2;}}class Caller {int calls;A receiver(){calls++;return null;}int run(){return receiver().f("x");}}'
        namespace,_=self.python(source);obj=namespace["Caller"]()
        actual=str(obj.run())+","+str(obj.calls)
        self.assertEqual(actual,self.java(source,'Caller c=new Caller();System.out.print(c.run()+","+c.calls);'));self.assertEqual(actual,"1,1")
    def test_unbound_overloaded_reference_excludes_receiver_from_arguments(self):
        source='import java.util.function.Function;class A {int f(){return 1;}int f(String n){return 2;}Function<A,Integer>reference(){return A::f;}}'
        namespace,_=self.python(source);obj=namespace["A"]()
        actual=str(obj.reference().apply(obj))
        self.assertEqual(actual,self.java(source,'A a=new A();System.out.print(a.reference().apply(a));'));self.assertEqual(actual,"1")
    def test_partial_inherited_family_is_merged_without_shadowing(self):
        source='class A {int f(Object n){return 1;}int run(){Object n="x";return f(n);}}class B extends A {int f(String n){return 2;}int other(){return f("x");}}'
        namespace,_=self.python(source);obj=namespace["B"]()
        actual=str(obj.run())+","+str(obj.other())
        self.assertEqual(actual,self.java(source,'B b=new B();System.out.print(b.run()+","+b.other());'))
        self.assertEqual(actual,"1,2")

if __name__=="__main__":unittest.main()
