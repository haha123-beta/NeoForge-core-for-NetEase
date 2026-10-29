import os,sys,tempfile,json,unittest,subprocess
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from translate_java import translate
from build_source_bundle import core_bundle,collect_sources
from workspace_paths import SCRIPTS_ROOT
from java_official_probe import JDK

class SourceGenerics087(unittest.TestCase):
    def execute(self,files,expected):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'input';source.mkdir()
            for name,body in files.items():
                path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body)
            probe=root/'Probe.java';probe.write_text('public class Probe {public static void main(String[] a){System.out.print(new Run().run());}}');classes=root/'classes';classes.mkdir()
            result=subprocess.run([str(JDK/'javac.exe'),'-d',str(classes)]+[str(source/name) for name in files]+[str(probe)],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(JDK/'java.exe'),'-cp',str(classes),'Probe'],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout,expected)
            report=translate(source,root/'out');self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(len(files),0,0),report)
            sources=core_bundle()['sources'];sources.update(collect_sources(root/'out/input'))
            payload={'loader_source':(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8'),'sources':sources,'module':'Run','class_name':'Run','expected':expected}
            path=root/'probe.json';path.write_text(json.dumps(payload),encoding='utf-8')
            result=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(Path(__file__).with_name('probe_interfaces082_python27.py')),str(path)],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)

    def test_three_level_type_parameters_field_return_and_constructor(self):
        self.execute({'a/Box.java':'package a;public class Box<T> {protected T value;public Box(T v){value=v;}public T get(){return value;}}','b/Mid.java':'package b;public class Mid<U> extends a.Box<U> {public Mid(U v){super(v);}public U read(){return get();}}','Run.java':'public class Run extends b.Mid<String> {public Run(){super("abc");}public int run(){return read().length()+value.length();}}'},'6')

    def test_generic_interface_default_and_abstract_specialization(self):
        self.execute({'a/Value.java':'package a;public interface Value<T> {T get();default T echo(T x){return x;}default T read(){return get();}}','a/Child.java':'package a;public interface Child<U> extends Value<U> {}','Run.java':'public class Run implements a.Child<String> {public String get(){return "yes";}public int run(){return read().length()+echo("word").length();}}'},'7')

    def test_nested_generic_inherited_return(self):
        self.execute({'Box.java':'public class Box<T> {private T value;public Box(T v){value=v;}public T get(){return value;}}','Run.java':'import java.util.List;import java.util.ArrayList;public class Run extends Box<List<String>> {public Run(){super(new ArrayList<String>());}public int run(){get().add("a");return get().size();}}'},'1')

    def test_distinct_erasure_overloads_and_erased_runtime_dispatch(self):
        self.execute({'Box.java':'public class Box<T> {public int tag;public Box(T v){tag=3;}public Box(int v){tag=v;}public T echo(T v){return v;}public int echo(int v){return v+1;}}','Run.java':'public class Run extends Box<String> {public Run(){super("x");}public int run(){return tag+echo(5)+echo("ab").length();}}'},'11')

    def test_concrete_generic_receiver_without_inheritance(self):
        self.execute({'Box.java':'public class Box<T> {private T value;public Box(T v){value=v;}public T get(){return value;}}','Run.java':'public class Run {public int run(){Box<String> b=new Box<String>("hello");return b.get().length();}}'},'5')

    def test_source_class_upper_bound_is_proven_and_substituted(self):
        self.execute({'Root.java':'public class Root {public int n(){return 7;}}','Child.java':'public class Child extends Root {}','Box.java':'public class Box<T extends Root> {private T value;public Box(T v){value=v;}public T get(){return value;}}','Run.java':'public class Run extends Box<Child> {public Run(){super(new Child());}public int run(){return get().n();}}'},'7')

    def test_conflicting_specializations_and_changing_argument_cycle_reject(self):
        fixtures=[{'I.java':'public interface I<T> {}','J.java':'public interface J extends I<String> {}','Run.java':'public class Run implements J,I<Integer> {}'}, {'Run.java':'public class Run<T> extends Run<java.util.List<T>> {}'}]
        for files in fixtures:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                for name,body in files.items():(root/name).write_text(body)
                report=translate(root,dry_run=True);row=next(r for r in report['results'] if r['file']=='Run.java')
                self.assertEqual(row['status'],'MANUAL_REVIEW',report);self.assertTrue('Conflicting generic' in row['reason'] or 'Cyclic superclass' in row['reason'],row)

    def test_invalid_bounds_and_bridge_overload_remain_explicit(self):
        for files,reason in [({'Base.java':'public class Base<T extends Number> {}','Run.java':'public class Run extends Base<String> {}'},'bound'),({'Base.java':'public class Base<T> {public T echo(T v){return v;}}','Run.java':'public class Run extends Base<String> {public String echo(String v){return v;}public int echo(int v){return v;}}'},'Generic bridge')]:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                for name,body in files.items():(root/name).write_text(body)
                report=translate(root,dry_run=True);blocked=next(row for row in report['results'] if row['file']=='Run.java')
                self.assertEqual(blocked['status'],'MANUAL_REVIEW',report);self.assertIn(reason,blocked['reason'])

if __name__=='__main__':unittest.main()
