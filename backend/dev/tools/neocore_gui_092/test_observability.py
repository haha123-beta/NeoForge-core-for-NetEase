import io,json,os,subprocess,sys,tempfile,threading,time,unittest,zipfile
from pathlib import Path
from process_control import OwnedProcess,Cancelled,TimedOut
from diagnostic_export import archive,snapshot
from app import Workspace,make_handler
from http.server import ThreadingHTTPServer
import urllib.request,urllib.error
import test_conversion as fixtures
from decompiler_evidence import register,recover,release_parser_caches

class Observability092(unittest.TestCase):
    def test_owned_decompiler_partial_recovery_and_cleanup_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt='b'*32;work=Path(tmp)/attempt;work.mkdir()
            external=Path(tempfile.mkdtemp(prefix='neocore092_'+attempt+'_'))
            register(work,external,'source-hash');out=external/'out/demo';out.mkdir(parents=True);(out/'Partial.java').write_text('class Partial {}')
            result=recover(work,attempt,'source-hash');self.assertFalse(external.exists())
            self.assertEqual(result['files'],['demo/Partial.java']);self.assertTrue((work/'decompile_partial/demo/Partial.java').exists())
            wrong=Path(tmp)/'private';wrong.mkdir();(wrong/'keep.txt').write_text('keep')
            (work/'external_workspace.json').write_text(json.dumps(dict(attempt=attempt,input_sha256='source-hash',path=str(wrong))))
            with self.assertRaises(ValueError):recover(work,attempt,'source-hash')
            self.assertTrue((wrong/'keep.txt').exists())
            cache=work/'.parser_ir_cache_test';cache.mkdir();(cache/'data.json').write_text('{}')
            self.assertEqual(release_parser_caches(work),['.parser_ir_cache_test']);self.assertFalse(cache.exists())
    def test_owned_process_timeout_and_cancel_reap_descendants(self):
        for cancel in (False,True):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);pid=root/'child.pid';log=(root/'log').open('wb')
                script=root/'worker.py';script.write_text('import subprocess,sys,time\nfrom pathlib import Path\np=subprocess.Popen([sys.executable,"-c","import time;time.sleep(120)"])\nready=Path(sys.argv[1]);pending=ready.with_suffix(".tmp")\npending.write_text(str(p.pid));pending.replace(ready)\ntime.sleep(120)\n')
                process=None
                try:
                    process=OwnedProcess([sys.executable,str(script),str(pid)],log)
                    deadline=time.monotonic()+10
                    while not pid.exists():
                        self.assertIsNone(process.process.poll(),'Worker exited before child readiness')
                        self.assertLess(time.monotonic(),deadline,'Worker did not publish child readiness')
                        time.sleep(.01)
                    metrics=[process.resource_snapshot()]
                    start=time.monotonic()
                    with self.assertRaises(Cancelled if cancel else TimedOut):
                        process.wait(1 if not cancel else 10,cancel=lambda:cancel and pid.exists(),tick=lambda:metrics.append(process.resource_snapshot()))
                finally:
                    if process is not None:process.close()
                    log.close()
                self.assertLess(time.monotonic()-start,15);self.assertIsNotNone(process.process.poll())
                self.assertTrue(pid.exists())
                if os.name=='nt':
                    self.assertTrue(metrics);self.assertIn('cpu_tree_seconds',metrics[-1]);self.assertGreaterEqual(metrics[-1]['cpu_tree_seconds'],0)
                if os.name=='nt':
                    import ctypes
                    from ctypes import wintypes as w
                    k=ctypes.WinDLL('kernel32');k.OpenProcess.restype=w.HANDLE;k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.CloseHandle.argtypes=[w.HANDLE]
                    h=k.OpenProcess(0x1000,False,int(pid.read_text()))
                    if h:
                        code=w.DWORD();k.GetExitCodeProcess.argtypes=[w.HANDLE,ctypes.POINTER(w.DWORD)];k.GetExitCodeProcess(h,ctypes.byref(code));k.CloseHandle(h)
                        self.assertNotEqual(code.value,259,'Descendant survived cancellation')
                # Process exit and Windows file rundown need not be simultaneous.
                # Verify actual release, bounded; never ignore a locked log.
                deadline=time.monotonic()+2
                while True:
                    try:(root/'log').unlink();break
                    except PermissionError:
                        if time.monotonic()>=deadline:raise
                        time.sleep(.01)
    def test_all_terminal_states_export_without_python_and_exclude_credentials(self):
        for state in ('FAILED','TIMED_OUT','CANCELLED','TRANSLATION_INCOMPLETE','BLOCKED'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);folder=root/'attempt';folder.mkdir()
                (folder/'request.json').write_text('{"token":"DO_NOT_EXPORT"}')
                (folder/'unrelated.txt').write_text('PRIVATE')
                (folder/'worker.log').write_text('worker failed api_key=PRIVATE_SECRET')
                (folder/'result.json').write_text(json.dumps({'status':state,'token':'PRIVATE_TOKEN','nested':{'authorization':'PRIVATE_AUTH'}}))
                (folder/'events.jsonl').write_text('{"phase":"parse","elapsed_seconds":2,"metrics":{}}\n{"partial":')
                job=dict(id='job',attempt='attempt',sha256='hash',status=state)
                path=root/'out.zip';report=archive(folder,job,path)
                self.assertEqual(report['status'],state)
                with zipfile.ZipFile(path) as z:
                    self.assertNotIn('request.json',str(z.namelist()));self.assertNotIn(b'DO_NOT_EXPORT',b''.join(z.read(n) for n in z.namelist()))
                    self.assertNotIn(b'PRIVATE_',b''.join(z.read(n) for n in z.namelist()))
                    self.assertEqual(json.loads(z.read('diagnostic_report.json'))['job_id'],'job')
                self.assertTrue(report['incomplete_evidence'])
                with self.assertRaises(ValueError):snapshot(folder,dict(job,attempt='other'))

    def test_http_cancel_export_restore_and_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);jar=fixtures.source_jar(root/'test.jar');ws=Workspace(root/'workspace',fixtures.CONFIG)
            key=ws.add(jar,'test.jar')['id']
            server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(ws,'test-token'))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def request(route,data=None,auth=True):
                r=urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+route,data=data,headers={'X-NeoCore-Token':'test-token'} if auth else {})
                with urllib.request.urlopen(r,timeout=30) as response:return response.read()
            try:
                request('/api/export',json.dumps({'id':key}).encode())
                request('/api/cancel',json.dumps({'id':key}).encode())
                deadline=time.monotonic()+15
                while ws.active() and time.monotonic()<deadline:time.sleep(.05)
                self.assertFalse(ws.active());self.assertEqual(ws.jobs[key]['status'],'CANCELLED')
                report=json.loads(request('/api/diagnostic/'+key));self.assertEqual(report['job_id'],key)
                raw=request('/diagnostic-download/'+key)
                with zipfile.ZipFile(io.BytesIO(raw)) as z:self.assertEqual(json.loads(z.read('diagnostic_report.json'))['status'],'CANCELLED')
                try:request('/diagnostic-download/'+key,auth=False)
                except urllib.error.HTTPError as e:self.assertEqual(e.code,403);e.close()
                else:self.fail('Unauthenticated download was allowed')
                restored=Workspace(ws.root,fixtures.CONFIG);self.assertEqual(restored.jobs[key]['status'],'CANCELLED')
                folder=ws.runs/ws.jobs[key]['attempt'];identity=json.loads((folder/'task_identity.json').read_bytes())
                identity['job_id']='other';(folder/'task_identity.json').write_text(json.dumps(identity))
                with self.assertRaises(ValueError):ws.diagnostic(key)
            finally:server.shutdown();server.server_close();thread.join()

    def test_event_cursor_recovers_partial_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);jar=fixtures.source_jar(root/'test.jar');ws=Workspace(root/'workspace',fixtures.CONFIG);key=ws.add(jar,'test.jar')['id']
            attempt='a'*32;folder=ws.runs/attempt;folder.mkdir();ws.jobs[key].update(attempt=attempt,status='RUNNING')
            (folder/'task_identity.json').write_text(json.dumps(dict(job_id=key,attempt=attempt,input_sha256=ws.jobs[key]['sha256'])))
            p=folder/'events.jsonl';p.write_bytes(b'{"sequence":1}\n{"sequence":2')
            first=ws.events(key);self.assertEqual(first['events'],[{'sequence':1}])
            with p.open('ab') as f:f.write(b'}\n')
            second=ws.events(key,first['cursor']);self.assertEqual(second['events'],[{'sequence':2}])

if __name__=='__main__':unittest.main()
