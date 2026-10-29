import hashlib,json,tempfile,time,unittest,zipfile
from pathlib import Path
from app import Workspace
from conversion import convert
from cli import describe

HERE=Path(__file__).resolve().parent
CONFIG={'dev_root':str(HERE.parents[1])}
TOML='modLoader="javafml"\nloaderVersion="[1,)"\nlicense="MIT"\n[[mods]]\nmodId="data_sample"\nversion="1"\n'

def jar(path,fabric=False):
    files={'data/data_sample/recipe/a.json':b'{"type":"minecraft:crafting_shapeless","ingredients":[]}', 'data/data_sample/tags/item/a.json':b'{"values":[]}','assets/data_sample/lang/en_us.json':b'{}'}
    files.update({'fabric.mod.json':json.dumps({'schemaVersion':1,'id':'data_sample','version':'1'}).encode()} if fabric else {'META-INF/neoforge.mods.toml':TOML.encode()})
    with zipfile.ZipFile(path,'w') as archive:
        for name,raw in files.items():archive.writestr(name,raw)
    return files

class DataContent087(unittest.TestCase):
    def test_java_free_jar_survives_import_conversion_without_fake_engine_zip(self):
        for fabric in (False,True):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);source=root/'input.jar';files=jar(source,fabric);before=hashlib.sha256(source.read_bytes()).hexdigest()
                report=convert(source,root/'work',root/'output.zip',CONFIG)
                self.assertEqual(report['status'],'CONTENT_STAGED_REVIEW_REQUIRED',report);self.assertEqual(report['source_mode'],'non_java_content');self.assertFalse(report['translated']);self.assertFalse(report['engine_verified']);self.assertTrue((root/'output.zip').exists());self.assertEqual(report['artifact_kind'],'SOURCE_REVIEW_ZIP')
                content=report['content'];self.assertEqual(content['lanes']['data_json']['files'],2);self.assertEqual(content['preserved_files'],len(files));self.assertFalse(content['semantic_conversion'])
                path=Path(content['manifest']);manifest=json.loads(path.read_bytes())
                for row in manifest['files']:self.assertEqual((path.parent/row['output']).read_bytes(),files[row['source']])
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)

    def test_worker_and_text_interface_expose_non_java_counts_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'input.jar';jar(source);workspace=Workspace(root/'state',CONFIG)
            job=workspace.add(source,'input.jar');workspace.export(job['id']);deadline=time.monotonic()+60
            while workspace.active() and time.monotonic()<deadline:time.sleep(.1)
            result=workspace.state()['jobs'][0];self.assertEqual(result['status'],'CONTENT_STAGED_REVIEW_REQUIRED',result)
            text=describe({'job':result});self.assertIn('data JSON 2',text);self.assertIn('无 Java 文件',text);self.assertNotIn('0/0',text);self.assertIn('内容清单',text)
            restored=Workspace(root/'state',CONFIG).state()['jobs'][0];self.assertEqual(restored['content'],result['content']);self.assertTrue(restored['content_staged']);self.assertEqual(restored['artifact_kind'],'SOURCE_REVIEW_ZIP')

if __name__=='__main__':unittest.main()
