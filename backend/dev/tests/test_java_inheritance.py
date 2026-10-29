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
pkg=Package()
api=pkg.load("core.java_api")
JAVA=Path(r"E:\Java\jdk-21.0.10\bin\java.exe")
JAVAC=JAVA.with_name("javac.exe")

class InheritanceTests(unittest.TestCase):
    def python(self,source):
        known,_=api_index()
        result=generate(parse_source(source,known_types=known))
        scope=api.JavaApiImports(sys).install(api.collect_java_api())
        try:
            namespace={};exec(result["python_source"],namespace)
            return namespace,result
        finally:scope.close()
    def java(self,source,body):
        self.assertTrue(JAVA.is_file() and JAVAC.is_file(),"JDK 21 required for actual Java comparison")
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"Probe.java"
            path.write_text(source+"\npublic class Probe { public static void main(String[] args) {"+body+"} }",encoding="utf-8")
            compiled=subprocess.run([str(JAVAC),"-encoding","UTF-8",str(path)],capture_output=True,text=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            run=subprocess.run([str(JAVA),"-cp",directory,"Probe"],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            return run.stdout.strip()
    def test_java_initialization_virtual_dispatch_and_source_order(self):
        source="""class A {
 static int trace=1;
 static {trace=trace*10+2;}
 static int later=mark();
 static int mark(){trace=trace*10+3;return 3;}
 int a=7;
 {trace=trace*10+5;}
 int seen;
 A(int n){seen=read();trace=trace*10+4;a=n;}
 int read(){return a;}
}
class B extends A {
 int b=9;
 {trace=trace*10+6;}
 B(int n){super(n);trace=trace*10+7;}
 @Override int read(){return b;}
 int value(){return super.read()+b;}
}"""
        namespace,result=self.python(source);obj=namespace["B"](5)
        actual=",".join(str(v) for v in (obj.seen,namespace["A"].trace,obj.b,obj.value()))
        expected=self.java(source,'B b=new B(5);System.out.print(b.seen+","+A.trace+","+b.b+","+b.value());')
        self.assertEqual(actual,expected)
        self.assertEqual(actual,"0,1235467,9,14")
        self.assertIsInstance(obj,namespace["A"])
        self.assertEqual(result["annotation_metadata"][0]["java_name"],"java.lang.Override")
    def test_forward_superclass_implicit_ctor_and_inherited_fields(self):
        source='class B extends A {int y=x+1; int result(){return read()+y;}} class A {int x=2;{x=x+1;} int read(){return x;}}'
        namespace,_=self.python(source);obj=namespace["B"]()
        actual=str(obj.result())
        self.assertEqual(actual,self.java(source,'System.out.print(new B().result());'))
        self.assertEqual(actual,"7")
    def test_initializer_scope_does_not_capture_constructor_parameter(self):
        source='class A {int n=3;int x=n;{int n=8;x=x+n;} A(int n){x=x+n;}}'
        namespace,_=self.python(source);obj=namespace["A"](2)
        self.assertEqual(str(obj.x),self.java(source,'System.out.print(new A(2).x);'))
        self.assertEqual(obj.x,13)
    def test_constructor_exception_skips_subclass_initializers(self):
        source='class A {static int trace=0;int x=fail();int fail(){trace=1;return 1/0;}} class B extends A {int y=next();int next(){trace=9;return 2;}}'
        namespace,_=self.python(source)
        with self.assertRaises(Exception):namespace["B"]()
        self.assertEqual(str(namespace["A"].trace),self.java(source,'try {new B();} catch(ArithmeticException e) {} System.out.print(A.trace);'))
    def test_super_field_static_owner_and_compound(self):
        source='class A {static int total=2;int x=3;} class B extends A {B(){super.x+=2;this.total=4;}int read(){return super.x+super.total;}}'
        namespace,_=self.python(source);obj=namespace["B"]()
        self.assertEqual(str(obj.read()),self.java(source,'System.out.print(new B().read());'))
        self.assertEqual(namespace["A"].total,4)
        self.assertNotIn("total",obj.__dict__)
    def test_constructor_delegation_initializes_once_and_distinct_arities(self):
        source='class A {static int trace=0;int x=init();int init(){trace=trace*10+1;return 3;}A(){this(4);trace=trace*10+3;}A(int n){x=x+n;trace=trace*10+2;}}'
        namespace,_=self.python(source);obj=namespace["A"]()
        actual=str(obj.x)+","+str(namespace["A"].trace)
        self.assertEqual(actual,self.java(source,'A a=new A();System.out.print(a.x+","+A.trace);'))
        self.assertEqual(actual,"7,123")
        with self.assertRaises(TypeError):namespace["A"](1,2)
    def test_subclass_calls_overloaded_parent_and_chains_own_constructor(self):
        source='class A {int x;A(){x=2;}A(int n){x=n;}}class B extends A {int y=3;B(){this(7);}B(int n){super(n);y=y+n;}}'
        namespace,_=self.python(source);obj=namespace["B"]()
        self.assertEqual(str(obj.x+obj.y),self.java(source,'B b=new B();System.out.print(b.x+b.y);'))
        self.assertEqual(obj.x+obj.y,17)
    def test_unresolved_abis_and_hidden_members_remain_diagnostics(self):
        cases=[
            'class A extends External {}',
            'class A extends B {} class B extends A {}',
            'class A {int x;} class B extends A {int x;}',
            'class A {int x;} class B extends A {int x(){return 1;}}',
            'class A {int x(){return 1;}} class B extends A {int x;}',
            'class A {private int read(){return 1;}} class B extends A {}',
            'class A {A(int n){}} class B extends A {}',
            'class A {A(){this(1);} A(int n){this();}}',
            'class A {A(int n){} A(int other){}}',
            'class object {}'
        ]
        for source in cases:
            with self.subTest(source=source),self.assertRaises(NeedsLowering):generate(parse_source(source))

if __name__=="__main__":unittest.main()
