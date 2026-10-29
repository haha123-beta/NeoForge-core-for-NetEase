import ast,copy,hashlib,json,sys,tempfile,unittest,zipfile
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]
from run_translation_job import run_job
from build_distribution import build,write_pack_archive
from build_source_bundle import core_bundle,content_bundle
from harness import Package
from test_content_registry import FakeEngine


def read_resource(path):
    tree=ast.parse(Path(path).read_text(encoding='utf-8'))
    value=next(node.value for node in tree.body if isinstance(node,ast.Assign)
        and any(isinstance(target,ast.Name) and target.id=='RESOURCE' for target in node.targets))
    return json.loads(ast.literal_eval(value.args[0]))


def prepare(root):
    dev=Path(__file__).resolve().parents[1];contents=[];jobs=[]
    for suffix in ('alpha','beta'):
        config=Path(root)/(suffix+'.json')
        config.write_text(json.dumps({'input':str(dev/('examples/runtime_resources_'+suffix)),
            'output_root':str(Path(root)/'jobs'),'distribution':{'pack_id':'resources_'+suffix,
            'layout':'resources'}}),encoding='utf-8')
        job=run_job(config)
        if job['status']!='PACKAGED_REVIEW_REQUIRED':raise AssertionError(job)
        jobs.append(job)
        contents.append({'pack_id':'resources_'+suffix,
            'folder':str(Path(job['output'])/'converted'/('runtime_resources_'+suffix)),
            'entrypoints':job['discovered_entrypoints']})
    output=Path(root)/'combined';report=build(output,contents,layout='resources')
    resources=[read_resource(output/('behavior_pack-'+row['pack_id'])/(row['pack_id']+'Scripts')/'resources/_nc_resources.py') for row in contents]
    return output,resources,jobs,report


class ResourcesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.output,cls.resources,cls.jobs,cls.report=prepare(Path(cls.temp.name))
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def host(self,side='CLIENT'):
        engine,exports=FakeEngine(),{}
        def register(namespace,name,path):
            instance=exports[path.rsplit('.',1)[-1]](namespace,name)
            engine.systems[(namespace,name)]=instance
            return instance
        engine.RegisterSystem=register
        host=Package().load('core.runtime_host').SourceRuntimeHost(core_bundle(),engine,side,exports,'NeoCoreSourceScripts')
        return host,engine,engine.GetSystem('NeoCore','Loader')
    def test_real_translation_physical_resources_and_preserved_assets(self):
        self.assertEqual(self.report['content_layout'],'resources')
        for payload in self.resources:
            pack=self.output/('behavior_pack-'+payload['pack_id']);scripts=pack/payload['script_package']
            self.assertTrue((pack/'entities').is_dir());self.assertFalse((scripts/'source_snapshot.py').exists())
            self.assertEqual((scripts/'resources/__init__.py').read_bytes(),b'')
            for name,row in payload['source_index'].items():
                path=pack/row['path'];self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),row['file_sha256'])
                self.assertNotIn('PLACEHOLDER_NOT_TRANSLATED',path.read_text(encoding='utf-8'))
            self.assertTrue((scripts/'resources/META-INF/neoforge.mods.toml').exists())
            suffix=payload['pack_id'].split('_')[-1]
            asset=scripts/('resources/assets/resources_'+suffix+'/lang/en_us.json')
            original=Path(__file__).resolve().parents[1]/('examples/runtime_resources_'+suffix)/('assets/resources_'+suffix+'/lang/en_us.json')
            self.assertEqual(asset.read_bytes(),original.read_bytes())
            archive=Path(self.temp.name)/(payload['pack_id']+'.zip')
            write_pack_archive(pack,archive)
            with zipfile.ZipFile(archive) as zipped:
                self.assertIsNone(zipped.testzip())
                for entry in zipped.infolist():
                    if not entry.file_size:self.assertEqual((entry.compress_type,entry.compress_size),(zipfile.ZIP_STORED,0))
    def test_invalid_payloads_rejected_before_any_content_import(self):
        host,engine,core=self.host()
        try:
            base=self.resources[0];name=next(iter(base['source_index']))
            mutations=[lambda x:x.update(schema_version=True),lambda x:x.update(format_preview_only=True),
                lambda x:x.update(pack_id='other'),lambda x:x.update(script_package='NeoCoreSourceScripts'),
                lambda x:x['source_index'][name].update(path='../escape.py'),
                lambda x:x['source_index'][name].update(text_sha256='0'*64),
                lambda x:x['bundle'].pop('runtime_requirements'),
                lambda x:x['bundle']['mods'][0].update(entrypoint='missing.Module:run')]
            for mutate in mutations:
                payload=copy.deepcopy(base);mutate(payload)
                self.assertFalse(core.RegisterResourceContent(base['pack_id'],payload)['accepted'])
            self.assertEqual(core.GetContentReport()['packs'],[])
            self.assertFalse(any(name.startswith('common.') for name in host.runtime.modules))
        finally:host.close()
        self.assertEqual(engine.listeners,[])
    def test_original_names_dependency_order_ticks_and_cleanup(self):
        host,engine,core=self.host()
        try:
            for payload in reversed(self.resources):self.assertTrue(core.RegisterResourceContent(payload['pack_id'],payload)['accepted'])
            engine.emit('Minecraft','Engine','LoadClientAddonScriptsAfter',{})
            loader=core.registry._session.loader
            self.assertEqual(loader.order,['resources_alpha','resources_beta'])
            self.assertTrue(all(r['ready'] for r in loader.results.values()))
            self.assertEqual([loader.contexts['resources_'+s].instance.initial for s in ('alpha','beta')],[23,14])
            self.assertIsNot(host.runtime.load('common.alpha.Main').Main,host.runtime.load('common.beta.Main').Main)
            for unused in range(150):engine.emit('Minecraft','Engine','OnScriptTickClient',{})
            self.assertEqual([loader.contexts['resources_'+s].instance.total for s in ('alpha','beta')],[0,0])
            host.close();self.assertTrue(all(r['state']=='unloaded' for r in loader.results.values()))
        finally:host.close()
        self.assertEqual(engine.listeners,[])
    def test_missing_required_dependency_remains_blocked(self):
        host,engine,core=self.host()
        try:
            payload=self.resources[1];self.assertTrue(core.RegisterResourceContent(payload['pack_id'],payload)['accepted'])
            engine.emit('Minecraft','Engine','LoadClientAddonScriptsAfter',{})
            result=core.GetContentReport()['mods']['resources_beta']
            self.assertFalse(result.get('ready'));self.assertNotIn('common.beta.Main',host.runtime.modules)
        finally:host.close()
    def test_exact_module_collision_fails_instead_of_cross_pack_override(self):
        host,engine,core=self.host()
        try:
            first=self.resources[0];second=copy.deepcopy(first)
            second.update(pack_id='resources_duplicate',script_package='resources_duplicateScripts',resource_root='resources_duplicateScripts/resources')
            for row in second['source_index'].values():row['path']=row['path'].replace(first['script_package'],'resources_duplicateScripts',1)
            second['bundle']['mods'][0]['mod_id']='resources_duplicate'
            self.assertTrue(core.RegisterResourceContent(first['pack_id'],first)['accepted'])
            self.assertTrue(core.RegisterResourceContent(second['pack_id'],second)['accepted'])
            engine.emit('Minecraft','Engine','LoadClientAddonScriptsAfter',{})
            self.assertEqual(core.GetContentReport()['state'],'failed')
            self.assertFalse(any(name.startswith('common.') for name in host.runtime.modules))
        finally:host.close()
    def test_resources_and_old_protocol_two_content_can_share_the_core(self):
        host,engine,core=self.host()
        try:
            for payload in self.resources:self.assertTrue(core.RegisterResourceContent(payload['pack_id'],payload)['accepted'])
            legacy=Path(__file__).resolve().parents[1]/'examples/multi_mod/neocore_example_base'
            bundle=content_bundle(legacy,{'neocore_example_base':'example.neocore_example_base.Main:start'})
            self.assertTrue(core.RegisterContent('old_content',2,[{'bundle':bundle}])['accepted'])
            engine.emit('Minecraft','Engine','LoadClientAddonScriptsAfter',{})
            self.assertEqual(len(core.GetContentReport()['mods']),3)
            self.assertTrue(all(r.get('ready') for r in core.GetContentReport()['mods'].values()))
        finally:host.close()
        self.assertEqual(engine.listeners,[])


if __name__=='__main__':unittest.main()
