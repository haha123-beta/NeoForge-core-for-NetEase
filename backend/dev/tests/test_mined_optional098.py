import sys,unittest,tempfile,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_interfaces082 as oracle
from translate_java import translate
from harness import Package
class MinedOptional098(unittest.TestCase):
 def test_factory_translates_and_executes_java_python2_python3(self):
  oracle.Interfaces082().compare({'use/Run.java':'''package use;import java.util.Optional;
public class Run {public int run(){Optional<String> a=Optional.ofNullable("value");
Optional<String> b=Optional.ofNullable(null);String v=null;Optional<String> c=Optional.ofNullable(v);
if(a==null||b==null||c==null)return -1;return 7;}}'''},'7')
 def test_runtime_value_and_empty_semantics(self):
  o=Package().load('java_stdlib.util').JavaOptional
  self.assertFalse(o.ofNullable(None).isPresent());self.assertEqual(o.ofNullable('x').get(),'x')
 def test_generic_mismatch_and_primitive_subset_remain_blocked(self):
  for body in ['java.util.Optional<Integer> o=java.util.Optional.ofNullable("x");','Object o=java.util.Optional.ofNullable(1);','Object o=java.util.Optional.ofNullable("a","b");']:
   with tempfile.TemporaryDirectory() as t:
    root=Path(t);(root/'Run.java').write_text('class Run {void run(){'+body+'}}')
    r=translate(root,dry_run=True);self.assertEqual(r['manual_review'],1,r)
if __name__=='__main__':unittest.main()
