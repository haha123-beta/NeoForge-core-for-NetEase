import sys,os,tempfile,subprocess,unittest,json,math,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from translate_java import translate
from harness import Package
from java_official_probe import JDK
from build_source_bundle import core_bundle,collect_sources
from workspace_paths import SCRIPTS_ROOT
import test_interfaces082 as oracle

class Foundations100(unittest.TestCase):
    def test_integer_factory_boxing_parameter_conversion_and_null_unbox(self):
        oracle.Interfaces082().compare({
            'use/Run.java':'package use;public class Run {static long widen(long n){return n;}static int take(int n){return n+1;}static Number ref(Number n){return n;}public String run(){int caught=0;try{take((Integer)null);}catch(NullPointerException e){caught=1;}Integer a=Integer.valueOf(127);Integer b=Integer.valueOf(127);return ""+widen(7)+"|"+take(Integer.valueOf(41))+"|"+ref(Integer.valueOf(7))+"|"+caught+"|"+(a==b);}}'
        },'7|42|7|1|true')

    def test_sqrt_generated_java_python2_python3(self):
        oracle.Interfaces082().compare({'use/Run.java':'package use;public class Run {public int run(){float x=3.0f;float y=4.0f;return (int)((float)Math.sqrt(x*x+y*y));}}'},'5')
        oracle.Interfaces082().compare({'use/Run.java':'package use;public class Run {public String run(){return ""+(Math.sqrt(-1.0)!=Math.sqrt(-1.0));}}'},'true')

    def test_sqrt_edge_bits_against_jdk_on_python2_and_python3(self):
        values=[-1.0,-float('inf'),float('nan'),-0.0,0.0,4.0,float('inf'),5e-324,1.7976931348623157e308]
        source='public class Probe {public static void main(String[] a){double[] v={-1.0,Double.NEGATIVE_INFINITY,Double.NaN,-0.0,0.0,4.0,Double.POSITIVE_INFINITY,Double.MIN_VALUE,Double.MAX_VALUE};for(double x:v){double y=Math.sqrt(x);System.out.println(Double.isNaN(y)?"nan":Long.toHexString(Double.doubleToRawLongBits(y)));}}}'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'Probe.java').write_text(source)
            subprocess.run([str(JDK/'javac.exe'),str(p/'Probe.java')],check=True,capture_output=True)
            expected=subprocess.check_output([str(JDK/'java.exe'),'-cp',tmp,'Probe'],text=True).splitlines()
            runtime=Package().load('java_stdlib.lang').Math
            bits=lambda v:'nan' if math.isnan(v) else format(struct.unpack('>Q',struct.pack('>d',v))[0],'x')
            self.assertEqual([bits(runtime.sqrt(v)) for v in values],expected)
            probe=p/'probe.py'
            probe.write_text('import sys,math,struct,json\nsys.path.insert(0,sys.argv[1])\nfrom java_stdlib.lang import Math\nv=[-1.0,-float("inf"),float("nan"),-0.0,0.0,4.0,float("inf"),5e-324,1.7976931348623157e308]\ny=[Math.sqrt(x) for x in v]\nprint(json.dumps(["nan" if math.isnan(x) else format(struct.unpack(">Q",struct.pack(">d",x))[0],"x") for x in y]))\n')
            actual=json.loads(subprocess.check_output([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(probe),str(SCRIPTS_ROOT)],text=True))
            self.assertEqual(actual,expected)

    def generated(self,source,expected):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);inp=root/'input';inp.mkdir();(inp/'Run.java').write_text(source)
            result=translate(inp,root/'out')
            self.assertEqual((result['generated_for_review'],result['manual_review'],result['failed']),(1,0,0),result)
            sources=core_bundle()['sources'];sources.update(collect_sources(root/'out/input'))
            package=Package();loader=package.load('core.source_modules').SourceModuleLoader(sources)
            api=loader.load('core.java_api');scope=api.JavaApiImports(loader).install(api.collect_java_api())
            try:self.assertEqual(str(loader.load('Run').Run().run()),expected)
            finally:scope.close();loader.close()
            payload=dict(sources=sources,loader_source=(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8'),module='Run',class_name='Run',expected=expected)
            p=root/'probe.json';p.write_text(json.dumps(payload))
            run=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(Path(__file__).with_name('probe_interfaces082_python27.py')),str(p)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)

    def test_generated_get_key_and_typed_wildcard_iteration(self):
        self.generated('import net.neoforged.neoforge.registries.DeferredRegister;import net.neoforged.neoforge.registries.DeferredItem;import net.minecraft.world.item.Item;public class Run {public int run(){DeferredRegister.Items items=DeferredRegister.createItems("view");DeferredItem<Item> a=items.register("a",()->new Item(new Item.Properties()));items.getEntries().forEach(h->h.getKey().location().getPath());return a.getKey().location().getPath().length();}}','1')

    def test_mutable_wildcards_wrong_sqrt_and_holder_key_arguments_stay_blocked(self):
        for body in ['Integer.valueOf(true);','Integer.valueOf(1L);','Integer.valueOf("7");','Math.sqrt("wrong");','Math.sqrt(1,2);','java.util.Collection<java.util.List<? extends String>> c=null;c.forEach(x->x.add("bad"));',
                     'net.neoforged.neoforge.registries.DeferredItem<net.minecraft.world.item.Item> h=null;h.getKey(1);']:
            with self.subTest(body=body),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'Run.java').write_text('class Run {void run(){'+body+'}}')
                r=translate(root,dry_run=True);self.assertEqual((r['manual_review'],r['failed']),(1,0),r)

if __name__=='__main__':unittest.main()
