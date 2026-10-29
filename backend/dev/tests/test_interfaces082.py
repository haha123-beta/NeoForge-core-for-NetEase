import hashlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from translate_java import translate
from build_source_bundle import collect_sources
from workspace_paths import SCRIPTS_ROOT
from harness import Package
JDK=Path(r'E:\Java\jdk-21.0.10\bin')


class Interfaces082(unittest.TestCase):
    def fixture(self,root,files):
        root.mkdir()
        for name,source in files.items():
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(source,encoding='utf-8')

    def compare(self,files,expected):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';self.fixture(root,files)
            before={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files}
            report=translate(root,Path(tmp)/'out')
            self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(len(files),0,0),report['results'])
            sources=collect_sources(Path(tmp)/'out/source')
            pkg=Package();runtime=pkg.load('core.source_modules').SourceModuleLoader(sources)
            api=pkg.load('core.java_api');scope=api.JavaApiImports(runtime).install(api.collect_java_api())
            try:self.assertEqual(str(runtime.load('use.Run').Run().run()),expected)
            finally:scope.close();runtime.close()
            probe=root/'Probe.java';probe.write_text('public class Probe {public static void main(String[] a){System.out.print(new use.Run().run());}}')
            classes=Path(tmp)/'classes';classes.mkdir()
            result=subprocess.run([str(JDK/'javac.exe'),'-encoding','UTF-8','-d',str(classes)]+[str(root/p) for p in files]+[str(probe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            run=subprocess.run([str(JDK/'java.exe'),'-cp',str(classes),'Probe'],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(run.stdout,expected)
            all_sources=collect_sources(SCRIPTS_ROOT);all_sources.update(sources)
            data={'loader_source':(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8'),'sources':all_sources,'module':'use.Run','class_name':'Run','expected':expected}
            input=Path(tmp)/'probe.json';input.write_text(json.dumps(data),encoding='utf-8')
            py2=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(Path(__file__).with_name('probe_interfaces082_python27.py')),str(input)],capture_output=True,text=True)
            self.assertEqual(py2.returncode,0,py2.stdout+'\n'+py2.stderr)
            self.assertTrue(json.loads(py2.stdout.strip().splitlines()[-1])['python2_executed'])
            self.assertEqual(before,{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files})

    def test_real_superclass_wins_two_defaults_and_virtual_interface_calls(self):
        self.compare({
            'api/Left.java':'package api;public interface Left {int value();default int left(){return value()+1;}default int clash(){return 100;}}',
            'api/Right.java':'package api;public interface Right {default int right(){return 3;}default int clash(){return 200;}}',
            'base/Parent.java':'package base;public class Parent {public int n=7;public Parent(int x){n=x;}public int clash(){return n;}}',
            'use/Child.java':'package use;import api.Left;import api.Right;import base.Parent;public class Child extends Parent implements Left,Right {public Child(){super(7);}public int value(){return 5;}public int total(){return left()+right()+clash()+super.clash();}}',
            'use/Run.java':'package use;import api.Left;import api.Right;public class Run {static int choose(Object o){return 99;}static int choose(Left o){return o.left();}public int run(){Child c=new Child();if(!(c instanceof Left))return 99;if(!(c instanceof Right))return 100;return c.total()+choose(c);}}'
        },'29')

    def test_explicit_class_override_and_abstract_interfaces_merge(self):
        self.compare({
            'api/A.java':'package api;public interface A {int value();default int clash(){return 100;}}',
            'api/B.java':'package api;public interface B {int value();default int clash(){return 200;}}',
            'use/Run.java':'package use;import api.A;import api.B;public class Run implements A,B {public int value(){return 7;}public int clash(){return value()+2;}public int run(){return clash();}}'
        },'9')

    def test_inherited_interface_identity_and_default_body_on_external_receiver(self):
        self.compare({
            'api/A.java':'package api;public interface A {default int value(){return 7;}}',
            'base/Parent.java':'package base;import api.A;public class Parent implements A {}',
            'use/Child.java':'package use;import api.A;import base.Parent;public class Child extends Parent implements A {}',
            'use/Run.java':'package use;import api.A;public class Run {static int choose(Object o){return 1;}static int choose(A o){return o.value();}public int run(){return choose(new Child());}}'
        },'7')

    def test_conflicting_defaults_abstract_contracts_and_qualified_super_are_diagnostics(self):
        cases=[
            ('default int value(){return 1;}','default int value(){return 2;}',''),
            ('default int value(){return 1;}','int value();',''),
            ('int value();','int value();',''),
            ('int value();','long value();','public int value(){return 1;}'),
            ('int value();','','protected int value(){return 1;}'),
            ('default int value(){return 1;}','','public int run(){return A.super.value();}'),
            ('default int value(){return 1;}','default int value(int x){return x;}',''),
        ]
        for left,right,body in cases:
            with self.subTest(left=left,right=right,body=body),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'source';self.fixture(root,{'x/A.java':'package x;public interface A {'+left+'}', 'x/B.java':'package x;public interface B {'+right+'}', 'x/Run.java':'package x;public class Run implements A,B {'+body+'}'})
                report=translate(root,dry_run=True)
                row=next(r for r in report['results'] if r['file']=='x/Run.java')
                self.assertEqual(row['status'],'GENERATED_REVIEW_REQUIRED' if 'value(int' in right or 'A.super' in body else 'MANUAL_REVIEW',row)
                classes=Path(tmp)/'classes';classes.mkdir()
                result=subprocess.run([str(JDK/'javac.exe'),'-d',str(classes)]+[str(p) for p in root.rglob('*.java')],capture_output=True,text=True)
                # Qualified source interface-super and distinct overloads are supported; invalid Java remains rejected.
                if 'A.super' not in body and 'value(int' not in right:self.assertNotEqual(result.returncode,0)
                else:self.assertEqual(result.returncode,0,result.stderr)

    def test_reviewed_native_goal_parent_plus_default_against_original_minecraft_jvm(self):
        from test_java_runtime_inheritance import RuntimeInheritance
        source='interface Value {default int value(){return 7;}} class Run extends Goal implements Value {public boolean canUse(){return value()==7;}public int run(){return super.canContinueToUse()?value():0;}}'
        mapped=source.replace('extends Goal','extends cam').replace('boolean canUse()','boolean b()').replace('super.canContinueToUse()','super.c()')
        expected=RuntimeInheritance().original_goal_java(mapped,'Run r=new Run();System.out.print(r.run());')
        self.assertEqual(expected,'7')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';self.fixture(root,{'Run.java':'import net.minecraft.world.entity.ai.goal.Goal;'+source})
            report=translate(root,Path(tmp)/'out')
            self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(1,0,0),report['results'])
            sources=collect_sources(SCRIPTS_ROOT);sources.update(collect_sources(Path(tmp)/'out/source'))
            data={'loader_source':(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8'),'sources':sources,'module':'Run','class_name':'Run','expected':expected}
            input=Path(tmp)/'probe.json';input.write_text(json.dumps(data),encoding='utf-8')
            result=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(Path(__file__).with_name('probe_interfaces082_python27.py')),str(input)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)


if __name__=='__main__':unittest.main()
