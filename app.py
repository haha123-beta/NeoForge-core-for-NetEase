"""Local-only browser GUI. Python 3.11+, standard library only."""
import argparse
import json
import os
import secrets
import shutil
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from jar_input import inspect_jar, preview_tree, digest
from conversion import environment, write_json
from pipeline_artifacts import verify_dependency
import subprocess
import copy
from process_control import OwnedProcess,Cancelled,TimedOut
from diagnostic_export import snapshot as diagnostic_snapshot,archive as diagnostic_archive
from decompiler_evidence import recover as recover_decompiler,release_parser_caches

HERE = Path(__file__).resolve().parent
LIMIT = 128 * 1024 * 1024

def mining_module(workspace):
    dev=Path(workspace.config['dev_root']).resolve()
    if str(dev) not in sys.path:sys.path.insert(0,str(dev))
    from tools.compat_mining098 import web
    return web


class Workspace:
    def __init__(self, root, config=None):
        self.root=Path(root).resolve()
        self.inputs,self.outputs,self.runs=self.root/'导入副本',self.root/'转换产物',self.root/'转换记录'
        for path in (self.inputs,self.outputs,self.runs):path.mkdir(parents=True,exist_ok=True)
        self.config=config or json.loads((HERE/'backend.json').read_bytes())
        self.lock=threading.RLock();self.worker_lock=threading.Lock();self.jobs={};self.cancellations={}
        self.restore()

    def restore(self):
        for path in sorted(self.inputs.glob('*.json')):
            try:
                job=json.loads(path.read_bytes());key=job['id']
                if not isinstance(key,str) or len(key)!=32 or any(c not in '0123456789abcdef' for c in key):continue
                source=self.inputs/(key+'.jar')
                if not source.is_file() or digest(source)!=job['sha256']:continue
                if not job.get('output'):job['tree']=preview_tree(job)
                if job.get('status') in ('QUEUED','RUNNING'):
                    job.update(status='INTERRUPTED',message='上次转换未完成，请点击重新转换',translated=False)
                    job.pop('output',None)
                name=job.get('output')
                if name and (Path(name).name!=name or not (self.outputs/name).is_file()
                        or digest(self.outputs/name)!=job.get('output_sha256')):
                    job.pop('output',None);job.update(status='INTERRUPTED',message='产物缺失或校验值变化，请重新转换',translated=False,tree=preview_tree(job))
                self.jobs[key]=job
            except (OSError,ValueError,KeyError,TypeError):continue

    def save(self,job):write_json(self.inputs/(job['id']+'.json'),job)

    def add(self,path,filename):
        if not filename.lower().endswith('.jar'):raise ValueError('请选择 .jar 文件')
        info=inspect_jar(path,filename)
        with self.lock:
            for job in self.jobs.values():
                if job['sha256']==info['sha256']:return copy.deepcopy(job)
            key=uuid.uuid4().hex;shutil.copyfile(path,self.inputs/(key+'.jar'))
            job=dict(info,id=key,tree=preview_tree(info),status='IMPORTED',message='已识别，尚未实际转换')
            self.save(job);self.jobs[key]=job;return copy.deepcopy(job)

    def state(self):
        with self.lock:
            jobs=[]
            for job in self.jobs.values():
                summary=dict(job)
                summary['diagnostic_count']=len(job.get('diagnostics',[]))
                summary['diagnostics']=job.get('diagnostics',[])[:50]
                summary['diagnostics_truncated_for_state']=summary['diagnostic_count']>50
                jobs.append(copy.deepcopy(summary))
        for job in jobs:
            if job.get('status')=='RUNNING' and job.get('attempt'):
                try:
                    value=json.loads((self.runs/job['attempt']/'progress.json').read_bytes())
                    job['message']=value.get('message',job['message']);job['stage']=value['phase']
                except (OSError,ValueError,KeyError):pass
                try:job['live']=json.loads((self.runs/job['attempt']/'live.json').read_bytes())
                except (OSError,ValueError):pass
        return {'jobs':jobs,'output_dir':str(self.outputs),'version':'1.0.0',
                'release_status':'DEVELOPMENT','current_release':'1.0.0',
                'format_preview_only':False,'environment':environment(self.config)}

    def dependency_records(self,key,dependency_ids):
        records=[];visited=set();visiting={key}
        def append_record(record):
            if not Path(record['manifest']).resolve().is_relative_to(self.runs.resolve()) or not Path(record['source_root']).resolve().is_relative_to(self.runs.resolve()):raise ValueError('前置库快照不属于当前工作区')
            verify_dependency(record)
            if not any(r['manifest_sha256']==record['manifest_sha256'] for r in records):records.append(copy.deepcopy(record))
        def visit(identity):
            if identity in visiting:raise ValueError('前置库依赖存在循环')
            if identity in visited:return
            job=self.jobs.get(identity)
            if not job or job.get('status') in ('QUEUED','RUNNING'):raise ValueError('前置库任务不存在或仍在处理：'+identity)
            record=job.get('dependency_abi')
            if not record or not record.get('available_types'):raise ValueError('该任务尚无可用前置库 ABI：'+identity)
            attempt=job.get('attempt','');base=self.runs/attempt
            if not attempt or not Path(record['manifest']).resolve().is_relative_to(base.resolve()) or not Path(record['source_root']).resolve().is_relative_to(base.resolve()):raise ValueError('前置库清单不属于已记录的转换任务')
            if record['source_jar_sha256']!=job['sha256']:raise ValueError('前置库 JAR 来源摘要变化')
            verify_dependency(record);visiting.add(identity)
            if key in job.get('dependency_ids',[]):raise ValueError('前置库依赖当前任务，存在循环')
            # Keep the exact dependency snapshots used to build this library;
            # reconverting another task must not silently replace its ABI.
            for snapshot in job.get('dependency_artifacts',[]):append_record(snapshot)
            visiting.remove(identity);visited.add(identity);append_record(record)
        for identity in dependency_ids:visit(identity)
        owners={}
        for record in records:
            name=record['dependency_id']
            if name in owners:raise ValueError('同时选择了相同前置库标识的多个任务：'+name)
            owners[name]=record
        for record in records:
            missing=set(record.get('requires_translated_dependencies',[]))-set(owners)
            if missing:raise ValueError('前置库缺少传递依赖：'+', '.join(sorted(missing)))
        return records

    def export(self,key,purpose='mod',dependency_ids=None):
        with self.lock:
            miner=getattr(self,'mining_controller',None)
            if miner is not None and miner.snapshot()['status']=='RUNNING':raise ValueError('请等待兼容性挖掘完成后转换')
            job=self.jobs.get(key)
            if not job:raise ValueError('找不到任务')
            if job.get('status') in ('QUEUED','RUNNING'):return copy.deepcopy(job)
            if purpose not in ('mod','library'):raise ValueError('处理用途应为 mod 或 library')
            dependency_ids=[] if dependency_ids is None else dependency_ids
            if not isinstance(dependency_ids,list) or any(not isinstance(i,str) for i in dependency_ids) or len(set(dependency_ids))!=len(dependency_ids):raise ValueError('dependency_ids 应为不重复的任务标识数组')
            records=self.dependency_records(key,dependency_ids)
            attempt=uuid.uuid4().hex
            self.cancellations[attempt]=threading.Event()
            folder=self.runs/attempt;folder.mkdir()
            write_json(folder/'task_identity.json',dict(job_id=key,attempt=attempt,input_sha256=job['sha256']))
            job.update(status='QUEUED',message='已排队，等待转换',attempt=attempt,translated=False,tree=preview_tree(job))
            for name in ('output','output_sha256','artifact_kind','dependency_abi','pipeline','diagnostics','translation','content','content_staged','translated_dependencies','stage','source_mode','source_output'):job.pop(name,None)
            job.update(purpose=purpose,dependency_ids=dependency_ids,dependency_artifacts=records)
            self.save(job)
            threading.Thread(target=self.run,args=(key,attempt),daemon=True).start()
            return copy.deepcopy(job)

    def run(self,key,attempt):
        with self.worker_lock:
            folder=self.runs/attempt
            with self.lock:
                job=self.jobs[key]
                if self.cancellations[attempt].is_set():job.update(status='CANCELLED',message='已取消排队任务');self.save(job);return
                job.update(status='RUNNING',message='正在准备转换',started_at=time.time());self.save(job)
                name=job['pack']+'-1.0.0-'+attempt[:8]+'.zip'
            try:
                folder.mkdir(exist_ok=True)
                request={'jar':str(self.inputs/(key+'.jar')),'work':str(folder),
                         'output':str(self.outputs/name),'config':dict(self.config,purpose=job.get('purpose','mod'),dependency_artifacts=job.get('dependency_artifacts',[]))}
                write_json(folder/'request.json',request)
                with (folder/'worker.log').open('wb') as log:
                    process=OwnedProcess([sys.executable,'-B',str(HERE/'conversion.py'),str(folder/'request.json')],log)
                    last_sample=[0]
                    def sample():
                        if time.monotonic()-last_sample[0]<1:return
                        last_sample[0]=time.monotonic()
                        with (folder/'worker_resources.jsonl').open('a',encoding='utf-8') as evidence:evidence.write(json.dumps(process.resource_snapshot())+'\n')
                    returncode=process.wait(900,cancel=self.cancellations[attempt].is_set,tick=sample)
                if returncode:raise ValueError('转换进程异常，查看转换记录中的 worker.log')
                result=json.loads((folder/'result.json').read_bytes())
                if result.get('input_sha256')!=job['sha256']:raise ValueError('转换报告输入摘要与任务不匹配')
                if result.get('output'):
                    if result['output']!=name or digest(self.outputs/name)!=result['output_sha256']:
                        raise ValueError('转换产物校验失败')
                with self.lock:
                    job.update({k:result[k] for k in ('status','stage','message','diagnostics','translated','translation','content','content_staged','translated_dependencies','dependency_abi','pipeline','artifact_kind','source_mode','source_output','output','output_sha256','tree') if k in result})
            except Exception as error:
                with self.lock:job.update(status='CANCELLED' if isinstance(error,Cancelled) else 'TIMED_OUT' if isinstance(error,TimedOut) else 'FAILED',message=str(error) or type(error).__name__)
                try:(folder/'worker_failure.log').write_text(traceback.format_exc(),encoding='utf-8')
                except OSError:pass
            with self.lock:
                job['elapsed_seconds']=time.time()-job.get('started_at',time.time())
                try:job['decompiler_recovery']=recover_decompiler(folder,attempt,job['sha256'])
                except (OSError,ValueError) as error:
                    job['decompiler_recovery']=dict(status='RECOVERY_FAILED',error=str(error))
                try:job['released_parser_caches']=release_parser_caches(folder)
                except (OSError,ValueError) as error:job['parser_cache_cleanup_error']=str(error)
                if not (folder/'result.json').exists():write_json(folder/'result.json',dict(status=job['status'],message=job['message'],engine_verified=False,translated=False,input_sha256=job['sha256']))
                job['diagnostics_available']=True;self.save(job)

    def cancel(self,key):
        with self.lock:
            job=self.jobs.get(key)
            if not job:raise ValueError('找不到任务')
            if job.get('status') not in ('QUEUED','RUNNING'):return copy.deepcopy(job)
            self.cancellations[job['attempt']].set();job['message']='正在取消并回收子进程';self.save(job)
            return copy.deepcopy(job)

    def diagnostic(self,key):
        with self.lock:job=copy.deepcopy(self.jobs.get(key))
        if not job or not job.get('attempt'):raise ValueError('尚无转换记录')
        return diagnostic_snapshot(self.evidence_folder(job),job)[0]

    def shared_blockers(self):
        with self.lock:
            targets=[copy.deepcopy(j) for j in self.jobs.values() if j.get('attempt')]
        groups={};unavailable=[]
        for job in targets:
            try:
                report=diagnostic_snapshot(self.evidence_folder(job),job)[0]
            except (OSError,ValueError,KeyError) as error:
                unavailable.append({'job_id':job['id'],'reason':str(error)});continue
            for group in report['structured_diagnostics']['shared_blockers']:
                blocker=group['blocker'];key=blocker['shared_key']
                entry=groups.setdefault(key,{'blocker':blocker,'affected_files':[]})
                entry['affected_files'].extend({'job_id':job['id'],'mod':job['filename'],'file':name}
                    for name in group['affected_files'])
        return {'schema_version':1,'groups':list(groups.values()),'unavailable':unavailable,
            'note':'仅聚合已发生的首阻断；清除诊断不保证新增可生成文件','engine_verified':False}

    def evidence_folder(self,job):
        folder=self.runs/job['attempt']
        if not folder.resolve().is_relative_to(self.runs.resolve()) or folder.is_symlink() or (hasattr(folder,'is_junction') and folder.is_junction()):raise ValueError('诊断目录不属于当前工作区')
        expected=dict(job_id=job['id'],attempt=job['attempt'],input_sha256=job['sha256'])
        identity=folder/'task_identity.json'
        if identity.exists():
            if json.loads(identity.read_bytes())!=expected:raise ValueError('诊断任务归属不匹配')
        else:
            # Migrate a previous 1.0.0 development record only after verifying
            # the request points to this workspace's exact imported JAR.
            request=json.loads((folder/'request.json').read_bytes())
            source=self.inputs/(job['id']+'.jar')
            if Path(request['jar']).resolve()!=source.resolve() or digest(source)!=job['sha256']:raise ValueError('历史诊断记录来源不匹配')
            write_json(identity,expected)
        return folder

    def events(self,key,after=0):
        if after<0:raise ValueError('事件位置无效')
        with self.lock:job=copy.deepcopy(self.jobs.get(key))
        if not job or not job.get('attempt'):raise ValueError('尚无转换记录')
        path=self.evidence_folder(job)/'events.jsonl';events=[];cursor=after
        if path.exists():
            with path.open('rb') as stream:
                if after>path.stat().st_size:after=0
                stream.seek(after);cursor=after
                for _ in range(128):
                    line=stream.readline(262144)
                    if not line or not line.endswith(b'\n'):break
                    events.append(json.loads(line));cursor=stream.tell()
        return dict(job_id=key,attempt=job['attempt'],cursor=cursor,events=events,status=job['status'])

    def active(self):
        with self.lock:return any(j.get('status') in ('QUEUED','RUNNING') for j in self.jobs.values())


