import os,sys,tempfile,subprocess,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from translate_java import translate
import test_interfaces082 as oracle

class CallGuard092(unittest.TestCase):
    def test_invalid_string_calls_rejected_by_full_entry_and_real_jdk(self):
        for body in ('s.length(1);','s.equals();','s.neocoreMissingMethod();','String.length();','Object o=s;o.is(s);'):
            for deferred in (False,True):
                with self.subTest(body=body,deferred=deferred),tempfile.TemporaryDirectory() as tmp:
                    root=Path(tmp)/'source';(root/'audit').mkdir(parents=True)
                    file=root/'audit/Probe.java';file.write_text('package audit;public class Probe {public void run(String s){'+body+'}}')
                    report=translate(root,dry_run=True,defer_external_symbols=deferred)
                    self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(0,1,0),report)
                    p=subprocess.run([str(oracle.JDK/'javac.exe'),'-proc:none','-d',str(Path(tmp)/'classes'),str(file)],capture_output=True,text=True)
                    self.assertNotEqual(p.returncode,0)
    def test_legal_string_calls_execute_jdk_python3_and_python2(self):
        oracle.Interfaces082().compare({'use/Run.java':'package use;public class Run {public String run(){String s="abc";return s.length()+":"+s.equals(s);}}'},'3:true')
    def test_unreviewed_real_method_is_not_reported_as_official_nonexistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';root.mkdir();(root/'Run.java').write_text('class Run {void run(String s){s.trim();}}')
            row=translate(root,dry_run=True)['results'][0]
            self.assertEqual(row['status'],'MANUAL_REVIEW');self.assertEqual(row['details']['category'],'REVIEWED_API_CONTRACT_MISSING')
            self.assertEqual(row['details']['owner'],'java.lang.String')

if __name__=='__main__':unittest.main()
