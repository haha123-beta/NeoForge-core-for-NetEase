import json,sys,tempfile,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from java_frontend import isolated_parse,api_index
from java_parser_worker import ParserWorker
WORKER=Path(__file__).resolve().parents[1]/'java_parser_worker.py'

class WorkerTests(unittest.TestCase):
    def test_real_ir_equivalence_context_isolation_and_recycling(self):
        known,_=api_index();source=b'import java.lang.String;class A {String value="x";}'
        with ParserWorker('a'*64,batch_limit=2,worker_script=WORKER) as worker:
            a=worker.parse(source,'A.java',known);pid=worker.process.pid
            self.assertEqual(a,isolated_parse(source,'A.java',known))
            b=worker.parse(source,'Other.java',[]);self.assertEqual(worker.process.pid,pid);self.assertFalse(b['known_api_types'])
            self.assertEqual(b,isolated_parse(source,'Other.java',[]))
            c=worker.parse(b'class Last {}','Last.java',known);self.assertNotEqual(worker.process.pid,pid);self.assertEqual(c['origin'],'Last.java')
    def test_timeout_bad_reply_and_crash_reap_worker(self):
        for body in ('import time;time.sleep(20)','print("{}",flush=True)','raise SystemExit(7)'):
            with self.subTest(body=body),tempfile.TemporaryDirectory() as tmp:
                script=Path(tmp)/'worker.py';script.write_text(body)
                with ParserWorker('b'*64,timeout=.5,worker_script=script) as worker:
                    with self.assertRaises((RuntimeError,ValueError)):worker.parse(b'class A{}','A.java',[])
                    self.assertIsNone(worker.process)
    def test_source_error_followed_by_clean_request(self):
        with ParserWorker('c'*64,worker_script=WORKER) as worker:
            with self.assertRaises(RuntimeError):worker.parse(b'\xff','Bad.java',[])
            self.assertIsNone(worker.process)
            self.assertEqual(worker.parse(b'class Fine {}','Fine.java',[])['parse_status'],'PARSED')

if __name__=='__main__':unittest.main()
