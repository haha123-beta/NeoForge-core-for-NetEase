import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from translate_java import translate
from build_source_bundle import collect_sources
from harness import Package
pkg=Package()
loader_type=pkg.load("core.source_modules").SourceModuleLoader
api=pkg.load("core.java_api")
JAVA=Path(r"E:\Java\jdk-21.0.10\bin\java.exe")
JAVAC=JAVA.with_name("javac.exe")

class ProjectInheritanceTests(unittest.TestCase):
    def sources(self,root,broken=False):
        files={
          "base/Root.java":'package base; public class Root {public static int total=1;public int x=2;public int seen;public Root(){seen=read();} public int read(){return x;}}',
          "demo/Mid.java":'package demo;import base.Root;public class Mid extends Root {public int m=3;public Mid(){super();}public int mid(){return super.read()+m;}}',
          "demo/Child.java":'package demo;public class Child extends Mid {public int y=5;public Child(){super();}@Override public int read(){return y;}public int value(){return super.mid()+y;}}'}
        if broken:files["base/Root.java"]=files["base/Root.java"].replace('public int read(){return x;}','public int read(){return x;} public synchronized long bad(long n){return n+1L;}')
        for name,source in files.items():
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(source,encoding="utf-8")
        return files
    def runtime(self,folder):
        runtime=loader_type(collect_sources(folder))
        scope=api.JavaApiImports(runtime).install(api.collect_java_api())
        return runtime,scope
    def test_cross_package_three_levels_preserve_original_paths_and_jdk_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/"original";root.mkdir();files=self.sources(root)
            fingerprints={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in files}
            report=translate(root,Path(directory)/"output")
            self.assertEqual((report["generated_for_review"],report["manual_review"],report["failed"]),(3,0,0))
            child=next(row for row in report["results"] if row["file"]=="demo/Child.java")
            self.assertEqual(child["project_dependencies"],["base/Root.java","demo/Mid.java"])
            runtime,scope=self.runtime(Path(directory)/"output/original")
            try:
                obj=runtime.load("demo.Child").Child()
                actual=str(obj.seen)+","+str(obj.value())
                self.assertEqual(actual,"0,10")
                self.assertIsInstance(obj,runtime.load("base.Root").Root)
                self.assertEqual(runtime.load("demo.Mid").Mid.__dict__["_nc_JavaClassABI"],2)
            finally:scope.close();runtime.close()
            probe=root/"Probe.java";probe.write_text('public class Probe {public static void main(String[] args){demo.Child c=new demo.Child();System.out.print(c.seen+","+c.value());}}')
            build=Path(directory)/"java";build.mkdir()
            compile_result=subprocess.run([str(JAVAC),"-encoding","UTF-8","-d",str(build)]+[str(root/p) for p in files]+[str(probe)],capture_output=True,text=True)
            self.assertEqual(compile_result.returncode,0,compile_result.stderr)
            run=subprocess.run([str(JAVA),"-cp",str(build),"Probe"],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(run.stdout.strip(),actual)
            for p,expected in fingerprints.items():self.assertEqual(hashlib.sha256((root/p).read_bytes()).hexdigest(),expected)
    def test_missing_generated_parent_is_not_a_ready_dependency(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/"original";root.mkdir();self.sources(root,True)
            report=translate(root,Path(directory)/"output")
            child=next(row for row in report["results"] if row["file"]=="demo/Child.java")
            self.assertEqual(next(row for row in report["results"] if row["file"]=="base/Root.java")["status"],"MANUAL_REVIEW")
            self.assertIn("base/Root.java",child["missing_generated_dependencies"])
            self.assertEqual(report["ready_mods"],0)
    def test_old_parent_abi_refused_before_child_definition(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/"original";root.mkdir();self.sources(root)
            translate(root,Path(directory)/"output")
            runtime,scope=self.runtime(Path(directory)/"output/original")
            try:
                parent=runtime.load("base.Root").Root
                delattr(parent,"_nc_JavaClassABI")
                with self.assertRaisesRegex(RuntimeError,"initialization ABI 2"):
                    runtime.load("demo.Child")
            finally:scope.close();runtime.close()
    def test_cross_package_same_arity_parent_constructor(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/"original";root.mkdir()
            (root/"base").mkdir();(root/"demo").mkdir()
            (root/"base/Parent.java").write_text('package base;public class Parent {public int value;public Parent(Object n){value=1;}public Parent(String n){value=2;}}')
            (root/"demo/Child.java").write_text('package demo;import base.Parent;public class Child extends Parent {public Child(){super("x");}}')
            report=translate(root,Path(directory)/"output")
            self.assertEqual((report["generated_for_review"],report["manual_review"],report["failed"]),(2,0,0))
            runtime,scope=self.runtime(Path(directory)/"output/original")
            try:self.assertEqual(runtime.load("demo.Child").Child().value,2)
            finally:scope.close();runtime.close()
            probe=root/"Probe.java";probe.write_text('public class Probe {public static void main(String[] args){System.out.print(new demo.Child().value);}}')
            build=Path(directory)/"java";build.mkdir()
            compiled=subprocess.run([str(JAVAC),"-d",str(build),str(root/"base/Parent.java"),str(root/"demo/Child.java"),str(probe)],capture_output=True,text=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            result=subprocess.run([str(JAVA),"-cp",str(build),"Probe"],capture_output=True,text=True)
            self.assertEqual(result.stdout.strip(),"2")
    def test_cross_package_inherited_close_keeps_runtime_interface(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/"original";root.mkdir();(root/"base").mkdir();(root/"demo").mkdir()
            (root/"base/Parent.java").write_text('package base;public class Parent implements AutoCloseable {public static int trace;public void close(){trace=trace*10+1;}}')
            (root/"demo/Child.java").write_text('package demo;import base.Parent;public class Child extends Parent implements AutoCloseable {public int run(){try(Child own=new Child()){trace=3;}return trace;}}')
            report=translate(root,Path(directory)/"output")
            self.assertEqual((report["generated_for_review"],report["manual_review"],report["failed"]),(2,0,0),report)
            runtime,scope=self.runtime(Path(directory)/"output/original")
            try:actual=str(runtime.load("demo.Child").Child().run())
            finally:scope.close();runtime.close()
            probe=root/"Probe.java";probe.write_text('public class Probe {public static void main(String[] args){System.out.print(new demo.Child().run());}}')
            build=Path(directory)/"java";build.mkdir()
            compiled=subprocess.run([str(JAVAC),"-d",str(build),str(root/"base/Parent.java"),str(root/"demo/Child.java"),str(probe)],capture_output=True,text=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            result=subprocess.run([str(JAVA),"-cp",str(build),"Probe"],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(actual,result.stdout.strip());self.assertEqual(actual,'31')
    def test_cross_file_cycle_remains_actionable(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/"original";root.mkdir()
            (root/"A.java").write_text('class A extends B {}')
            (root/"B.java").write_text('class B extends A {}')
            report=translate(root,Path(directory)/"output")
            self.assertEqual(report["manual_review"],2)
            self.assertTrue(all("Cyclic" in row["reason"] for row in report["results"]))

if __name__=="__main__":unittest.main()
