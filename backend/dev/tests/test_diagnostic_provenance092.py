"""JDK-valid foreign generic ancestry stays blocked, with accurate source ownership."""
import json,sys,tempfile,subprocess,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from translate_java import translate
import test_interfaces082 as oracle

class Provenance092(unittest.TestCase):
    def test_supported_generic_ancestor_still_executes_three_runtimes(self):
        oracle.Interfaces082().compare({
            'base/Box.java':'package base;public class Box<T>{public T value;public Box(T x){value=x;}public T get(){return value;}}',
            'use/Child.java':'package use;import base.Box;public class Child extends Box<String>{public Child(){super("ok");}}',
            'use/Run.java':'package use;public class Run {public String run(){return new Child().get();}}'},'ok')

    def test_foreign_generic_blocker_is_not_reported_as_current_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';root.mkdir()
            files={'api/Broken.java':'package api;import java.util.ArrayList;public class Broken<T> extends ArrayList<T>{public static int value(){return 7;}}',
                   'use/Run.java':'package use;import api.Broken;public class Run {public int run(){return Broken.value();}}'}
            for n,s in files.items():
                p=root/n;p.parent.mkdir(exist_ok=True);p.write_text(s)
            javac=subprocess.run([str(oracle.JDK/'javac.exe'),'-d',str(Path(tmp)/'classes')]+[str(root/n) for n in files],capture_output=True,text=True)
            self.assertEqual(javac.returncode,0,javac.stderr)
            first=translate(root,dry_run=True);second=translate(root,dry_run=True)
            self.assertEqual(first,second)
            row=next(r for r in first['results'] if r['file']=='use/Run.java')
            self.assertEqual(row['status'],'MANUAL_REVIEW')
            self.assertEqual(row['details']['declaring_type'],'api.Broken')
            origin=row['details']['diagnostic_origin']
            self.assertEqual((origin['compilation_unit'],origin['referenced_file'],origin['referenced_type']),('use/Run.java','api/Broken.java','api.Broken'))
            self.assertIn('java.util.ArrayList<T>',row['reason'])

if __name__=='__main__':unittest.main()
