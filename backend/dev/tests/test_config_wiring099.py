import sys,unittest,tempfile,subprocess,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from java_frontend import parse_source,api_index
from java_codegen import generate,NeedsLowering
from build_source_bundle import core_bundle
from workspace_paths import SCRIPTS_ROOT

SOURCE='''import net.neoforged.fml.ModContainer;import net.neoforged.fml.config.ModConfig;
import net.neoforged.neoforge.common.ModConfigSpec;
public class Run {public static void register(ModContainer c,ModConfigSpec s){
c.registerConfig(ModConfig.Type.COMMON,s);c.registerConfig(ModConfig.Type.CLIENT,s,"custom.toml");}}'''

KEY_SOURCE='''import net.neoforged.neoforge.registries.DeferredHolder;
import net.minecraft.world.level.block.Block;import net.minecraft.resources.ResourceKey;
public class KeyRun {public static ResourceKey<Block> key(DeferredHolder<Block,Block> h){return h.getKey();}}'''

class ConfigWiring099(unittest.TestCase):
    def test_typed_config_registration_generated_python2_python3(self):
        known,stale=api_index();self.assertFalse(stale)
        code=generate(parse_source(SOURCE,known_types=known))['python_source']
        sources=core_bundle()['sources'];sources['Run']={'source':code,'origin':'Run.java'}
        probe='''from __future__ import print_function
import io,json,sys
with io.open(sys.argv[1],encoding='utf-8') as f:d=json.load(f)
scope={};eval(compile(d['loader'].encode('utf-8'),'loader.py','exec'),scope)
r=scope['SourceModuleLoader'](d['sources']);api=r.load('core.java_api');s=api.JavaApiImports(r).install(api.collect_java_api())
try:
 c=r.load('neoforge.config');b=c.ModConfigSpec.Builder();b.define('enabled',True);spec=b.build();container=c.ModContainer('sample')
 r.load('Run').Run.register(container,spec)
 assert len(container.getConfigs())==2
 assert container.getConfig(c.ModConfig.Type.COMMON).getFileName()=='sample-common.toml'
 assert container.getConfig(c.ModConfig.Type.CLIENT).getFileName()=='custom.toml'
 container.close();assert container.getConfigs()==[]
 print('CONFIG_WIRING099_PASS')
finally:s.close();r.close()
'''
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'input.json';p.write_text(json.dumps(dict(sources=sources,loader=(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8'))),encoding='utf-8');f=root/'probe.py';f.write_text(probe)
            for exe in (sys.executable,r'D:\NeoCore工具\python27_validation\runtime\python.exe'):
                r=subprocess.run([exe,'-B',str(f),str(p)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_invalid_config_spec_type_and_unreviewed_constants_rejected(self):
        known,_=api_index()
        for source in (SOURCE.replace('Type.COMMON','Type.NOT_REAL'),SOURCE.replace('Type.COMMON,s','Type.COMMON,7'),SOURCE.replace('"custom.toml"','false')):
            with self.subTest(source=source),self.assertRaises(NeedsLowering):generate(parse_source(source,known_types=known))

    def test_fully_qualified_nested_identity_reuses_only_known_export(self):
        known,_=api_index()
        ir=parse_source(SOURCE,known_types=known)
        self.assertIn('net.neoforged.fml.config.ModConfig.Type',generate(ir)['required_api_types'])
        bad=SOURCE.replace('ModConfig.Type.COMMON','ModConfig.Unknown.COMMON')
        with self.assertRaises(NeedsLowering):generate(parse_source(bad,known_types=known))

    def test_reviewed_ancestry_shared_by_overloads_and_generic_bounds(self):
        from java_generic_contracts import proves_bound
        from java_method_overloads import subtype
        spec='net.neoforged.neoforge.common.ModConfigSpec';contract='net.neoforged.fml.config.IConfigSpec'
        self.assertTrue(subtype(spec,contract,{},{}))
        self.assertTrue(proves_bound(spec,contract,{},{}))
        self.assertFalse(subtype('java.lang.String',contract,{},{}))
        self.assertFalse(proves_bound('java.lang.String',contract,{},{}))
        known,_=api_index()
        bad='import net.minecraft.resources.ResourceKey;import net.minecraft.world.level.block.Block;class Run {ResourceKey<String> wrong(ResourceKey<Block> key){return key;}}'
        with self.assertRaises(NeedsLowering):generate(parse_source(bad,known_types=known))
        # 1.0.0 reviews the corrected entry-key provider. Its positive runtime
        # contract is checked in test_registry_keys100/test_foundations100.
        generate(parse_source(KEY_SOURCE,known_types=known))
        with self.assertRaises(NeedsLowering):generate(parse_source(KEY_SOURCE.replace('h.getKey()','h.getKey(1)'),known_types=known))

if __name__=='__main__':unittest.main()
