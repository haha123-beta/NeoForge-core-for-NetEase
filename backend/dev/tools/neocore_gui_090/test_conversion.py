import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer
from app import Workspace, make_handler
from conversion import convert, checked_entries

HERE=Path(__file__).resolve().parent
DEV=HERE.parents[1]
CONFIG={'dev_root':str(DEV)}
META='''modLoader="javafml"
loaderVersion="[1,)"
license="MIT"
[[mods]]
modId="gui_sample"
version="1.0"
displayName="GUI实际转换样例"
'''
MAIN='''package sample; import net.neoforged.fml.common.Mod;
@Mod("gui_sample") public class Main {public final int value; public Main(){this.value=Helper.compute(3);}}
'''
HELPER='package sample; public class Helper {public static int compute(int n){return n*7+2;}}'


def source_jar(path,main=MAIN,extras=None):
    with zipfile.ZipFile(path,'x') as z:
        for name,raw in {'META-INF/neoforge.mods.toml':META,'sample/Main.java':main,
                         'sample/Helper.java':HELPER,'assets/gui_sample/lang/en_us.json':'{"gui.sample":"示例"}',**(extras or {})}.items():
            z.writestr(name,raw)
    return path


def compiled_jar(folder):
    src=folder/'compile';src.mkdir();out=folder/'classes'
    files={'sample/Main.java':MAIN,'sample/Helper.java':HELPER,
           'net/neoforged/fml/common/Mod.java':'package net.neoforged.fml.common; import java.lang.annotation.*; @Retention(RetentionPolicy.RUNTIME) public @interface Mod {String value();}',
           'Probe.java':'public class Probe {public static void main(String[] args){System.out.print(sample.Helper.compute(3));}}'}
    for name,raw in files.items():
        p=src/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(raw,encoding='utf-8')
    java=Path(r'E:\Java\jdk-21.0.10\bin')
    subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-d',str(out)]+[str(src/n) for n in files],check=True,capture_output=True)
    value=subprocess.check_output([str(java/'java.exe'),'-cp',str(out),'Probe'],text=True)
    assert value=='23'
    jar=folder/'实际类文件.jar'
    with zipfile.ZipFile(jar,'x') as z:
        z.writestr('META-INF/neoforge.mods.toml',META)
        z.writestr('assets/gui_sample/lang/en_us.json','{"gui.sample":"示例"}')
        for p in (out/'sample').glob('*.class'):z.write(p,p.relative_to(out).as_posix())
    return jar


