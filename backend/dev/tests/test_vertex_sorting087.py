import sys,os,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from java_official_probe import run_original
from java_interface_oracle import verify
from java_frontend import api_index,parse_source
from java_codegen import generate,NeedsLowering
from test_network086 import GROUPS
import test_official_interfaces086 as execution

class VertexSorting087(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.package=Package();cls.sorting=cls.package.load('minecraft.vertex_sorting')
    def test_complete_original_instance_contracts(self):verify(self.sorting.INTERFACE_CONTRACTS)

    def test_original_stable_float_sort_and_live_origin(self):
        ref=Path(__file__).parents[1]/'references/checkpoint-0.8.7'
        expected=run_original((ref/'vertex_sorting_probe.java.txt').read_text(),GROUPS).splitlines()
        m=self.sorting;v=m.Vector3f;s=m.VertexSorting
        points=[v(1,0,0),v(0,0,-2),v(0,0,2),v(),v(-0.0,0,0),v(float('nan'),0,0),v(float('inf'),0,1)]
        out=[str(list(s.DISTANCE_TO_ORIGIN.sort(points))),str(list(s.ORTHOGRAPHIC_Z.sort(points)))];origin=v();live=s._by_vector(origin);pair=[v(),v(2,0,0)]
        out.append(str(list(live.sort(pair))));origin.x=3.0;out.append(str(list(live.sort(pair))))
        bits=self.package.load('minecraft.model_math')._bits(v(0.1,0.2,0.3).distanceSquared(v(0.4,0.5,0.6)))
        out.extend([str(bits),'0','NullPointerException']);self.assertEqual(out,expected)
        absent=s._by_function(None);self.assertEqual(len(absent.sort([])),0)
        with self.assertRaises(self.package.load('java_stdlib.lang').NullPointerException):absent.sort(pair)

    def test_function_calls_once_in_input_order_and_signed_zero(self):
        m=self.sorting
        class Distance(m.DistanceFunction):
            def __init__(self):self.calls=[]
            def apply(self,point):self.calls.append(point);return point.z
        d=Distance();points=[m.Vector3f(0,0,-0.0),m.Vector3f(0,0,0.0),m.Vector3f(0,0,float('nan')),m.Vector3f(0,0,0.0)]
        self.assertEqual(list(m.VertexSorting._by_function(d).sort(points)),[2,1,3,0]);self.assertEqual(d.calls,points)

    def test_functional_sort_array_and_mutable_vector_fields_actual_python2(self):
        source='''import org.joml.Vector3f;import com.mojang.blaze3d.vertex.VertexSorting;
public class Run {public int run(){Vector3f a=new Vector3f(0.0f,0.0f,1.0f);a.x=2.0f;if(a.x()!=2.0f)return 99;Vector3f b=new Vector3f(0.0f,0.0f,3.0f);VertexSorting sorter=VertexSorting.byDistance(v->v.z());int[] order=sorter.sort(new Vector3f[]{a,b});return order[0]*10+order[1];}}'''
        execution.OfficialInterfaces086().execute(source,'10')
        execution.OfficialInterfaces086().execute('import org.joml.Vector3f;public class Run {int count=0;float side(){count++;return 1.0f;}public int run(){Vector3f v=null;try{v.x=side();}catch(NullPointerException e){return count;}return 99;}}','1')
        known,_=api_index()
        for invalid in ['import org.joml.Vector3f;class Run {void f(Vector3f v){v.x=null;}}','import org.joml.Vector3f;class Run {void f(){Vector3f.x=1.0f;}}','import com.mojang.blaze3d.vertex.VertexSorting;class Run {Object x=new VertexSorting();}']:
            with self.subTest(source=invalid),self.assertRaises(NeedsLowering):generate(parse_source(invalid,known_types=known))

if __name__=='__main__':unittest.main()
