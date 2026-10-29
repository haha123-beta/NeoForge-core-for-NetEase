import json,os,random,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from java_official_probe import native,run_original
from translate_java import translate
from build_source_bundle import collect_sources,core_bundle
from workspace_paths import SCRIPTS_ROOT
from harness import Package


class Geometry084(unittest.TestCase):
    def test_geometry_int_overflow_edges_against_original_jar_and_python2(self):
        randomizer=random.Random(841)
        cases=[[0,0,0,0,0,0,1,1],[10,20,7,5,13,22,10,10],[-3,-3,-2,0,0,0,2,2],[2147483647,-2147483648,2,-1,-1,0,9,9]]
        cases += [[randomizer.randint(-30,30) for i in range(8)] for unused in range(35)]
        p='net.minecraft.client.gui.navigation.';rect=native(p+'ScreenRectangle');axis=native(p+'ScreenAxis');direction=native(p+'ScreenDirection')
        rows=','.join('{'+','.join(map(str,c))+'}' for c in cases)
        source='public class Probe {public static void main(String[] a){int[][] cs=new int[][]{'+rows+'};for(int[] c:cs){'+rect+' r=new '+rect+'(c[0],c[1],c[2],c[3]);'+rect+' o=new '+rect+'(c[4],c[5],c[6],c[7]);'+rect+' cut=r.b(o);System.out.println(r.d()+","+r.b()+","+r.e()+","+r.c()+","+r.b('+axis+'.a)+","+r.b('+axis+'.b)+","+r.hashCode()+","+r.a(o)+","+(cut==null?"null":cut.d()+","+cut.b()+","+cut.g()+","+cut.h()));for('+direction+' d:'+direction+'.values()){'+rect+' b=r.c(d);System.out.println(r.b(d)+","+b.d()+","+b.b()+","+b.g()+","+b.h()+","+d.a(2,1)+","+d.b(2,1));}}}}'
        expected=run_original(source,('it.unimi.dsi:fastutil',)).splitlines()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';root.mkdir()
            java='import net.minecraft.client.gui.navigation.ScreenRectangle;import net.minecraft.client.gui.navigation.ScreenAxis;public class Run {public int run(){ScreenRectangle r=new ScreenRectangle(10,20,7,5);ScreenRectangle cut=r.intersection(new ScreenRectangle(13,22,10,10));return cut.width()+cut.height()+r.getCenterInAxis(ScreenAxis.HORIZONTAL);}}'
            (root/'Run.java').write_text(java);report=translate(root,Path(tmp)/'converted')
            self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(1,0,0),report['results'])
            sources=core_bundle()['sources'];sources.update(collect_sources(Path(tmp)/'converted/source'))
            data={'loader_source':(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8'),'sources':sources,'cases':cases,'expected':expected}
            input=Path(tmp)/'data.json';input.write_text(json.dumps(data),encoding='utf-8')
            run=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(Path(__file__).with_name('probe_gui084_python27.py')),str(input)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+'\n'+run.stderr)
            self.assertEqual(json.loads(run.stdout.strip().splitlines()[-1])['cases'],39)

    def test_half_open_hit_test_immutability_and_unreviewed_overloads(self):
        pkg=Package();gui=pkg.load('minecraft.gui_navigation');r=gui.ScreenRectangle(1,2,3,4)
        self.assertTrue(r.containsPoint(1,2));self.assertFalse(r.containsPoint(4,2));self.assertFalse(r.containsPoint(1,6))
        self.assertIsNone(r.intersection(gui.ScreenRectangle(4,2,1,1)))
        self.assertIs(gui.ScreenRectangle.empty(),gui.ScreenRectangle.empty())
        with self.assertRaises(AttributeError):r._width=7
        for source in ('new ScreenRectangle(1,2,3)','new ScreenRectangle(true,2,3,4)'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'Run.java').write_text('import net.minecraft.client.gui.navigation.ScreenRectangle;class Run {ScreenRectangle r='+source+';}')
                self.assertEqual(translate(root,dry_run=True)['manual_review'],1)


if __name__=='__main__':unittest.main()
