import os,sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from java_frontend import parse_source,api_index
from java_codegen import generate,NeedsLowering
from translate_java import translate
from java_official_probe import run_original
import test_official_interfaces086 as execution

class AbstractClasses087(unittest.TestCase):
    def test_abstract_class_defers_interface_requirement_and_reabstracts_default(self):
        source='interface A {default int value(){return 99;}int other();}abstract class Base implements A {public abstract int value();public int add(){return value()+other();}}public class Run extends Base {public int value(){return 5;}public int other(){return 2;}public int run(){A a=this;return a.value()+add();}}'
        result=run_original(source.replace('public class Run','class Run')+'public class Probe {public static void main(String[] a){System.out.print(new Run().run());}}')
        self.assertEqual(result,'12');execution.OfficialInterfaces086().execute(source,result)

    def test_abstract_native_subclass_in_actual_python2(self):
        execution.OfficialInterfaces086().execute('import net.minecraft.world.entity.ai.goal.Goal;abstract class Base extends Goal {public abstract boolean canUse();public int v(){return 7;}}public class Run extends Base {public boolean canUse(){return true;}public int run(){return v()+(canContinueToUse()?1:99);}}','8')

    def test_abstract_class_cannot_be_instantiated_or_referenced_as_factory(self):
        known,_=api_index()
        for source in ['abstract class Base {}class Run {Object f(){return new Base();}}','import java.util.function.Supplier;abstract class Base {}class Run {Supplier<Base> f(){return Base::new;}}','abstract class Base {abstract int f();}class Run extends Base {}','interface A {int f();}abstract class Base implements A {}class Run extends Base {}','interface A {default int f(){return 1;}}interface B {default int f(){return 2;}}abstract class Run implements A,B {}','interface A {int f();}abstract class Run implements A {protected abstract int f();}']:
            with self.subTest(source=source),self.assertRaises(NeedsLowering):generate(parse_source(source,known_types=known))

    def test_cross_file_abstract_metadata_defers_to_concrete_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'demo';folder.mkdir()
            for name,source in {'A':'package demo;public interface A {int f();}','Base':'package demo;public abstract class Base implements A {public abstract int f();public int run(){return f();}}','Child':'package demo;public class Child extends Base {public int f(){return 7;}}'}.items():
                (folder/(name+'.java')).write_text(source)
            report=translate(root,dry_run=True)
            self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(3,0,0),report)

if __name__=='__main__':unittest.main()
