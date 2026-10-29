import copy,hashlib,json,os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from workspace_paths import DEV_ROOT
from run_translation_job import run_job
from build_source_bundle import core_bundle,content_bundle

class RequirementBuildTests(unittest.TestCase):
    def job(self,folder,source=None):
        original=folder/'original';original.mkdir()
        (original/'META-INF').mkdir();(original/'META-INF/neoforge.mods.toml').write_text('modLoader="javafml"\nloaderVersion="[4,)"\n[[mods]]\nmodId="runtime_test"\nversion="1"\n',encoding='utf-8')
        (original/'Main.java').write_text(source or 'import net.neoforged.fml.common.Mod;@Mod("runtime_test") public class Main {public Main(){}}',encoding='utf-8')
        config=folder/'job.json';config.write_text(json.dumps({'input':str(original),'output_root':str(folder/'out'),'distribution':{'pack_id':'runtime_test_content'}}),encoding='utf-8')
        return original,config
    def test_generated_requirements_bind_code_helpers_and_mechanical_wrapper(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);original,config=self.job(root)
            before={str(p.relative_to(original)):hashlib.sha256(p.read_bytes()).hexdigest() for p in original.rglob('*') if p.is_file()}
            report=run_job(config);self.assertEqual(report['status'],'PACKAGED_REVIEW_REQUIRED',report)
            converted=Path(report['output'])/'converted/original'
            manifest=json.loads((converted/'_nc_runtime_requirements.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['evidence_scope'],'api_type_presence_and_helper_abi')
            self.assertIn('Main',manifest['modules']);self.assertEqual(len(manifest['modules']),2)
            self.assertIn('neocore.runtime.ModEntrypoints@1',manifest['modules']['Main']['required_runtime_helpers'])
            item=content_bundle(converted,report['discovered_entrypoints'])
            self.assertEqual(item['runtime_requirements'],manifest)
            pkg=Package();session=pkg.load('core.bundled_mods').BundledModSession(core_bundle()['sources'],[item])
            try:
                result=session.loader.activate()['runtime_test'];self.assertTrue(result['ready'])
                self.assertEqual(result['runtime_requirements']['status'],'requirements_satisfied')
                self.assertEqual(result['runtime_requirements']['untracked_modules'],[])
            finally:session.close()
            self.assertEqual(before,{str(p.relative_to(original)):hashlib.sha256(p.read_bytes()).hexdigest() for p in original.rglob('*') if p.is_file()})
    def test_modified_generated_file_cannot_be_repackaged_under_old_requirements(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);original,config=self.job(root);report=run_job(config)
            converted=Path(report['output'])/'converted/original'
            path=converted/'Main.py';path.write_text(path.read_text(encoding='utf-8')+'\nchanged=1\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'stale generated runtime requirements'):content_bundle(converted,report['discovered_entrypoints'])
    def test_original_manifest_filename_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);original,config=self.job(root)
            file=original/'_nc_runtime_requirements.json';file.write_text('{"original":true}',encoding='utf-8');before=file.read_bytes()
            report=run_job(config);self.assertEqual(report['status'],'FAILED');self.assertIn('conflict with an original file',report['error'])
            self.assertEqual(file.read_bytes(),before)
            self.assertEqual((Path(report['output'])/'converted/original/_nc_runtime_requirements.json').read_bytes(),before)
    def test_native_extra_source_remains_explicitly_untracked(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);original,config=self.job(root)
            (original/'Native.py').write_text('def original_helper():\n    return 3\n',encoding='utf-8')
            report=run_job(config);self.assertEqual(report['status'],'PACKAGED_REVIEW_REQUIRED')
            self.assertEqual(report['runtime_requirements']['untracked_modules'],['Native'])

if __name__=='__main__':unittest.main()
