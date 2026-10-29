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

class ConstructorTests(unittest.TestCase):
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
    def test_object_static_type_constructor_and_null_specificity(self):
        source='class Box {int value;Box(int n){value=1;}Box(String n){value=2;}Box(Object n){value=3;}}class A {int run(){Object n="x";return new Box(n).value*100+new Box("x").value*10+new Box(null).value;}}'
        namespace,_=self.python(source);actual=str(namespace["A"]().run())
        self.assertEqual(actual,self.java(source,'System.out.print(new A().run());'));self.assertEqual(actual,"322")
        with self.assertRaisesRegex(TypeError,"constructor signature"):namespace["Box"]("x")
    def test_this_same_arity_initializes_once(self):
        source='class A {static int trace=0;int value=init();int init(){trace=trace*10+1;return 4;}A(){this("x");trace=trace*10+3;}A(int n){value=n;trace=trace*10+4;}A(String n){value=7;trace=trace*10+2;}}'
        namespace,_=self.python(source);obj=namespace["A"]()
        actual=str(obj.value)+","+str(namespace["A"].trace)
        self.assertEqual(actual,self.java(source,'A a=new A();System.out.print(a.value+","+A.trace);'));self.assertEqual(actual,"7,123")
    def test_super_selects_declared_object_then_child_initializes(self):
        source='class A {int value;A(Object n){value=1;}A(String n){value=2;}}class B extends A {int added=3;B(Object n){super(n);}}class Factory {int run(){Object n="x";B b=new B(n);return b.value+b.added;}}'
        namespace,_=self.python(source);actual=str(namespace["Factory"]().run())
        self.assertEqual(actual,self.java(source,'System.out.print(new Factory().run());'));self.assertEqual(actual,"4")
    def test_constructor_reference_keeps_target_signature(self):
        source='import java.util.function.Function;class Box {int value;Box(Object n){value=1;}Box(String n){value=2;}}class A {Function<Object,Box>obj(){return Box::new;}Function<String,Box>str(){return Box::new;}}'
        namespace,result=self.python(source);obj=namespace["A"]()
        actual=str(obj.obj().apply("x").value)+","+str(obj.str().apply("x").value)
        self.assertEqual(actual,self.java(source,'A a=new A();System.out.print(a.obj().apply("x").value+","+a.str().apply("x").value);'));self.assertEqual(actual,"1,2")
        self.assertIn("neocore.runtime.Functional@4",result["required_runtime_helpers"])
    def test_same_arity_delegation_cycle_is_diagnostic(self):
        source='class A {A(int n){this("x");}A(String n){this(1);}}'
        with self.assertRaisesRegex(NeedsLowering,"Cyclic"):generate(parse_source(source))
    def test_ambiguous_null_constructor_is_diagnostic(self):
        source='class X {}class Y {}class A {A(X n){}A(Y n){}}class B {A run(){return new A(null);}}'
        with self.assertRaisesRegex(NeedsLowering,"Ambiguous"):generate(parse_source(source))

if __name__=="__main__":unittest.main()
