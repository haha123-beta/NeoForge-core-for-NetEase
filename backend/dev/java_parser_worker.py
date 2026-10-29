"""Bounded sequential parser service; no shared CST/type environment between requests.

The supervising process owns timeouts, input/reply identity and worker recycling.
Only pipe I/O uses threads; Java files are never parsed in parallel here.
"""
import base64,hashlib,json,os,queue,subprocess,sys,tempfile,threading,time
from pathlib import Path

class ParserWorker:
    def __init__(self,context_sha256,batch_limit=32,timeout=30,worker_script=None):
        self.context=context_sha256;self.batch_limit=batch_limit;self.timeout=timeout
        self.script=Path(worker_script or __file__).resolve();self.process=None;self.count=0;self.sequence=0
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def start(self):
        self.replies=queue.Queue(maxsize=2);self.stderr=tempfile.TemporaryFile();self.reader_stop=threading.Event()
        try:
            self.process=subprocess.Popen([sys.executable,'-X','faulthandler','-B',str(self.script),'--worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except BaseException:self.stderr.close();raise
        self.count=0
        stream=self.process.stdout;replies=self.replies;stop=self.reader_stop
        def deliver(value):
            while not stop.is_set():
                try:replies.put(value,timeout=.1);return
                except queue.Full:pass
        def reader():
            try:
                while True:
                    raw=stream.readline()
                    if not raw:deliver(None);return
                    deliver(raw)
                    if stop.is_set():return
            except (OSError,ValueError):
                try:replies.put_nowait(None)
                except queue.Full:pass
        self.reader=threading.Thread(target=reader,daemon=True,name='neocore-parser-reader-'+str(self.process.pid));self.reader.start()
    def close(self):
        if self.process is None:return
        self.reader_stop.set()
        if self.process.poll() is None:self.process.kill()
        self.process.wait(timeout=10)
        for stream in (self.process.stdin,self.process.stdout):
            if stream:
                try:stream.close()
                except OSError:pass
        self.reader.join(timeout=2)
        self.stderr.seek(0);stderr=self.stderr.read()
        destination=os.environ.get('NEOCORE_OBSERVABILITY_DIR')
        try:
            if destination and stderr:
                folder=Path(destination)/'parser_errors';folder.mkdir(exist_ok=True)
                target=folder/(str(self.process.pid)+'-'+str(self.sequence)+'.parser.stderr.log')
                with target.open('xb') as stream:stream.write(stderr)
        finally:self.stderr.close();self.process=None
    def parse(self,source,origin,known_types):
        if self.process is None or self.process.poll() is not None or self.count>=self.batch_limit:
            self.close();self.start()
        self.sequence+=1;self.count+=1
        identity=dict(sequence=self.sequence,source_sha256=hashlib.sha256(source).hexdigest(),origin=origin,
            known_sha256=hashlib.sha256(json.dumps(sorted(known_types)).encode()).hexdigest(),context_sha256=self.context)
        request=dict(identity,source_base64=base64.b64encode(source).decode('ascii'),known_types=sorted(known_types))
        raw=json.dumps(request,ensure_ascii=True).encode()+b'\n';write_errors=[];stream=self.process.stdin
        def write():
            try:stream.write(raw);stream.flush()
            except (OSError,ValueError) as error:write_errors.append(error)
        writer=threading.Thread(target=write,daemon=True);writer.start()
        try:
            try:reply=self.replies.get(timeout=self.timeout)
            except queue.Empty:raise RuntimeError('Parser request timed out after '+str(self.timeout)+' seconds: '+origin)
            if reply is None:raise RuntimeError('Parser worker exited before replying: '+origin)
            value=json.loads(reply)
            if any(value.get(k)!=v for k,v in identity.items()):raise RuntimeError('Parser reply identity mismatch: '+origin)
            if value.get('status')!='PARSED_RESPONSE':raise RuntimeError('Parser rejected request: '+value.get('error','Unknown error'))
            result=value['ir']
            if result['origin']!=origin or result['source_sha256']!=identity['source_sha256']:raise RuntimeError('Parser result identity mismatch: '+origin)
            if value.get('parser_metrics'):
                from translation_observer import event
                event('parser_worker','REQUEST_FINISHED',file=origin,worker_pid=self.process.pid,parser_metrics=value['parser_metrics'])
            return result
        except BaseException:
            self.close();raise
        finally:writer.join(timeout=2)

def worker_main():
    # A prototype outside dev has the same producer import; installed copies
    # use their own directory. No production package imports this module.
    candidate=Path(__file__).resolve().parent
    if not (candidate/'java_frontend.py').exists():candidate=Path(__file__).resolve().parents[3]
    sys.path.insert(0,str(candidate))
    from java_frontend import parse_source
    from translation_observer import metrics
    for line in sys.stdin.buffer:
        request=json.loads(line);identity={k:request[k] for k in ('sequence','source_sha256','origin','known_sha256','context_sha256')}
        try:
            raw=base64.b64decode(request['source_base64'],validate=True)
            if hashlib.sha256(raw).hexdigest()!=identity['source_sha256']:raise ValueError('Parser input digest mismatch')
            if hashlib.sha256(json.dumps(sorted(request['known_types'])).encode()).hexdigest()!=identity['known_sha256']:raise ValueError('Parser known-type digest mismatch')
            start=metrics();ir=parse_source(raw,request['origin'],request['known_types']);end=metrics()
            reply=dict(identity,status='PARSED_RESPONSE',ir=ir,parser_metrics=dict(
                cpu_request_seconds=end['cpu_seconds']-start['cpu_seconds'],
                process_memory_highwater_bytes=end['memory_peak_bytes'],process_memory_current_bytes=end['memory_current_bytes'],
                memory_scope='Parser PID cumulative high-water at request end; not an exclusive per-file allocation peak'))
        except Exception as error:reply=dict(identity,status='ERROR',error=type(error).__name__+': '+str(error))
        sys.stdout.buffer.write(json.dumps(reply,ensure_ascii=True,separators=(',',':')).encode()+b'\n');sys.stdout.buffer.flush()
        # No CST or IR from a previous request may overlap the next parse.
        if 'ir' in locals():del ir
        if 'raw' in locals():del raw
        del request,reply,identity,line

if __name__=='__main__':worker_main()