class ConversionTests(unittest.TestCase):
    def test_embedded_java_creates_real_resources_and_immutable_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);jar=source_jar(root/'source.jar');before=jar.read_bytes()
            result=convert(jar,root/'work',root/'out.zip',CONFIG)
            self.assertEqual(result['status'],'PACKAGED_REVIEW_REQUIRED',result)
            self.assertTrue(result['translated']);self.assertEqual(jar.read_bytes(),before)
            with zipfile.ZipFile(root/'out.zip') as z:
                names=z.namelist();path=next(n for n in names if n.endswith('/resources/sample/Helper.py'))
                self.assertNotIn(b'PLACEHOLDER',z.read(path));self.assertNotIn(b'FORMAT_PREVIEW_ONLY',z.read(path))
                self.assertFalse(any(n.endswith(('.java','.class','.jar')) for n in names))
                self.assertIn('behavior_pack_neocore/NeoCoreSourceScripts/source_snapshot.py',names)
                self.assertTrue(any(n.endswith('/entities/') for n in names))

    def test_compiled_jar_cfr_to_real_python_and_native_python2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);jar=compiled_jar(root)
            result=convert(jar,root/'work',root/'out.zip',CONFIG)
            self.assertEqual(result['status'],'PACKAGED_REVIEW_REQUIRED',result)
            self.assertEqual(result['source_mode'],'cfr');self.assertEqual(result['decompiled_files'],2)
            extracted=root/'extracted'
            with zipfile.ZipFile(root/'out.zip') as z:z.extractall(extracted)
            text=(DEV/'tests/test_content_registry.py').read_text(encoding='utf-8')
            fake=next(n for n in ast.parse(text).body if isinstance(n,ast.ClassDef) and n.name=='FakeEngine')
            data={'root':str(extracted),'fake_engine_source':ast.get_source_segment(text,fake)}
            (root/'probe.json').write_text(json.dumps(data),encoding='utf-8')
            p=subprocess.run([str(DEV.parent/'python27_validation/runtime/python.exe'),'-B',str(HERE/'probe_native_python27.py'),str(root/'probe.json')],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stdout+'\n'+p.stderr)
            proof=json.loads(p.stdout.splitlines()[-1]);self.assertEqual(len(proof['runs']),4)
            self.assertTrue(all(r['value']==23 and r['listeners_after_close']==0 for r in proof['runs']))

    def test_unsupported_java_has_file_diagnostics_and_review_only_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);jar=source_jar(root/'bad.jar',main=MAIN.replace('this.value=Helper.compute(3);','synchronized(this){this.value=Helper.compute(3);}'))
            result=convert(jar,root/'work',root/'out.zip',CONFIG)
            self.assertEqual(result['status'],'TRANSLATION_INCOMPLETE');self.assertTrue((root/'out.zip').exists())
            self.assertEqual(result['artifact_kind'],'SOURCE_REVIEW_ZIP');self.assertFalse(result['translated'])
            with zipfile.ZipFile(root/'out.zip') as z:
                self.assertFalse(json.loads(z.read('review_manifest.json'))['netease_pack'])
                self.assertFalse(any(n.startswith('behavior_pack') for n in z.namelist()))
            self.assertTrue(any(r.get('file')=='sample/Main.java' and r.get('reason') for r in result['diagnostics']),result)

    def test_nested_dependency_and_windows_aliases_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for i,extra in enumerate(({'META-INF/jarjar/dep.jar':b'jar'},{'a./bad.txt':'x'},{'a':'file','a/b.txt':'x'})):
                jar=source_jar(root/(str(i)+'.jar'),extras=extra)
                result=convert(jar,root/('w'+str(i)),root/(str(i)+'.zip'),CONFIG)
                self.assertEqual(result['status'],'BLOCKED',result);self.assertFalse((root/(str(i)+'.zip')).exists())

    def test_http_background_download_auth_restore_and_changed_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);jar=source_jar(root/'source.jar');workspace=Workspace(root/'data',CONFIG)
            server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(workspace,'test-token'))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            url='http://127.0.0.1:'+str(server.server_address[1])
            def request(path,data=None,token='test-token',headers=None):
                req=urllib.request.Request(url+path,data=data,headers={'X-NeoCore-Token':token,**(headers or {})})
                return urllib.request.urlopen(req,timeout=10)
            try:
                with self.assertRaises(urllib.error.HTTPError) as rejected:request('/api/state',token='wrong')
                rejected.exception.close()
                with request('/api/import',jar.read_bytes(),headers={'X-Filename':'sample.jar'}) as r:job=json.load(r)['job']
                with request('/api/export',json.dumps({'id':job['id']}).encode()) as r:
                    queued=json.load(r)['job'];self.assertIn(queued['status'],('QUEUED','RUNNING'))
                with self.assertRaises(urllib.error.HTTPError) as error:request('/api/shutdown',b'')
                self.assertEqual(error.exception.code,409);error.exception.close()
                start=time.monotonic()
                with request('/api/state') as r:json.load(r)
                self.assertLess(time.monotonic()-start,3)
                deadline=time.monotonic()+120
                while workspace.active() and time.monotonic()<deadline:time.sleep(.1)
                state=workspace.state()['jobs'][0];self.assertEqual(state['status'],'PACKAGED_REVIEW_REQUIRED',state)
                with self.assertRaises(urllib.error.HTTPError) as rejected:request('/download/'+job['id']+'?token=wrong')
                rejected.exception.close()
                with request('/download/'+job['id']+'?token=test-token') as r:raw=r.read()
                self.assertEqual(hashlib.sha256(raw).hexdigest(),state['output_sha256'])
                self.assertEqual(Workspace(root/'data',CONFIG).state()['jobs'][0]['output'],state['output'])
                (workspace.outputs/state['output']).write_bytes(b'changed')
                with self.assertRaises(urllib.error.HTTPError) as rejected:request('/download/'+job['id']+'?token=test-token')
                self.assertEqual(rejected.exception.code,409);rejected.exception.close()
                changed=Workspace(root/'data',CONFIG).state()['jobs'][0]
                self.assertEqual(changed['status'],'INTERRUPTED');self.assertNotIn('output',changed)
            finally:server.shutdown();server.server_close();thread.join()

    def test_running_recovery_becomes_interrupted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);jar=source_jar(root/'source.jar');workspace=Workspace(root/'data',CONFIG)
            job=workspace.add(jar,'source.jar');job.update(status='RUNNING');workspace.save(job)
            self.assertEqual(Workspace(root/'data',CONFIG).state()['jobs'][0]['status'],'INTERRUPTED')


if __name__=='__main__':unittest.main()
