"""Text client for the same local conversion queue used by the browser."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

HERE=Path(__file__).resolve().parent


def request(root, route, data=None, headers=None):
    connection=json.loads((root/'当前窗口.json').read_bytes())
    url=connection['url']
    if urllib.parse.urlsplit(url).hostname!='127.0.0.1':raise ValueError('后台地址必须是本机')
    auth={'X-NeoCore-Token':connection['token']}
    auth.update(headers or {})
    req=urllib.request.Request(url+route.lstrip('/'),data=data,headers=auth)
    with urllib.request.urlopen(req,timeout=120) as response:return response.read()


def call(root,route,data=None,headers=None):
    return json.loads(request(root,route,data,headers))


def describe(value):
    if 'jobs' in value:
        return '\n'.join(describe({'job':job}) for job in value['jobs']) or '暂无任务'
    if 'job' in value:
        job=value['job'];tr=job.get('translation',{})
        lines=[job['id']+' '+job.get('filename','')+' '+job['status'],job.get('message','')]
        if 'files' in tr:
            if tr['files']:lines.append('生成待审查: {}/{}；人工处理: {}；失败: {}'.format(tr['generated_for_review'],tr['files'],tr['manual_review'],tr['failed']))
            else:lines.append('Java 代码：不适用（无 Java 文件）')
        content=job.get('content',{})
        if content:
            labels={'data_json':'data JSON','assets_resources':'资源','metadata_dependencies':'元数据/依赖','mixin_at':'Mixin/AT'}
            lines.append('内容扫描：'+'；'.join(label+' '+str(content.get('lanes',{}).get(lane,{}).get('files',0)) for lane,label in labels.items()))
            lines.append('原样保留 '+str(content.get('preserved_files',0))+' 项；未转换为网易格式')
            lines.append('内容清单：'+content['manifest'])
        for row in tr.get('skipped_optional',[]):lines.append(row['label']+': '+row['source'])
        for row in tr.get('capability_blockers',[]):lines.append('能力阻断: '+row['source']+' '+row['message'])
        if job.get('source_output'):lines.append('部分源码: '+job['source_output'])
        if job.get('dependency_abi'):
            abi=job['dependency_abi'];lines.append('前置库 ABI：'+abi['dependency_id']+'；可用类型 '+str(abi['available_types'])+'/'+str(abi['declared_types']))
        if job.get('dependency_ids'):lines.append('所选依赖：'+', '.join(job['dependency_ids']))
        if job.get('output'):lines.append(('源码审查包（不是网易测试包）: ' if job.get('artifact_kind')=='SOURCE_REVIEW_ZIP' else '网易测试 ZIP（待审查）: ')+job['output'])
        lines.append('网易加载/玩法：未验证')
        return '\n'.join(lines)
    return json.dumps(value,ensure_ascii=False,indent=2)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=HERE/'工作区')
    parser.add_argument('--json',action='store_true',help='机器可读 JSON 输出')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('start');sub.add_parser('status')
    for name in ('import','convert'):
        p=sub.add_parser(name);p.add_argument('jar',type=Path)
        if name=='convert':p.add_argument('--library',action='store_true');p.add_argument('--dependency',action='append',default=[])
    for name in ('export','report','wait'):
        p=sub.add_parser(name);p.add_argument('id')
        if name=='export':p.add_argument('--library',action='store_true');p.add_argument('--dependency',action='append',default=[])
    p=sub.add_parser('download');p.add_argument('id');p.add_argument('output',type=Path)
    args=parser.parse_args();root=args.data_dir.resolve()
    if args.command=='start':
        try:
            call(root,'api/state');value={'message':'后台已运行'}
        except (OSError,ValueError,KeyError):
            root.mkdir(parents=True,exist_ok=True)
            log=(root/'后台日志.txt').open('ab')
            process=subprocess.Popen([sys.executable,'-B',str(HERE/'app.py'),'--no-browser','--data-dir',str(root)],
                stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            log.close()
            for attempt in range(100):
                try:call(root,'api/state');break
                except (OSError,ValueError,KeyError):
                    if process.poll() is not None:raise ValueError('后台启动失败，查看后台日志.txt')
                    time.sleep(.1)
            else:raise ValueError('后台启动超时，查看后台日志.txt')
            value={'message':'后台已启动，无需打开浏览器'}
    elif args.command in ('import','convert'):
        jar=args.jar.resolve()
        if jar.stat().st_size>128*1024*1024:raise ValueError('单个 JAR 不得超过 128 MB')
        value=call(root,'api/import',jar.read_bytes(),{'X-Filename':urllib.parse.quote(jar.name)})
        if args.command=='convert':value=call(root,'api/export',json.dumps({'id':value['job']['id'],'purpose':'library' if args.library else 'mod','dependency_ids':args.dependency}).encode())
    elif args.command=='export':value=call(root,'api/export',json.dumps({'id':args.id,'purpose':'library' if args.library else 'mod','dependency_ids':args.dependency}).encode())
    elif args.command=='status':value=call(root,'api/state')
    elif args.command=='report':value=call(root,'api/report/'+urllib.parse.quote(args.id,safe=''))
    elif args.command=='wait':
        while True:
            value=call(root,'api/job/'+urllib.parse.quote(args.id,safe=''))
            if value['job']['status'] not in ('QUEUED','RUNNING'):break
            time.sleep(1)
    else:
        raw=request(root,'download/'+urllib.parse.quote(args.id,safe=''))
        # Never overwrite an existing user file.
        with args.output.open('xb') as output:output.write(raw)
        value={'downloaded':str(args.output.resolve()),'bytes':len(raw)}
    print(json.dumps(value,ensure_ascii=False,indent=2) if args.json else describe(value))
    return 1 if value.get('job',{}).get('status') in ('BLOCKED','FAILED','INTERRUPTED','TRANSLATION_INCOMPLETE') else 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,KeyError) as error:
        print('错误: '+str(error),file=sys.stderr);raise SystemExit(2)
