import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from java_mixin_plan import plan,MixinPlanError
from java_mixin_refmap import inspect as inspect_refmap
from translate_java import translate
from build_source_bundle import content_bundle,core_bundle
from run_translation_job import run_job
from harness import Package
import test_mixin_weave_r55 as base
import test_mixin_modify_arg_r64 as argbase
import test_native_mixin_lowering_r69 as native


def array_hooks(root, files):
    path=root/'demo/Hooks.java'
    text=path.read_text(encoding='utf-8').replace('@Mixin(Target.class)','@Mixin(value={Target.class})')
    import re
    text=re.sub(r'method="([^"]+)"',r'method={"\1"}',text)
    if '@Inject(' in text and '@ModifyArg(' not in text:
        text=text.replace('at=@At("RETURN")','at={@At(value="RETURN")}')
    path.write_text(text,encoding='utf-8');files['demo/Hooks.java']=text
    config=json.loads((root/'demo.mixins.json').read_bytes());config['refmap']='absent.refmap.json'
    (root/'demo.mixins.json').write_text(json.dumps(config),encoding='utf-8');files['demo.mixins.json']=json.dumps(config)


class CfrMixinTests(unittest.TestCase):
    def test_singleton_callbacks_original_body_jdk_and_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'original';root.mkdir();files=base.fixture(root,base.ACTIVE[0]);array_hooks(root,files)
            contract=plan(root)
            self.assertEqual(contract['configs'][0]['reference_map']['mode'],'missing_passthrough')
            self.assertTrue(contract['configs'][0]['reference_map']['declared'])
            result=translate(root,Path(tmp)/'out')
            self.assertEqual((result['manual_review'],result['failed']),(0,0),result)
            actual=base.previous.actual(Path(tmp)/'out/original')
            self.assertEqual(actual,'12');self.assertEqual(actual,base.oracle(root,files))
            self.assertEqual({name:(root/name).read_text(encoding='utf-8') for name in files},files)

    def test_singleton_modify_arg_preserves_argument_evaluation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'original';root.mkdir();files=argbase.fixture(root,argbase.CASES[0]);array_hooks(root,files)
            result=translate(root,Path(tmp)/'out')
            self.assertEqual((result['manual_review'],result['failed']),(0,0),result)
            actual=base.previous.actual(Path(tmp)/'out/original')
            self.assertEqual(actual,'422');self.assertEqual(actual,base.oracle(root,files))

    def test_native_constructor_arrays_register_and_unload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'original';root.mkdir();native.fixture(root)
            path=root/'nativehooks/Hooks.java';text=path.read_text(encoding='utf-8')
            text=text.replace('@Mixin(AbstractContainerMenu.class)','@Mixin(value={AbstractContainerMenu.class})')
            text=text.replace('method="<init>",at=@At("TAIL")','method={"<init>"},at={@At(value="TAIL")}')
            path.write_text(text,encoding='utf-8')
            config=Path(tmp)/'job.json';config.write_text(json.dumps({'input':str(root),'output_root':str(Path(tmp)/'out'),
                'distribution':{'pack_id':'native_array_content','layout':'resources'}}),encoding='utf-8')
            report=run_job(config);self.assertEqual(report['status'],'PACKAGED_REVIEW_REQUIRED',report)
            bundle=content_bundle(Path(report['output'])/'converted/original',report['discovered_entrypoints'])
            core=core_bundle();runtime=Package().load('core.source_modules').SourceModuleLoader(core['sources'])
            session=runtime.load('core.bundled_mods').BundledModSession(core['sources'],[bundle],runtime=runtime)
            try:
                result=session.loader.activate();self.assertTrue(result['native_menu_example']['ready'],result)
                state=session.loader.contexts['native_menu_example'].instance
                self.assertEqual((state.menu.containerId,state.menu.body,state.seen),(7,1,1))
                hooks=runtime.load('neoforge.mixin_hooks');self.assertEqual(hooks.MixinHooks.count(),1)
                session.close();self.assertEqual(hooks.MixinHooks.count(),0)
            finally:session.close();runtime.close()

    def test_multiple_empty_and_scalar_only_members_remain_blocked(self):
        replacements=[('@Mixin(value={Target.class})','@Mixin(value={})'),
            ('@Mixin(value={Target.class})','@Mixin(value={Target.class,Target.class})'),
            ('method={"run(I)I"}','method={}'),('method={"run(I)I"}','method={"run(I)I","touch(I)V"}'),
            ('at={@At(value="RETURN")}','at={}'),
            ('at={@At(value="RETURN")}','at={@At(value="HEAD"),@At(value="RETURN")}'),
            ('@At(value="RETURN")','@At(value={"RETURN"})')]
        for before,after in replacements:
            with self.subTest(after=after),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);files=base.fixture(root,base.ACTIVE[0]);array_hooks(root,files)
                path=root/'demo/Hooks.java';text=path.read_text(encoding='utf-8');self.assertIn(before,text)
                path.write_text(text.replace(before,after),encoding='utf-8')
                with self.assertRaises(MixinPlanError):plan(root)

    def test_refmap_identity_contexts_and_rejection_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'map.json';config={'refmap':'map.json'}
            identity={'mappings':{'demo/Hooks':{'run(I)I':'run(I)I'}},'data':{'named':{'demo/Hooks':{'field:I':'field:I'}}}}
            path.write_text(json.dumps(identity),encoding='utf-8')
            result=inspect_refmap(root,config,'config.json');self.assertEqual((result['mode'],result['mapping_count']),('identity_only',2))
            self.assertIsNotNone(result['sha256'])
            invalid=[{'mappings':{'demo/Hooks':{'run(I)I':'m_123(I)I'}}},
                {'data':{'searge':{'demo/Hooks':{'run(I)I':'m_123(I)I'}}}},
                {'mappings':[]},{'data':[]},{'mappings':{'demo/Hooks':{'x':3}}},{'unknown':True}]
            for value in invalid:
                path.write_text(json.dumps(value),encoding='utf-8')
                with self.assertRaises(MixinPlanError):inspect_refmap(root,config,'config.json')
            for raw in ('not json','{"mappings":{},"mappings":{}}'):
                path.write_text(raw,encoding='utf-8')
                with self.assertRaises(MixinPlanError):inspect_refmap(root,config,'config.json')
            for name in ('../map.json','/map.json','a\\map.json','a//map.json','a/./map.json','',True):
                with self.assertRaises(MixinPlanError):inspect_refmap(root,{'refmap':name},'config.json')

    def test_refmap_presence_and_bytes_invalidate_existing_weave_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'original';root.mkdir();files=base.fixture(root,base.ACTIVE[0]);array_hooks(root,files)
            report=translate(root,Path(tmp)/'out');self.assertEqual(report['manual_review'],0,report)
            out=Path(tmp)/'out/original';meta=out/'META-INF/neoforge.mods.toml';meta.parent.mkdir()
            meta.write_text('[[mods]]\nmodId="reviewed"\nversion="1"\n',encoding='utf-8')
            bundle=content_bundle(out,{'reviewed':'demo.Use:Use'})
            self.assertEqual(bundle['mods'][0]['source_mixin_adaptation']['reference_maps'][0]['mode'],'missing_passthrough')
            mapping=out/'absent.refmap.json';mapping.write_text('{"mappings":{}}',encoding='utf-8')
            with self.assertRaises(ValueError):content_bundle(out,{'reviewed':'demo.Use:Use'})
            mapping.unlink()
            (root/'absent.refmap.json').write_text('{}',encoding='utf-8')
            report=translate(root,Path(tmp)/'out2');self.assertEqual(report['manual_review'],0,report)
            second=Path(tmp)/'out2/original';metadata=second/'META-INF/neoforge.mods.toml';metadata.parent.mkdir()
            metadata.write_bytes(meta.read_bytes());content_bundle(second,{'reviewed':'demo.Use:Use'})
            (second/'absent.refmap.json').write_text('{}\n',encoding='utf-8')
            with self.assertRaises(ValueError):content_bundle(second,{'reviewed':'demo.Use:Use'})
            config=out/'demo.mixins.json';value=json.loads(config.read_bytes());value.pop('refmap');config.write_text(json.dumps(value),encoding='utf-8')
            # An implicit default resource also cannot be silently ignored.
            (out/'mixin.refmap.json').write_text('{"mappings":{"demo/Hooks":{"run":"other"}}}',encoding='utf-8')
            with self.assertRaises(ValueError):content_bundle(out,{'reviewed':'demo.Use:Use'})

    def test_missing_refmap_does_not_relax_method_or_runtime_target_identity(self):
        for before,after in [('run(I)I','missing(I)I'),('Target.class','java.lang.String.class')]:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);files=base.fixture(root,base.ACTIVE[0]);array_hooks(root,files)
                path=root/'demo/Hooks.java';path.write_text(path.read_text(encoding='utf-8').replace(before,after),encoding='utf-8')
                with self.assertRaises(MixinPlanError):plan(root)


if __name__=='__main__':unittest.main()