def make_handler(workspace, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, data, status=200):
            raw = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_bytes(raw, 'application/json; charset=utf-8', status)

        def send_bytes(self, raw, content_type, status=200):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self):
            return self.headers.get('X-NeoCore-Token') == token

        def local_host(self):
            return urllib.parse.urlsplit('http://'+self.headers.get('Host','')).hostname in ('127.0.0.1','localhost')

        def do_GET(self):
            if not self.local_host():
                self.reply({'error': '仅支持本机窗口'}, 403); return
            try:
                path = urllib.parse.urlsplit(self.path).path
                if path == '/':
                    raw = (HERE/'index.html').read_text(encoding='utf-8').replace('__TOKEN__', token).encode('utf-8')
                    self.send_bytes(raw, 'text/html; charset=utf-8')
                elif path == '/mining':
                    self.send_bytes(mining_module(workspace).page(token),'text/html; charset=utf-8')
                elif path == '/mining/report':
                    self.send_bytes(mining_module(workspace).controller(workspace).artifact('report.html'),'text/html; charset=utf-8')
                elif path == '/api/mining/state' and self.authorized():
                    self.reply(mining_module(workspace).controller(workspace).snapshot())
                elif path == '/api/mining/tasks' and self.authorized():
                    self.send_bytes(mining_module(workspace).controller(workspace).artifact('能力任务包.zip'),'application/zip')
                elif path == '/api/mining/ranking' and self.authorized():
                    self.send_bytes(mining_module(workspace).controller(workspace).artifact('ranking.json'),'application/json; charset=utf-8')
                elif path == '/health':
                    self.reply({'app':'neocore-converter-gui','version':'1.0.0','pid':os.getpid()})
                elif path == '/api/state' and self.authorized():
                    self.reply(workspace.state())
                elif path.startswith('/api/job/') and self.authorized():
                    key=path.rsplit('/',1)[-1]
                    job=next((j for j in workspace.state()['jobs'] if j['id']==key),None)
                    if job is None:self.reply({'error':'找不到任务'},404);return
                    self.reply({'job':job})
                elif path == '/api/shared-blockers' and self.authorized():
                    self.reply(workspace.shared_blockers())
                elif path.startswith('/api/diagnostic/') and self.authorized():
                    self.reply(workspace.diagnostic(path.rsplit('/',1)[-1]))
                elif path.startswith('/api/events/') and self.authorized():
                    query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                    self.reply(workspace.events(path.rsplit('/',1)[-1],int(query.get('after',['0'])[0])))
                elif path.startswith('/diagnostic-download/'):
                    query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                    if not self.authorized() and query.get('token')!=[token]:self.reply({'error':'无效的下载请求'},403);return
                    key=path.rsplit('/',1)[-1]
                    with workspace.lock:job=copy.deepcopy(workspace.jobs.get(key))
                    if not job or not job.get('attempt'):self.reply({'error':'尚无转换记录'},404);return
                    # Immutable snapshot is built to a unique file; active task
                    # evidence is explicitly a checkpoint, not a final report.
                    target=workspace.outputs/('diagnostic-'+key+'-'+uuid.uuid4().hex+'.zip')
                    diagnostic_archive(workspace.evidence_folder(job),job,target)
                    self.send_bytes(target.read_bytes(),'application/zip')
                elif path.startswith('/api/report/') and self.authorized():
                    key=path.rsplit('/',1)[-1]
                    with workspace.lock:job=copy.deepcopy(workspace.jobs.get(key))
                    if job is None:self.reply({'error':'找不到任务'},404);return
                    attempt=job.get('attempt')
                    if not attempt:self.reply({'error':'尚未转换'},409);return
                    folder=workspace.evidence_folder(job)
                    result=json.loads((folder/'result.json').read_bytes()) if (folder/'result.json').is_file() else {'status':job['status']}
                    reports=[json.loads(p.read_bytes()) for p in folder.glob('jobs/*/converted/translation_report.json')]
                    jobs=[json.loads(p.read_bytes()) for p in folder.glob('jobs/*/job_report.json')]
                    content=[json.loads(p.read_bytes()) for p in folder.glob('jobs/*/content/content_manifest.json')]
                    abis=[json.loads(p.read_bytes()) for p in folder.glob('jobs/*/dependency_abi.json')]
                    data_reports=[json.loads(p.read_bytes()) for p in folder.glob('data_report.json')]
                    self.reply({'result':result,'source_reports':reports,'job_reports':jobs,'content_reports':content,'dependency_abis':abis,'data_reports':data_reports})
                elif path.startswith('/download/'):
                    query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                    if (query.get('token') is not None and query.get('token') != [token]) or (query.get('token') is None and not self.authorized()):
                        self.reply({'error': '无效的下载请求'}, 403); return
                    key = path.split('/')[-1]
                    with workspace.lock:
                        job = workspace.jobs.get(key)
                        if not job or not job.get('output'):
                            self.reply({'error': '实际转换 ZIP 尚未生成'}, 404); return
                        output = workspace.outputs/job['output']
                        if not output.is_file() or digest(output)!=job.get('output_sha256'):
                            self.reply({'error':'转换产物缺失或变化，请重新转换'},409); return
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/zip')
                    self.send_header('Content-Disposition', "attachment; filename*=UTF-8''"+urllib.parse.quote(output.name))
                    self.send_header('Content-Length', str(output.stat().st_size))
                    self.end_headers()
                    with output.open('rb') as source:
                        shutil.copyfileobj(source, self.wfile)
                else:
                    self.reply({'error': '找不到页面'}, 404)
            except (OSError, ValueError) as error:
                self.reply({'error': str(error)}, 400)

        def do_POST(self):
            if not self.local_host() or not self.authorized():
                self.reply({'error': '请求来源无效，请重新打开转换器'}, 403); return
            try:
                path = urllib.parse.urlsplit(self.path).path
                size = int(self.headers.get('Content-Length', '0'))
                if size < 0 or size > LIMIT:
                    self.reply({'error': '单个 JAR 不得超过 128 MB'}, 413); return
                self.connection.settimeout(90)
                if path == '/api/import':
                    filename = urllib.parse.unquote(self.headers.get('X-Filename', ''))
                    filename = filename.replace('\\', '/').split('/')[-1]
                    temporary = workspace.inputs/('.upload-'+uuid.uuid4().hex)
                    try:
                        remaining = size
                        with temporary.open('xb') as output:
                            while remaining:
                                block = self.rfile.read(min(1024*1024, remaining))
                                if not block:raise ValueError('文件上传中断')
                                output.write(block); remaining -= len(block)
                        self.reply({'job': workspace.add(temporary, filename)})
                    finally:
                        temporary.unlink(missing_ok=True)
                elif path == '/api/export':
                    if size > 4096:raise ValueError('请求过大')
                    request = json.loads(self.rfile.read(size))
                    if set(request)-{'id','purpose','dependency_ids'}:raise ValueError('未知的转换选项')
                    self.reply({'job': workspace.export(request['id'],request.get('purpose','mod'),request.get('dependency_ids',[]))})
                elif path == '/api/mining/start':
                    if size>16384:raise ValueError('挖掘请求过大')
                    request=json.loads(self.rfile.read(size))
                    self.reply(mining_module(workspace).controller(workspace).start(request))
                elif path == '/api/cancel':
                    if size>4096:raise ValueError('请求过大')
                    request=json.loads(self.rfile.read(size));self.reply({'job':workspace.cancel(request['id'])})
                elif path == '/api/examples':
                    examples = workspace.root/'测试样本.json'
                    if not examples.is_file():
                        self.reply({'error': '本目录没有测试样本，请直接拖入 JAR 或点击选择文件'}, 400); return
                    jobs = []
                    for item in json.loads(examples.read_bytes()):
                        source = Path(item['copy'])
                        if not source.is_absolute():source=workspace.root/source
                        if not source.resolve().is_relative_to(workspace.root):raise ValueError('样本必须在工作区副本目录')
                        jobs.append(workspace.add(source, item['filename']))
                    self.reply({'jobs': jobs})
                elif path == '/api/open-records':
                    if sys.platform == 'win32':os.startfile(str(workspace.runs))
                    self.reply({'path': str(workspace.runs)})
                elif path == '/api/open-output':
                    if sys.platform == 'win32':os.startfile(str(workspace.outputs))
                    self.reply({'path': str(workspace.outputs)})
                elif path == '/api/shutdown':
                    miner=getattr(workspace,'mining_controller',None)
                    if workspace.active() or (miner is not None and miner.snapshot()['status']=='RUNNING'):
                        self.reply({'error':'转换仍在进行，请完成后退出'},409); return
                    self.reply({'closed':True})
                    threading.Thread(target=self.server.shutdown,daemon=True).start()
                else:self.reply({'error': '未知操作'}, 404)
            except Exception as error:
                (workspace.root/'错误日志.txt').write_text(traceback.format_exc(), encoding='utf-8')
                self.reply({'error': str(error) or type(error).__name__}, 400)
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=HERE/'工作区')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    workspace = Workspace(args.data_dir)
    window_record=workspace.root/'当前窗口.json'
    if not args.port and window_record.is_file():
        try:
            previous=json.loads(window_record.read_bytes())
            if urllib.parse.urlsplit(previous['url']).hostname!='127.0.0.1':raise ValueError('not local')
            with urllib.request.urlopen(previous['url']+'health',timeout=1) as response:health=json.load(response)
            if health.get('app')=='neocore-converter-gui' and health.get('pid')==previous['pid'] and health.get('version')=='1.0.0':
                if not args.no_browser:webbrowser.open(previous['url'])
                return
        except (OSError,ValueError,KeyError):pass
    token = secrets.token_urlsafe(32)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(workspace, token))
    url = 'http://127.0.0.1:'+str(server.server_address[1])+'/'
    (workspace.root/'当前窗口.json').write_text(json.dumps({'url': url, 'pid': os.getpid(), 'token':token}, indent=2), encoding='utf-8')
    if not args.no_browser:
        threading.Timer(.4, lambda: webbrowser.open(url)).start()
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        server.server_close()
        try:
            if json.loads(window_record.read_bytes()).get('pid')==os.getpid():window_record.unlink()
        except (OSError,ValueError):pass


if __name__ == '__main__':
    main()
