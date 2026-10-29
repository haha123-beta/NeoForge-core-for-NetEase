import os,sys,unittest,json,tempfile,subprocess
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from java_official_probe import run_original
from java_official_probe import JDK
from translate_java import translate
from build_source_bundle import core_bundle,collect_sources
from workspace_paths import SCRIPTS_ROOT
from java_interface_oracle import verify
from test_network086 import GROUPS
from java_frontend import api_index,parse_source
from java_codegen import generate,NeedsLowering
import test_official_interfaces086 as execution

class ModelMath087(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.package=Package();cls.math=cls.package.load('minecraft.model_math')

    def test_model_state_original_complete_instance_contract(self):verify(self.math.INTERFACE_CONTRACTS)

    def test_original_identity_reference_copy_and_hash(self):
        ref=Path(__file__).parents[1]/'references/checkpoint-0.8.7'
        expected=run_original((ref/'model_state_identity_probe.java.txt').read_text(),GROUPS)
        m=self.math
        class State(m.ModelState):pass
        state=State();identity=m.Transformation.identity();copy=identity.getMatrix();copy.m00(2.0)
        original=m.Matrix4f().m00(3.0);wrapped=m.Transformation(original);original.m00(4.0)
        actual=[state.getRotation() is identity,state.isUvLocked(),identity.getMatrix().m00(),wrapped.getMatrix().m00(),wrapped.getMatrix() is original,m.Transformation(None).equals(identity),identity.hashCode()]
        # inverse itself is outside the reviewed source API, so retain the first
        # seven original observations rather than manufacturing its behavior.
        result='RESULT:'+','.join(str(v).lower() if isinstance(v,bool) else str(v) for v in actual)
        self.assertEqual(result,expected.rsplit(',',1)[0])
        lang=self.package.load('java_stdlib.lang')
        with self.assertRaises(lang.NullPointerException):m.Matrix4f(None)

    def test_original_matrix_column_order_float_bits_and_hash(self):
        ref=Path(__file__).parents[1]/'references/checkpoint-0.8.7'
        expected=run_original((ref/'matrix_storage_probe.java.txt').read_text(),GROUPS).splitlines();m=self.math;actual=[]
        for value in (0.0,-0.0,0.1,float('nan'),float('inf')):
            matrix=m.Matrix4f(*([value]+list(range(2,17))));copy=m.Matrix4f(matrix)
            bits=((m._bits(matrix.m00())+2147483648)&4294967295)-2147483648
            actual.append(','.join(str(v).lower() if isinstance(v,bool) else str(v) for v in (bits,matrix.hashCode(),matrix.equals(copy),matrix.m01(),matrix.m10())))
        self.assertEqual(actual,expected)
        matrix=m.Matrix4f().zero();self.assertEqual([getattr(matrix,'m'+str(c)+str(r))() for c in range(4) for r in range(4)],[0.0]*16)
        matrix.identity();self.assertEqual(matrix.m33(),1.0)

    def test_actual_python2_default_model_state_and_matrix_copy(self):
        source='''import net.minecraft.client.resources.model.ModelState;import com.mojang.math.Transformation;import org.joml.Matrix4f;
public class Run implements ModelState {public int run(){Matrix4f m=getRotation().getMatrix();m.m00(2.0f);if(getRotation().getMatrix().m00()!=1.0f)return 99;Matrix4f original=new Matrix4f();Transformation t=new Transformation(original);original.m00(4.0f);if(t.getMatrix().m00()!=4.0f)return 98;Matrix4f copy=new Matrix4f(original);copy.zero();if(original.m00()!=4.0f)return 97;return isUvLocked()?96:7;}}'''
        execution.OfficialInterfaces086().execute(source,'7')

    def test_unsupported_math_codecs_private_fields_and_ambiguous_null_copy_reject(self):
        known,_=api_index()
        for source in ['import org.joml.Matrix4f;class Run {Object x=new Matrix4f(null);}','import org.joml.Matrix4f;class Run {float f(Matrix4f m){return m.m00;}}','import com.mojang.math.Transformation;class Run {Object x=Transformation.CODEC;}','import com.mojang.math.Transformation;class Run {Object f(Transformation t){return t.getTranslation();}}','import org.joml.Matrix4f;class Run {Object f(Matrix4f m){return m.invert();}}']:
            with self.subTest(source=source),self.assertRaises(NeedsLowering):generate(parse_source(source,known_types=known))

    def test_private_field_method_storage_and_float_comparisons_actual_python2(self):
        source='''import net.minecraft.client.resources.model.ModelState;
public class Run implements ModelState {private boolean isUvLocked=true;private int count=2;public boolean isUvLocked(){return this.isUvLocked;}public int count(){return this.count;}public int run(){this.count+=3;count++;if(!isUvLocked())return 99;if(0.0f!=-0.0f)return 98;if(Float.NaN==Float.NaN)return 97;if(Float.NaN>0.0f)return 96;if(1.0f>=2.0f)return 95;return count();}}'''
        execution.OfficialInterfaces086().execute(source,'6')
        known,_=api_index()
        with self.assertRaises(NeedsLowering):generate(parse_source('class Box {private int x;public int x(){return x;}}class Run {Run(){Box b=new Box();b.x=7;}}',known_types=known))

    def test_same_named_cross_package_parents_have_distinct_private_storage(self):
        files={'a/Same.java':'package a;public class Same {private int x=1;public int x(){return x;}}','b/Same.java':'package b;public class Same extends a.Same {private int y=2;public int y(){return y;}public int run(){return x()*10+y();}}','Run.java':'public class Run {public int run(){return new b.Same().run();}}'}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';source.mkdir()
            for name,body in files.items():
                path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body)
            probe=root/'Probe.java';probe.write_text('public class Probe {public static void main(String[] a){System.out.print(new Run().run());}}');classes=root/'classes';classes.mkdir()
            j=subprocess.run([str(JDK/'javac.exe'),'-d',str(classes)]+[str(source/name) for name in files]+[str(probe)],capture_output=True,text=True);self.assertEqual(j.returncode,0,j.stderr)
            j=subprocess.run([str(JDK/'java.exe'),'-cp',str(classes),'Probe'],capture_output=True,text=True);self.assertEqual(j.returncode,0,j.stderr);self.assertEqual(j.stdout,'12')
            report=translate(source,root/'out');self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(3,0,0),report)
            sources=core_bundle()['sources'];sources.update(collect_sources(root/'out/source'))
            data={'loader_source':(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8'),'sources':sources,'module':'Run','class_name':'Run','expected':j.stdout}
            path=root/'probe.json';path.write_text(json.dumps(data),encoding='utf-8')
            run=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(Path(__file__).with_name('probe_interfaces082_python27.py')),str(path)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+'\n'+run.stderr)

if __name__=='__main__':unittest.main()
