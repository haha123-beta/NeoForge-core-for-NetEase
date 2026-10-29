import json,sys,tempfile,subprocess,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from translate_java import translate
import test_interfaces082 as oracle

class ExistingCalls092(unittest.TestCase):
    def test_existing_array_runnable_optional_implementations_execute_three_runtimes(self):
        oracle.Interfaces082().compare({'use/Run.java':'''package use;
import java.util.Arrays;import java.util.List;import java.util.Optional;
public class Run {int value;public int run(){int[] a={3,1,2};System.arraycopy(a,0,a,1,2);
int[] b=Arrays.copyOf(a,5);int[] c=Arrays.copyOfRange(a,1,4);Arrays.sort(a);
List<String> list=Arrays.asList(new String[]{"x","y"});Runnable r=()->{value=7;};r.run();
Optional<String> empty=Optional.empty();if(empty==null)return -1;
return value+a[0]+a[1]+a[2]+b[4]+c[2]+list.size();}}'''},'16')
    def test_invalid_argument_type_and_arity_rejected_from_full_entry(self):
        cases=['System.arraycopy(new int[1],0L,new int[1],0,1);','Runnable r=()->{};r.run(1);','java.util.Optional.empty(1);',
               'java.util.Arrays.copyOf(new int[1],true);','s.equals(System.gc());']
        for body in cases:
            with self.subTest(body=body),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'source';root.mkdir();file=root/'Run.java';file.write_text('class Run {void run(String s){'+body+'}}')
                report=translate(root,dry_run=True)
                self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(0,1,0),report)
                p=subprocess.run([str(oracle.JDK/'javac.exe'),'-proc:none',str(file)],capture_output=True,text=True)
                self.assertNotEqual(p.returncode,0)
    def test_non_event_consumer_is_rejected_before_codegen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';root.mkdir();(root/'Run.java').write_text('import net.neoforged.bus.api.IEventBus;class Run {void run(IEventBus bus){bus.addListener((String s)->{});}}')
            report=translate(root,dry_run=True);self.assertEqual(report['manual_review'],1)
            self.assertIn('proven Event subtype',report['results'][0]['reason'])

    def test_array_null_guards_execute_in_all_three_runtimes(self):
        oracle.Interfaces082().compare({'use/Run.java':'''package use;
import java.util.Arrays;public class Run {public int run(){int count=0;
String[] strings=null;int[] ints=null;
try {Arrays.asList(strings);}catch(NullPointerException e){count++;}
try {Arrays.sort(ints);}catch(NullPointerException e){count+=2;}
return count;}}'''},'3')

    def test_unreviewed_future_observation_remains_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';root.mkdir()
            (root/'Run.java').write_text('import net.neoforged.fml.event.lifecycle.FMLCommonSetupEvent;class Run {Object run(FMLCommonSetupEvent e){return e.enqueueWork(()->{});}}')
            report=translate(root,dry_run=True)
            self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(0,1,0),report)
            self.assertIn('Future return observation',report['results'][0]['reason'])

    def test_official_abstract_event_registration_requires_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';root.mkdir()
            (root/'Run.java').write_text('import net.neoforged.bus.api.IEventBus;import net.neoforged.bus.api.Event;class Run {void run(IEventBus b){b.addListener((Event e)->{});}}')
            report=translate(root,dry_run=True)
            self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(0,1,0),report)
            self.assertIn('rejects abstract event',report['results'][0]['reason'])

if __name__=='__main__':unittest.main()
