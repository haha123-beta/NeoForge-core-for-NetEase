import sys,os,unittest,re
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from java_official_probe import run_original
from test_network086 import GROUPS
from java_frontend import api_index,parse_source
from java_codegen import generate,NeedsLowering
import test_official_interfaces086 as execution

class ImmutableModel087(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package=Package();cls.guava=cls.package.load('java_stdlib.guava_map');cls.math=cls.package.load('minecraft.model_math')
    def test_original_snapshot_immutability_and_duplicate_timing(self):
        ref=Path(__file__).parents[1]/'references/checkpoint-0.8.7'
        probe=(ref/'immutable_map_probe.java.txt').read_text().replace('com.google.common.collect.ImmutableMap','ImmutableMap')
        result=run_original('import com.google.common.collect.ImmutableMap;'+probe,GROUPS)
        p=self.package;lang=p.load('java_stdlib.lang');maps=p.load('java_stdlib.util');g=self.guava
        a=lang.JavaString('a');b=lang.JavaString('b');source=maps.JavaMap();source.put(a,lang.Integer(1));source.put(b,lang.Integer(2));m=g.ImmutableMap.copyOf(source);source.put(a,lang.Integer(9))
        data='RESULT:'+str(m.get(a))+','+str(m.getOrDefault(lang.JavaString('x'),lang.Integer(7)))+','+str(m.containsKey(None)).lower()+','+str(m is g.ImmutableMap.copyOf(m)).lower()+','+str(m.hashCode())+','+str(m.keySet())
        self.assertEqual(result.splitlines(),[data,'UnsupportedOperationException','PUT_OK','IllegalArgumentException','NullPointerException'])
        with self.assertRaises(lang.UnsupportedOperationException):m.put('c',3)
        with self.assertRaises(lang.UnsupportedOperationException):m.entrySet().iterator().next().setValue(7)
        iterator=m.keySet().iterator();iterator.next()
        with self.assertRaises(lang.UnsupportedOperationException):iterator.remove()
        builder=g.ImmutableMap.builder().put(a,1).put(a,2)
        with self.assertRaises(lang.IllegalArgumentException):builder.buildOrThrow()
        with self.assertRaises(lang.NullPointerException):g.ImmutableMap.builder().put(None,1)
        self.assertIs(g.ImmutableMap.of(),g.ImmutableMap.copyOf(maps.JavaMap()))

    def test_original_item_display_context_all_values(self):
        ref=Path(__file__).parents[1]/'references/checkpoint-0.8.7'
        expected=run_original((ref/'display_context_probe.java.txt').read_text(),GROUPS)
        actual='\n'.join(','.join([str(v.name()),str(v.getId()),str(v.getSerializedName()),str(v.firstPerson()).lower()]) for v in self.math.ItemDisplayContext.values())
        self.assertEqual(actual,expected)

    def test_original_perspective_source_actual_python2(self):
        original=Path(__file__).parents[1]/'builds/manaita_087/input/sen/manaita_plus_legacy/client/model/PerspectiveModelState.java'
        source=re.sub(r'^package [^;]+;','',original.read_text(),flags=re.M).replace('public final class PerspectiveModelState','final class PerspectiveModelState')
        source=source.replace('import java.util.Map;','import java.util.Map;import java.util.HashMap;import org.joml.Matrix4f;')
        source+='''public class Run {public int run(){Map<ItemDisplayContext,Transformation> data=new HashMap<>();Transformation t=new Transformation(new Matrix4f().m00(2.0f));data.put(ItemDisplayContext.GUI,t);PerspectiveModelState state=new PerspectiveModelState(data,true);data.clear();if(state.getTransform(ItemDisplayContext.GUI)!=t)return 99;if(!state.isUvLocked())return 98;if(PerspectiveModelState.IDENTITY.getTransform(ItemDisplayContext.GROUND)!=Transformation.identity())return 97;return state.getTransform(ItemDisplayContext.GUI).getMatrix().equals(new Matrix4f().m00(2.0f))?7:96;}}'''
        execution.OfficialInterfaces086().execute(source,'7')

    def test_context_typed_empty_map_factory_and_rejection_of_invalid_types(self):
        execution.OfficialInterfaces086().execute('import java.util.Map;import com.google.common.collect.ImmutableMap;public class Run {Map<String,String> map;public Run(){this(ImmutableMap.of());}Run(Map<String,String> m){map=m;}public int run(){return map.size()+7;}}','7')
        known,_=api_index()
        for source in ['import com.google.common.collect.ImmutableMap;class Run {Object f(){return new ImmutableMap();}}','import com.google.common.collect.ImmutableMap;class Run {int f(){return take(ImmutableMap.of());}int take(String s){return 7;}}','import net.minecraft.world.item.ItemDisplayContext;class Run {Object x=ItemDisplayContext.CODEC;}']:
            with self.subTest(source=source),self.assertRaises(NeedsLowering):generate(parse_source(source,known_types=known))

if __name__=='__main__':unittest.main()
