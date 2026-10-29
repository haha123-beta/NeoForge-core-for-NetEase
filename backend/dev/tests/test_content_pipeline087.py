import os,sys,tempfile,json,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mod_content_pipeline import stage
from run_translation_job import run_job

class ContentPipeline087(unittest.TestCase):
    def test_independent_lanes_and_exact_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'input';root.mkdir()
            files={'Code.java':b'class Code {}','data/demo/recipe/a.json':b'{"type":"minecraft:crafting_shapeless"}','data/demo/tags/item/a.json':b'{"values":[]}', 'data/demo/loot_table/a.json':b'{}','data/demo/advancement/a.json':b'{}','data/demo/worldgen/a.json':b'{}','assets/demo/lang/en_us.json':b'{}','META-INF/neoforge.mods.toml':b'modLoader="javafml"','a.mixins.json':b'{"required":false}','META-INF/services/demo.Service':b'demo.Provider'}
            for name,raw in files.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            report=stage(root,Path(tmp)/'out')
            self.assertEqual(report['lanes']['data_json']['files'],5);self.assertTrue(all(v['files'] for v in report['lanes'].values()))
            for row in report['files']:
                if row['lane']=='java_code':self.assertNotIn('output',row);continue
                self.assertEqual((Path(tmp)/'out'/row['output']).read_bytes(),files[row['source']]);self.assertFalse(row['semantic_conversion'])
            self.assertFalse(report['engine_verified'])

    def test_invalid_json_localizes_without_deleting_other_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'input';(root/'data/demo/recipe').mkdir(parents=True)
            (root/'data/demo/recipe/bad.json').write_bytes(b'{bad')
            (root/'data/demo/recipe/good.json').write_bytes(b'{}')
            report=stage(root,Path(tmp)/'out');self.assertEqual(report['invalid_json_files'],1);self.assertEqual(report['preserved_files'],2)
            self.assertTrue(any(r.get('reason') and r['status']=='INVALID_JSON_PRESERVED' for r in report['files']))

    def test_non_java_job_is_content_not_empty_mod(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'input';(source/'data/demo/recipe').mkdir(parents=True);(source/'data/demo/recipe/a.json').write_text('{}')
            config=root/'job.json';config.write_text(json.dumps({'input':str(source),'output_root':str(root/'jobs')}))
            report=run_job(config)
            self.assertEqual(report['status'],'CONTENT_STAGED_REVIEW_REQUIRED',report)
            self.assertEqual(report['translation']['files'],0);self.assertEqual(report['content']['lanes']['data_json']['files'],1)
            self.assertFalse(report['engine_verified']);self.assertNotIn('distribution',report)

if __name__=='__main__':unittest.main()
