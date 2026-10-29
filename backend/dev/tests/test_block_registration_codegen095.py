"""Typed block registration subset, with incompatible suppliers rejected."""
import sys, unittest, json, hashlib, subprocess, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from java_frontend import parse_source, api_index
from java_codegen import generate, NeedsLowering
from build_source_bundle import core_bundle
from workspace_paths import SCRIPTS_ROOT

SOURCE = '''import net.minecraft.world.level.block.Block;
import java.util.function.Supplier;
import net.neoforged.neoforge.registries.DeferredRegister;
import net.neoforged.neoforge.registries.DeferredBlock;
public class Run {
 public static final DeferredRegister.Blocks BLOCKS=DeferredRegister.createBlocks("example");
 public static DeferredBlock<Block> make(Supplier<Block> source){return BLOCKS.register("one",source);}
 public static Block get(DeferredBlock<Block> value){return value.get();}
}'''


class BlockRegistrationCodegen095(unittest.TestCase):
    def test_concrete_block_supplier_and_get(self):
        known, _ = api_index()
        for namespace in ('example', 'unrelated'):
            self.assertTrue(generate(parse_source(SOURCE.replace('"example"', '"'+namespace+'"'), known_types=known)))

    def test_invalid_factory_argument_and_result(self):
        known, _ = api_index()
        cases = [SOURCE.replace('createBlocks("example")', 'createBlocks(7)'),
                 SOURCE.replace('BLOCKS.register("one",source)', 'BLOCKS.register("one",()->"wrong")'),
                 SOURCE.replace('BLOCKS.register("one",', 'BLOCKS.register(7,'),
                 SOURCE.replace('BLOCKS.register("one",source)', 'BLOCKS.register("one",7)')]
        for source in cases:
            with self.subTest(source=source), self.assertRaises(NeedsLowering):
                generate(parse_source(source, known_types=known))

    def test_typed_incompatible_supplier_is_not_accepted_by_erasure(self):
        source = SOURCE.replace('Supplier<Block> source', 'Supplier<String> source')
        known, _ = api_index()
        with self.assertRaises(NeedsLowering):
            generate(parse_source(source, known_types=known))

    def test_generated_make_and_get_execute_in_actual_python2(self):
        known, _ = api_index()
        code=generate(parse_source(SOURCE,known_types=known))['python_source']
        sources=core_bundle()['sources']
        sources['Run']={'source':code,'origin':'Run.java','sha256':hashlib.sha256(code.encode('utf-8')).hexdigest()}
        payload={'sources':sources,'loader_source':(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8')}
        probe='''from __future__ import print_function
import io,json,sys
with io.open(sys.argv[1],encoding='utf-8') as stream:data=json.load(stream)
scope={'__name__':'registration095_loader'}
eval(compile(data['loader_source'].encode('utf-8'),'source_modules.py','exec'),scope)
runtime=scope['SourceModuleLoader'](data['sources'])
api=runtime.load('core.java_api');imports=api.JavaApiImports(runtime).install(api.collect_java_api())
try:
    Run=runtime.load('Run').Run
    Block=runtime.load('minecraft.block').Block
    Supplier=runtime.load('java_stdlib.function').Supplier
    created=[]
    holder=Run.make(Supplier(lambda: created.append(1) or Block()))
    assert created==[] and not holder.isBound()
    Run.BLOCKS.freeze_and_register()
    assert created==[1] and Run.get(holder) is holder.get()
    print('GENERATED_REGISTRATION_PY2_PASS; engine_verified=false')
finally:imports.close();runtime.close()
'''
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'input.json').write_text(json.dumps(payload),encoding='utf-8');(root/'probe.py').write_text(probe,encoding='utf-8')
            result=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(root/'probe.py'),str(root/'input.json')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('GENERATED_REGISTRATION_PY2_PASS',result.stdout)


if __name__ == '__main__':
    unittest.main()
