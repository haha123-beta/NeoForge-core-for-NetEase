import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from java_official_probe import native,run_original
from translate_java import translate
from build_source_bundle import collect_sources,core_bundle
from workspace_paths import SCRIPTS_ROOT
from harness import Package

class Vertex085(unittest.TestCase):
    def test_original_layouts_modes_overflow_and_actual_python2_source(self):
        p='com.mojang.blaze3d.vertex.';F=native(p+'VertexFormat');E=native(p+'VertexFormatElement');M=native(p+'VertexFormat$Mode').replace('$','.');I=native(p+'VertexFormat$IndexType').replace('$','.');T=native(p+'VertexFormatElement$Type').replace('$','.');D=native(p+'DefaultVertexFormat')
        counts=[-2147483648,-65536,-7,-1,0,1,3,4,7,65535,65536,2147483647];padding=[-2147483648,-17,-1,0,1,4,2147483647]
        cs=','.join(map(str,counts));ps=','.join(map(str,padding))
        source='public class Probe {public static void main(String[] a){int[] cs={'+cs+'};for('+M+' m:'+M+'.values()){System.out.println(m.name()+","+m.i+","+m.j+","+m.k+","+m.l);for(int n:cs)System.out.println(m.a(n));}for(int n:cs)System.out.println('+I+'.a(n).name());for('+T+' t:'+T+'.class.getEnumConstants())System.out.println(t.name()+","+t.a()+","+t.b()+","+t.toString());'
        source+='for('+F+' f:new '+F+'[]{'+','.join(D+'.'+c for c in 'abcdefghijklm')+'}){System.out.print(f.b()+","+f.f()+","+f.hashCode());for(int n:f.e())System.out.print(","+n);System.out.println();System.out.print(f.toString());}'
        source+='for(int p:new int[]{'+ps+'}){'+F+' f='+F+'.a().a("Position",'+E+'.b).a("Color",'+E+'.c).a(p).a("Normal",'+E+'.h).a(1).a();System.out.println(f.b()+","+f.a('+E+'.c)+","+f.a('+E+'.h)+","+f.f()+","+f.hashCode());f.e()[0]=99;System.out.println(f.a('+E+'.b)+","+f.f()+","+f.hashCode());}}}'
        expected=run_original(source,('it.unimi.dsi:fastutil','com.google.guava:guava')).splitlines()
        java='import com.mojang.blaze3d.vertex.VertexFormat;import com.mojang.blaze3d.vertex.VertexFormatElement;import com.mojang.blaze3d.vertex.DefaultVertexFormat;public class Run {public int run(){VertexFormat f=VertexFormat.builder().add("Position",VertexFormatElement.POSITION).add("Color",VertexFormatElement.COLOR).padding(1).add("Normal",VertexFormatElement.NORMAL).padding(1).build();return f.getVertexSize()+f.getOffset(VertexFormatElement.COLOR)+VertexFormat.Mode.QUADS.indexCount(8)+VertexFormat.IndexType.least(65536).bytes+DefaultVertexFormat.NEW_ENTITY.getVertexSize();}}'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';root.mkdir();(root/'Run.java').write_text(java)
            report=translate(root,Path(tmp)/'converted')
            self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(1,0,0),report['results'])
            sources=core_bundle()['sources'];sources.update(collect_sources(Path(tmp)/'converted/source'))
            data={'loader_source':(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8'),'sources':sources,'counts':counts,'padding':padding,'expected':expected}
            path=Path(tmp)/'data.json';path.write_text(json.dumps(data),encoding='utf-8')
            run=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(Path(__file__).with_name('probe_vertex085_python27.py')),str(path)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+'\n'+run.stderr)
            self.assertGreater(json.loads(run.stdout.strip().splitlines()[-1])['rows'],180)

    def test_rejections_immutable_views_builder_snapshot_and_shared_identity(self):
        pkg=Package();v=pkg.load('minecraft.vertex_format');F=v.VertexFormat;E=v.VertexFormatElement;l=pkg.load('java_stdlib.lang')
        self.assertIs(pkg.load('shader.material').VertexFormat,F)
        self.assertNotIn('sen.manaita_plus_legacy.client.shander.comis.CCShaderInstance',pkg.load('core.java_api').collect_java_api())
        self.assertFalse(hasattr(pkg.load('shader.material'),'CCShaderInstance'))
        b=F.builder().add('Position',E.POSITION);f=b.build();b.add('Color',E.COLOR)
        self.assertEqual(f.getVertexSize(),12);self.assertEqual(b.build().getVertexSize(),16)
        with self.assertRaises(l.UnsupportedOperationException):f.getElements().add(E.NORMAL)
        with self.assertRaises(l.IllegalArgumentException):b.add('Position',E.NORMAL).build()
        with self.assertRaises(l.NullPointerException):F.builder().add(None,E.POSITION)
        with self.assertRaises(l.IllegalArgumentException):E(32,0,E.Type.FLOAT,E.Usage.POSITION,3)
        with self.assertRaises(l.IllegalStateException):E(6,1,E.Type.FLOAT,E.Usage.POSITION,3)
        with self.assertRaises(AttributeError):E.POSITION._count=9
        self.assertIs(E.UV,E.UV0);self.assertIsNone(E.byId(6))
        with self.assertRaises(l.ArrayIndexOutOfBoundsException):E.byId(-1)
        for action in (f.setupBufferState,f.clearBufferState,f.getImmediateDrawVertexBuffer,lambda:E.elementsFromMask(1),lambda:E.register(6,0,E.Type.FLOAT,E.Usage.POSITION,3)):
            with self.assertRaises(l.UnsupportedOperationException):action()
        for expression in ('VertexFormat.builder().build().setupBufferState()','VertexFormatElement.register(6,0,VertexFormatElement.Type.FLOAT,VertexFormatElement.Usage.POSITION,3)','VertexFormat.Mode.QUADS.primitiveStride=9'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'Run.java').write_text('import com.mojang.blaze3d.vertex.VertexFormat;import com.mojang.blaze3d.vertex.VertexFormatElement;class Run {void run(){'+expression+';}}')
                self.assertEqual(translate(root,dry_run=True)['manual_review'],1,expression)

if __name__=='__main__':unittest.main()
