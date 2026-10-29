import os,sys,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from java_interface_oracle import verify
from java_official_probe import run_original
from test_network086 import GROUPS
from java_frontend import api_index,parse_source
from java_codegen import generate,NeedsLowering
from java_method_overloads import erased_signature
import test_official_interfaces086 as execution

class HolderGetter087(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.package=Package();cls.holder=cls.package.load('minecraft.holder_contracts')
    def test_original_complete_generic_contract(self):verify(self.holder.GENERIC_INTERFACES)
    def test_default_missing_messages_original_and_native(self):
        ref=Path(__file__).parents[1]/'references/checkpoint-0.8.7'
        expected=run_original((ref/'holder_getter_probe.java.txt').read_text(),GROUPS).splitlines();p=self.package;m=self.holder;optional=p.load('java_stdlib.util').Optional;lang=p.load('java_stdlib.lang')
        class Getter(m.HolderGetter):
            def get(self,key):return optional.empty()
        g=Getter();actual=[]
        for signature in ('net.minecraft.resources.ResourceKey<java.lang.String>','net.minecraft.tags.TagKey<java.lang.String>'):
            with self.assertRaises(lang.IllegalStateException) as captured:g.getOrThrow(None,_nc_java_signature=(signature,))
            actual.append(str(captured.exception))
        self.assertEqual(actual,expected)

    def test_success_identity_and_null_optional(self):
        p=self.package;m=self.holder;optional=p.load('java_stdlib.util').Optional;lang=p.load('java_stdlib.lang');reg=p.load('neoforge.registries').Registry('demo:holder');reg.put('demo:a','a');holder=reg._holder_for_value('a')
        class Getter(m.HolderGetter):
            def get(self,key):return optional.of(holder)
        self.assertIs(Getter().getOrThrow(None),holder)
        class Broken(m.HolderGetter):
            def get(self,key):return None
        with self.assertRaises(lang.NullPointerException):Broken().getOrThrow(None)

    def test_specialized_overloaded_defaults_actual_python2(self):
        source='''import net.minecraft.core.HolderGetter;import net.minecraft.core.Holder;import net.minecraft.core.HolderSet;import net.minecraft.resources.ResourceKey;import net.minecraft.tags.TagKey;import java.util.Optional;
public class Run implements HolderGetter<String> {public Optional<Holder.Reference<String>> get(ResourceKey<String> key){return Optional.empty();}public Optional<HolderSet.Named<String>> get(TagKey<String> tag){return Optional.empty();}public int run(){int count=0;HolderGetter<String> getter=this;try{getter.getOrThrow((ResourceKey<String>)null);}catch(IllegalStateException e){count++;}try{getter.getOrThrow((TagKey<String>)null);}catch(IllegalStateException e){count++;}return count;}}'''
        execution.OfficialInterfaces086().execute(source,'2')

    def test_generic_parameter_erasures_and_conflict_guards(self):
        known,_=api_index()
        for source in ['import java.util.List;class Run {int f(List<String> a){return 1;}int f(List<Integer> b){return 2;}}','class Run {<T> int f(T a){return 1;}<U> int f(U b){return 2;}}','import java.util.List;class Run {Run(List<String> a){}Run(List<Integer> b){}}']:
            with self.subTest(source=source),self.assertRaises(NeedsLowering):generate(parse_source(source,known_types=known))
        row={'parameters':[{'declared_type':'T[]'}],'type_parameters':'<T extends Number>'}
        self.assertEqual(erased_signature(row,{}, {'imports':[],'package':None}),('java.lang.Number[]',))

    def test_distinct_generic_overloads_keep_types_actual_python2(self):
        source='''import java.util.List;import java.util.Set;public class Run {int pick(List<String> x){return 1;}int pick(Set<String> x){return 2;}public int run(){return pick((List<String>)null)*10+pick((Set<String>)null);}}'''
        expected=run_original(source.replace('public class Run','class Run')+'public class Probe {public static void main(String[] a){System.out.print(new Run().run());}}')
        self.assertEqual(expected,'12');execution.OfficialInterfaces086().execute(source,expected)
        known,_=api_index()
        with self.assertRaises(NeedsLowering):generate(parse_source(source.replace('pick((List<String>)null)','pick((List<Integer>)null)'),known_types=known))

if __name__=='__main__':unittest.main()
