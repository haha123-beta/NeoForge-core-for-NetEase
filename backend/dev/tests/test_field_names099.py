import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_interfaces082 as oracle
from translate_java import translate

class FieldNames099(unittest.TestCase):
    def test_public_field_and_accessor_cross_file_read_write_three_runtimes(self):
        oracle.Interfaces082().compare({'api/Entry.java':'package api;public class Entry {public int value;public boolean processed;public Entry(int n){value=n;}public int value(){return value;}public boolean processed(){return processed;}public void mark(){processed=true;}}','use/Run.java':'package use;import api.Entry;public class Run {public int run(){Entry x=new Entry(2);x.value=7;x.mark();if(!x.processed)return -1;return x.value+x.value();}}'},'14')

    def test_same_unit_public_field_and_final_initialization_three_runtimes(self):
        oracle.Interfaces082().compare({'use/Run.java':'package use;public class Run {public final int value=4;public int value(){return value;}public int run(){return this.value+value();}}'},'8')

    def test_private_field_access_and_static_collision_remain_blocked(self):
        for files in [ {'use/A.java':'package use;public class A {private int n;public int n(){return n;}}','use/Run.java':'package use;public class Run {int run(){A a=new A();return a.n;}}'}, {'use/Run.java':'package use;class Run {static int n;static int n(){return n;}}'}]:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                for name,source in files.items():p=root/name;p.parent.mkdir(exist_ok=True);p.write_text(source)
                r=translate(root,dry_run=True);self.assertGreater(r['manual_review'],0,r)

if __name__=='__main__':unittest.main()
