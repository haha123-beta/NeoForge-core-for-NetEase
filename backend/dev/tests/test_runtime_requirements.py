import ast,copy,json,os,sys,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from build_source_bundle import core_bundle
from test_content_registry import FakeEngine
pkg=Package();requirements=pkg.load('core.runtime_requirements')

def bundle(mod_id='sample',source='def start(context):\n    return {"started": True}\n',helpers=None,api_types=None):
    name=mod_id+'.Main';sources={name:{'source':source,'is_package':False}}
    manifest={'schema_version':1,'evidence_scope':'api_type_presence_and_helper_abi',
        'modules':{name:{'code_sha256':requirements.code_digest(source),
            'required_api_types':api_types or ['java.lang.String'],
            'required_runtime_helpers':helpers or []}}}
    return {'schema_version':1,'kind':'neocore_content_sources','sources':sources,
        'mods':[{'mod_id':mod_id,'entrypoint':name+':start'}],'runtime_requirements':manifest}

class RuntimeRequirementsTests(unittest.TestCase):
    def api(self):return pkg.load('core.java_api').collect_java_api()
    def check(self,item):return requirements.inspect_requirements(item.get('runtime_requirements'),item['sources'],self.api())
    def test_actual_helpers_and_nested_type_aliases_are_checked(self):
        item=bundle(helpers=['neocore.runtime.Profilers@1','neocore.runtime.Functional@4'],api_types=['net.minecraft.world.entity.ai.goal.Goal.Flag'])
        result=self.check(item);self.assertEqual(result['status'],'requirements_satisfied');self.assertEqual(result['checked_modules'],['sample.Main'])
        self.assertEqual(result['evidence_scope'],'api_type_presence_and_helper_abi')
    def test_future_helper_and_unmapped_type_are_reported_without_import(self):
        item=bundle(helpers=['neocore.runtime.Profilers@2'],api_types=['net.minecraft.NotMapped'])
        result=self.check(item);self.assertEqual(result['status'],'blocked')
        self.assertEqual({row['category'] for row in result['issues']},{'helper_abi','missing_api_type'})
    def test_changed_code_and_missing_module_are_not_ignored(self):
        item=bundle();item['sources']['sample.Main']['source']+='x=1\n'
        self.assertEqual(self.check(item)['issues'][0]['category'],'source_changed')
        item['sources']={};self.assertIn('missing_source',[row['category'] for row in self.check(item)['issues']])
    def test_malformed_declarations_block_one_bundle(self):
        for value in (None,[],{'schema_version':True},{'schema_version':1.0}):
            item=bundle();item['runtime_requirements']=value
            if value is None:self.assertEqual(self.check(item)['status'],'not_declared')
            else:self.assertEqual(self.check(item)['issues'][0]['category'],'invalid_manifest')
        for token in ('neocore.runtime.Profilers@0','neocore.runtime.Profilers@-1','not.helper@1','neocore.runtime.Profilers@'+'9'*200):
            item=bundle(helpers=[token]);self.assertEqual(self.check(item)['issues'][0]['category'],'invalid_manifest')
    def test_legacy_and_untracked_sources_are_explicit(self):
        item=bundle();item.pop('runtime_requirements');self.assertEqual(self.check(item)['status'],'not_declared')
        item=bundle();item['sources']['native.helper']={'source':'x=1\n','is_package':False}
        result=self.check(item);self.assertEqual(result['untracked_modules'],['native.helper'])
    def test_bad_bundle_never_executes_and_other_pack_is_ready(self):
        bad=bundle('badpack','raise RuntimeError("must not import")\n',helpers=['neocore.runtime.Profilers@99'])
        good=bundle('goodpack');dependent=bundle('dependent','raise RuntimeError("must not import dependent")\n')
        dependent['mods'][0]['requires']=['badpack']
        session=pkg.load('core.bundled_mods').BundledModSession(core_bundle()['sources'],[bad,good,dependent])
        try:
            result=session.loader.activate();self.assertEqual(result['badpack']['phase'],'runtime_requirements')
            self.assertEqual(result['dependent']['state'],'blocked');self.assertTrue(result['goodpack']['ready'])
            self.assertNotIn('badpack.Main',session.runtime.modules);self.assertNotIn('dependent.Main',session.runtime.modules)
            self.assertNotIn('badpack',session.loader.contexts)
            self.assertTrue(session.loader.contexts['goodpack'].instance['started'])
            session.close();self.assertEqual(session.loader.results['goodpack']['state'],'unloaded')
        finally:session.close()
    def test_malformed_missing_source_does_not_abort_healthy_pack(self):
        bad=bundle('badpack');bad['runtime_requirements']['modules']={'badpack.Missing':{}}
        session=pkg.load('core.bundled_mods').BundledModSession(core_bundle()['sources'],[bad,bundle('goodpack')])
        try:
            result=session.loader.activate();self.assertEqual(result['badpack']['phase'],'runtime_requirements');self.assertTrue(result['goodpack']['ready'])
        finally:session.close()
    def test_requirement_success_does_not_satisfy_neoforge_dependency(self):
        item=bundle();item['mods'][0]['dependency_constraints']=[{'modId':'neoforge','versionRange':'[21.1.233,21.2)','type':'required'}]
        session=pkg.load('core.bundled_mods').BundledModSession(core_bundle()['sources'],[item])
        try:
            result=session.loader.activate()['sample'];self.assertEqual(result['phase'],'dependencies')
            self.assertEqual(result['runtime_requirements']['status'],'requirements_satisfied')
            self.assertIn('neoforge',result['message']);self.assertNotIn('sample.Main',session.runtime.modules)
        finally:session.close()
    def test_manifest_is_not_modified_by_validation(self):
        item=bundle();before=copy.deepcopy(item);self.check(item);self.assertEqual(item,before)
    def test_rejected_sources_cannot_execute_via_another_pack_import(self):
        bad=bundle('badpack','raise RuntimeError("rejected source executed")\n',helpers=['neocore.runtime.Profilers@99'])
        importer=bundle('importer','from badpack import Main\ndef start(context):\n    return Main\n')
        core=core_bundle()['sources']
        runtime=pkg.load('core.source_modules').SourceModuleLoader(core)
        session=pkg.load('core.bundled_mods').BundledModSession(core,[bad,importer,bundle('healthy')],runtime=runtime)
        try:
            result=session.loader.activate()
            self.assertEqual(result['badpack']['phase'],'runtime_requirements')
            self.assertEqual(result['importer']['state'],'failed')
            self.assertIn('blocked before import',result['importer']['message'])
            self.assertTrue(result['healthy']['ready'])
            self.assertNotIn('badpack.Main',runtime.modules)
            with self.assertRaisesRegex(ImportError,'blocked before import'):runtime.load('badpack.Main')
        finally:session.close()
        self.assertEqual(runtime._blocked_sources,{})
        self.assertFalse(runtime.closed)
        # A later session may register a repaired version under the same original name.
        replacement=pkg.load('core.bundled_mods').BundledModSession(core,[bundle('badpack')],runtime=runtime)
        try:self.assertTrue(replacement.loader.activate()['badpack']['ready'])
        finally:replacement.close();runtime.close()
    def test_native_core_namespace_initializers_cannot_run_during_api_install(self):
        for name in ('java','net','net.minecraft','net.neoforged','com','com.mojang','it','it.unimi','neocore','neocore.runtime'):
            item=bundle();item['sources'][name]={'source':'raise RuntimeError("namespace executed")\n','is_package':True}
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'shadows Java compatibility API'):
                pkg.load('core.bundled_mods').BundledModSession(core_bundle()['sources'],[item])
    def test_thin_provider_rejects_old_core_before_registration(self):
        from workspace_paths import DEV_ROOT
        tree=ast.parse((DEV_ROOT/'templates/source_content_modMain.py').read_text(encoding='utf-8'))
        function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='register_provider')
        for version in (0,1):
            engine=FakeEngine();calls=[]
            class Core:
                RUNTIME_REQUIREMENTS_PROTOCOL=version
                def RegisterContent(self,*args):calls.append(args);return {'accepted':True}
            engine.systems[('NeoCore','Loader')]=Core()
            namespace={'BUNDLE':bundle(),'PACK_ID':'example_pack','SCRIPT_PACKAGE':'exampleScripts','NAMESPACE':'example_pack'}
            exec(compile(ast.Module(body=[function],type_ignores=[]),'actual_content_provider','exec'),namespace)
            def register(ns,name,path):return namespace[name](ns,name)
            engine.RegisterSystem=register
            provider=namespace['register_provider'](engine,'SERVER')
            engine.emit('NeoCore','Loader','NeoCoreCollectContent',{})
            self.assertEqual(len(calls),version)
            provider.Destroy();self.assertEqual(engine.listeners,[])

if __name__=='__main__':unittest.main()
