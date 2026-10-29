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

HERE = Path(__file__).resolve().parent
LIMIT = 128 * 1024 * 1024


class Workspace:
    def __init__(self, root, config=None):
        self.root=Path(root).resolve()
        self.inputs,self.outputs,self.runs=self.root/'导入副本',self.root/'转换产物',self.root/'转换记录'
        for path in (self.inputs,self.outputs,self.runs):path.mkdir(parents=True,exist_ok=True)
        self.config=config or json.loads((HERE/'backend.json').read_bytes())
        self.lock=threading.RLock();self.worker_lock=threading.Lock();self.jobs={}
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
            jobs=copy.deepcopy(list(self.jobs.values()))
        for job in jobs:
            if job.get('status')=='RUNNING' and job.get('attempt'):
                try:
                    value=json.loads((self.runs/job['attempt']/'progress.json').read_bytes())
                    job['message']=value['message'];job['stage']=value['phase']
                except (OSError,ValueError,KeyError):pass
        return {'jobs':jobs,'output_dir':str(self.outputs),'version':'0.9.0',
                'release_status':'RELEASED','current_release':'0.9.0',
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
            job=self.jobs.get(key)
            if not job:raise ValueError('找不到任务')
            if job.get('status') in ('QUEUED','RUNNING'):return copy.deepcopy(job)
            if purpose not in ('mod','library'):raise ValueError('处理用途应为 mod 或 library')
            dependency_ids=[] if dependency_ids is None else dependency_ids
            if not isinstance(dependency_ids,list) or any(not isinstance(i,str) for i in dependency_ids) or len(set(dependency_ids))!=len(dependency_ids):raise ValueError('dependency_ids 应为不重复的任务标识数组')
            records=self.dependency_records(key,dependency_ids)
            attempt=uuid.uuid4().hex
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
                job=self.jobs[key];job.update(status='RUNNING',message='正在准备转换');self.save(job)
                name=job['pack']+'-0.9.0-'+attempt[:8]+'.zip'
            try:
                folder.mkdir()
                request={'jar':str(self.inputs/(key+'.jar')),'work':str(folder),
                         'output':str(self.outputs/name),'config':dict(self.config,purpose=job.get('purpose','mod'),dependency_artifacts=job.get('dependency_artifacts',[]))}
                write_json(folder/'request.json',request)
                with (folder/'worker.log').open('wb') as log:
                    process=subprocess.run([sys.executable,'-B',str(HERE/'conversion.py'),str(folder/'request.json')],
                        stdout=log,stderr=subprocess.STDOUT,timeout=900,
                        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if process.returncode:raise ValueError('转换进程异常，查看转换记录中的 worker.log')
                result=json.loads((folder/'result.json').read_bytes())
                if result.get('output'):
                    if result['output']!=name or digest(self.outputs/name)!=result['output_sha256']:
                        raise ValueError('转换产物校验失败')
                with self.lock:
                    job.update({k:result[k] for k in ('status','stage','message','diagnostics','translated','translation','content','content_staged','translated_dependencies','dependency_abi','pipeline','artifact_kind','source_mode','source_output','output','output_sha256','tree') if k in result})
            except Exception as error:
                with self.lock:job.update(status='FAILED',message=str(error) or type(error).__name__)
                try:(folder/'worker_failure.log').write_text(traceback.format_exc(),encoding='utf-8')
                except OSError:pass
            with self.lock:self.save(job)

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
                elif path == '/health':
                    self.reply({'app':'neocore-converter-gui','version':'0.9.0','pid':os.getpid()})
                elif path == '/api/state' and self.authorized():
                    self.reply(workspace.state())
                elif path.startswith('/api/job/') and self.authorized():
                    key=path.rsplit('/',1)[-1]
                    with workspace.lock:job=copy.deepcopy(workspace.jobs.get(key))
                    if job is None:self.reply({'error':'找不到任务'},404);return
                    self.reply({'job':job})
                elif path.startswith('/api/report/') and self.authorized():
                    key=path.rsplit('/',1)[-1]
                    with workspace.lock:job=copy.deepcopy(workspace.jobs.get(key))
                    if job is None:self.reply({'error':'找不到任务'},404);return
                    attempt=job.get('attempt')
                    if not attempt:self.reply({'error':'尚未转换'},409);return
                    folder=workspace.runs/attempt
                    result=json.loads((folder/'result.json').read_bytes()) if (folder/'result.json').is_file() else {'status':job['status']}
                    reports=[json.loads(p.read_bytes()) for p in folder.glob('jobs/*/converted/translation_report.json')]
                    jobs=[json.loads(p.read_bytes()) for p in folder.glob('jobs/*/job_report.json')]
                    content=[json.loads(p.read_bytes()) for p in folder.glob('jobs/*/content/content_manifest.json')]
                    abis=[json.loads(p.read_bytes()) for p in folder.glob('jobs/*/dependency_abi.json')]
                    self.reply({'result':result,'source_reports':reports,'job_reports':jobs,'content_reports':content,'dependency_abis':abis})
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
                    if workspace.active():
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
            if health.get('app')=='neocore-converter-gui' and health.get('pid')==previous['pid'] and health.get('version')=='0.9.0':
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
