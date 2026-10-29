import os,sys,json,subprocess,tempfile,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from translate_java import translate
from build_source_bundle import collect_sources
from workspace_paths import SCRIPTS_ROOT
import test_interfaces082 as oracle

class ConfigBoxingIntegration087(unittest.TestCase):
    def test_cast_then_unbox_in_assignment_return_and_boolean_condition(self):
        oracle.Interfaces082().compare({'use/Run.java':'''package use; public class Run {
          static int integer(Object o){return (Integer)o;}
          static boolean flag(Object o){return (Boolean)o;}
          public int run(){Object a=7;Object b=false;int x=(Integer)a;boolean f=(Boolean)b;
            Boolean check=(Boolean)b;if(check)return 99;
            if(f)return 98;if(flag(b))return 97;return x+integer(a);}
        }'''},'14')

    def test_wrong_wrapper_and_null_keep_original_exceptions(self):
        oracle.Interfaces082().compare({'use/Run.java':'''package use; public class Run {
          public int run(){int n=0;Object x=7;
            try{boolean bad=(Boolean)x;return 99;}catch(ClassCastException e){n=3;}
            try{boolean bad=(Boolean)null;return 98;}catch(NullPointerException e){n=n+4;}
            return n;}
        }'''},'7')

    def test_config_native_boundary_generated_code_in_real_python2(self):
        code='''import net.neoforged.fml.event.config.ModConfigEvent;
import net.neoforged.neoforge.common.ModConfigSpec;
public class Run {
 public static ModConfigSpec SPEC;
 public static ModConfigSpec.IntValue NUMBER;
 public static ModConfigSpec.BooleanValue FLAG;
 public static int number; public static boolean flag;
 public static void read(ModConfigEvent.Loading e){
  if(e.getConfig().getModId().equals("demo") && e.getConfig().getSpec()==SPEC){
   number=(Integer)NUMBER.get(); flag=(Boolean)FLAG.get();
  }
 }
 public static boolean direct(){return FLAG.get();}
}'''
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'source';src.mkdir();(src/'Run.java').write_text(code)
            report=translate(src,root/'out')
            self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(1,0,0),report)
            sources=collect_sources(SCRIPTS_ROOT);sources.update(collect_sources(root/'out/source'))
            payload={'loader':(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8'),'sources':sources}
            (root/'bundle.json').write_text(json.dumps(payload),encoding='utf-8')
            runner='''from __future__ import print_function
import sys,json,io
with io.open(sys.argv[1],encoding='utf-8') as f:d=json.load(f)
s={};eval(compile(d['loader'].encode('utf-8'),'loader.py','exec'),s)
r=s['SourceModuleLoader'](d['sources']);api=r.load('core.java_api');scope=api.JavaApiImports(r).install(api.collect_java_api())
try:
 c=r.load('neoforge.config');ev=r.load('neoforge.event.fml.config');lang=r.load('java_stdlib.lang');run=r.load('Run').Run
 b=c.ModConfigSpec.Builder();run.NUMBER=b.defineInRange('n',7,0,20);run.FLAG=b.define('f',False);run.SPEC=b.build()
 event=ev.ModConfigEvent.Loading(c.ModConfig(c.ModConfig.Type.COMMON,run.SPEC,'demo'))
 run.read(event);assert type(run.number) is int and run.number==7
 assert type(run.flag) is bool and run.flag is False;assert run.direct() is False
 run.NUMBER.set(11);run.FLAG.set(True);run.read(event)
 assert run.number==11 and type(run.flag) is bool and run.flag is True
 foreign=ev.ModConfigEvent.Loading(c.ModConfig(c.ModConfig.Type.COMMON,b.build(),'other'))
 run.NUMBER.set(13);run.read(foreign);assert run.number==11
 run.FLAG=None
 try:run.direct();raise AssertionError('null receiver accepted')
 except lang.NullPointerException:pass
 print('CONFIG_PY27_OK')
finally:scope.close();r.close()
'''
            (root/'runner.py').write_text(runner,encoding='utf-8')
            result=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(root/'runner.py'),str(root/'bundle.json')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
            self.assertIn('CONFIG_PY27_OK',result.stdout)

    def test_cast_helper_stays_strict_and_boolean_boxing_rejects_numbers(self):
        pkg=Package();f=pkg.load('java_stdlib.function').Functional;lang=pkg.load('java_stdlib.lang')
        for value,kind in [(True,lang.Boolean),(7,lang.Integer)]:
            with self.assertRaises(lang.ClassCastException):f.castReference(value,kind)
        for value in (0,1,'true'):
            with self.assertRaises(lang.ClassCastException):f.boxBoolean(value)
        with self.assertRaises(lang.NullPointerException):f.unboxBoolean(None)

    def test_context_getter_wrong_arguments_never_fall_back_to_dynamic_call(self):
        from java_world_signatures import resolve
        for owner in ('net.minecraft.world.item.context.UseOnContext','net.minecraft.world.item.context.BlockPlaceContext'):
            with self.assertRaises(ValueError):resolve(owner,'getClickedPos',1,['int'])

    def test_entity_builder_defaults_and_overrides_are_independent(self):
        # Entity imports install package aliases; isolate them from the Java API
        # oracle's independent Package instances in the other tests in this file.
        code="""from harness import Package
e=Package().load('minecraft.entity')
first=e.EntityType.Builder.of(lambda kind,level:None,e.MobCategory.MISC).build('verify:defaults')
custom=e.EntityType.Builder.of(lambda kind,level:None,e.MobCategory.MISC).noSave().clientTrackingRange(9).updateInterval(2).build('verify:custom')
second=e.EntityType.Builder.of(lambda kind,level:None,e.MobCategory.MISC).build('verify:independent')
assert (first._serialize,first._client_tracking_range,first._update_interval)==(True,5,3)
assert (custom._serialize,custom._client_tracking_range,custom._update_interval)==(False,9,2)
assert (second._serialize,second._client_tracking_range,second._update_interval)==(True,5,3)
"""
        proc=subprocess.run([sys.executable,'-B','-c',code],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,encoding='utf-8',errors='replace',env=dict(os.environ,PYTHONIOENCODING='utf-8'))
        self.assertEqual(proc.returncode,0,proc.stdout+'\n'+proc.stderr)

    def test_block_item_generated_override_and_super_in_python2(self):
        source='''import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.Item;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.item.context.BlockPlaceContext;
public class Run extends BlockItem {
 public Run(Block b,Item.Properties p){super(b,p);}
 public BlockPlaceContext updatePlacementContext(BlockPlaceContext c){return super.updatePlacementContext(c);}
 public static BlockPlaceContext dispatch(BlockItem item,BlockPlaceContext c){return item.updatePlacementContext(c);}
}'''
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'source';src.mkdir();(src/'Run.java').write_text(source)
            report=translate(src,root/'out')
            self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(1,0,0),report)
            sources=collect_sources(SCRIPTS_ROOT);sources.update(collect_sources(root/'out/source'))
            (root/'bundle.json').write_text(json.dumps({'loader':(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8'),'sources':sources}),encoding='utf-8')
            runner='''from __future__ import print_function
import sys,json,io
with io.open(sys.argv[1],encoding='utf-8') as f:d=json.load(f)
s={};eval(compile(d['loader'].encode('utf-8'),'loader.py','exec'),s)
r=s['SourceModuleLoader'](d['sources']);api=r.load('core.java_api');scope=api.JavaApiImports(r).install(api.collect_java_api())
try:
 run=r.load('Run').Run;items=r.load('minecraft.item');contexts=r.load('minecraft.item_context');blocks=r.load('minecraft.block')
 item=run(blocks.Block().setRegistryName('check:block'),items.Item.Properties());context=contexts.BlockPlaceContext()
 assert run.dispatch(item,context) is context
 assert run.dispatch(item,None) is None
 try:item.place(context);raise AssertionError('unsupported placement succeeded')
 except NotImplementedError:pass
 print('BLOCK_SUPER_PY27_OK')
finally:scope.close();r.close()
'''
            (root/'runner.py').write_text(runner)
            result=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(root/'runner.py'),str(root/'bundle.json')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
            self.assertIn('BLOCK_SUPER_PY27_OK',result.stdout)

if __name__=='__main__':unittest.main()
