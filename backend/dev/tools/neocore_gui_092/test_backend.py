import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer
from app import Workspace,make_handler
from cli import call,request,describe
from test_conversion import META


class BackendTests(unittest.TestCase):
    def test_text_client_uses_same_queue_auth_report_and_download_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);workspace=Workspace(root,{'dev_root':str(Path(__file__).resolve().parents[2])})
            server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(workspace,'test-secret'))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            url='http://127.0.0.1:'+str(server.server_port)+'/'
            (root/'当前窗口.json').write_text(json.dumps({'url':url,'pid':0,'token':'test-secret'}))
            try:
                with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(url+'api/state')
                jar=root/'original.jar'
                with zipfile.ZipFile(jar,'w') as z:z.writestr('META-INF/neoforge.mods.toml',META);z.writestr('x/Good.java','package x;public class Good {}')
                job=call(root,'api/import',jar.read_bytes(),{'X-Filename':'example.jar'})['job']
                key=job['id'];self.assertEqual(call(root,'api/job/'+key)['job']['sha256'],job['sha256'])
                self.assertIn(key,describe(call(root,'api/state')))
                with self.assertRaises(urllib.error.HTTPError) as error:call(root,'api/report/'+key)
                self.assertEqual(error.exception.code,409)
                attempt='a'*32;folder=workspace.runs/attempt;folder.mkdir();workspace.jobs[key]['attempt']=attempt
                (folder/'task_identity.json').write_text(json.dumps(dict(job_id=key,attempt=attempt,input_sha256=job['sha256'])))
                (folder/'result.json').write_text(json.dumps({'status':'BLOCKED'}))
                report_dir=folder/'jobs'/'one'/'converted';report_dir.mkdir(parents=True)
                (report_dir/'translation_report.json').write_text(json.dumps({'files':1,'results':[{'file':'x/Good.java','status':'GENERATED_REVIEW_REQUIRED'}]}))
                result=call(root,'api/report/'+key)
                self.assertEqual(result['source_reports'][0]['results'][0]['file'],'x/Good.java')
                with self.assertRaises(urllib.error.HTTPError):request(root,'download/'+key)
                workspace.jobs[key]['source_output']='old-attempt-source'
                workspace.run=lambda *args:None
                queued=workspace.export(key)
                self.assertNotIn('source_output',queued)
                self.assertNotIn('source_output',call(root,'api/job/'+key)['job'])
                run=subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('cli.py')),'--data-dir',str(root),'--json','status'],capture_output=True,text=True,encoding='utf-8',env=dict(os.environ,PYTHONIOENCODING='utf-8'))
                self.assertEqual(run.returncode,0,run.stderr)
                self.assertEqual(json.loads(run.stdout)['jobs'][0]['id'],key)
            finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
