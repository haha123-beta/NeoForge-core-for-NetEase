"""Development backend adapter. Never executes input JAR code."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import traceback
import zipfile
import os,time
from process_control import OwnedProcess,TimedOut
from decompiler_evidence import register as register_decompiler,recover as recover_decompiler
from jar_input import digest, inspect_jar, valid_entries
from pipeline_artifacts import dependency_artifact,verify_dependency,review_archive

VERSION = '0.9.8'


def write_json(path, data):
    path = Path(path)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def environment(config):
    dev = Path(config['dev_root']).resolve()
    required = ['run_translation_job.py', 'build_distribution.py', 'decompile_mod.py', 'workspace_paths.py']
    return {'ready': all((dev/name).is_file() for name in required), 'dev_root': str(dev),
            'message': '已连接本机转换工具' if all((dev/name).is_file() for name in required) else '找不到本机转换工具，请检查 backend.json 的 dev_root'}


def checked_entries(archive):
    entries = valid_entries(archive)
    files = {e.filename.rstrip('/').casefold() for e in entries if not e.is_dir()}
    for entry in entries:
        path = PurePosixPath(entry.filename)
        if stat.S_ISLNK(entry.external_attr >> 16):
            raise ValueError('不支持 JAR 内链接：'+entry.filename)
        for part in path.parts:
            if (part.endswith(('.', ' ')) or any(ord(c)<32 for c in part)
                    or part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}):
                raise ValueError('Windows 无法保真保留此路径：'+entry.filename)
        if any(str(p).casefold() in files for p in path.parents if str(p)!='.'):
            raise ValueError('JAR 文件与目录路径冲突：'+entry.filename)
    return entries


def archive_distribution(distribution, output, report):
    roots = ([(distribution/'NeoCore_behavior_pack', 'behavior_pack_neocore'),
             (distribution/'NeoCore_resource_pack', 'resource_pack_neocore')] if report.get('core_modules',1) else [])
    roots += [(distribution/row['pack_path'], row['pack_path']) for row in report['contents']]
    roots += [(distribution/row['resource_pack_path'], row['resource_pack_path']) for row in report['contents'] if row.get('resource_pack_path')]
    with zipfile.ZipFile(output, 'x') as zipped:
        for folder, label in roots:
            for path in sorted(folder.rglob('*')):
                if path.is_symlink():raise ValueError('发行目录不允许链接')
                name = label+'/'+path.relative_to(folder).as_posix()
                if path.is_dir():zipped.writestr(name+'/', b'', compress_type=zipfile.ZIP_STORED)
                elif path.is_file():
                    if path.suffix.lower() in ('.class','.java','.jar','.pyc','.pyo','.exe','.dll','.so'):
                        raise ValueError('发行目录含未转换文件：'+name)
                    raw=path.read_bytes()
                    zipped.writestr(name,raw,compress_type=zipfile.ZIP_DEFLATED if raw else zipfile.ZIP_STORED)
        if report.get('source_kind')=='DATA_ONLY':
            text='# NeoCore 数据实验候选\n\n纯数据格式转换，未进行 Java 转译，不包含 Python 入口或共享核心。'
            text+=('本包仅含通过静态检查的部分配方，不能代表原模组完整兼容。' if report.get('partial') else '全部所选数据已静态生成，尚待网易验证。')
        else:
            text='# NeoCore 代码与内容测试候选\n\n包含一份共享核心。已转换内容以各内容报告为准；其余原始资源保留不等于语义转换。'
        zipped.writestr('转换说明.md',(text+'\n依赖、原生 SDK、加载和玩法仍须核实；打包不计实机成功。\n').encode('utf-8'))
    with zipfile.ZipFile(output) as zipped:
        if zipped.testzip():raise ValueError('ZIP 内容校验失败')
        for folder,label in roots:
            for path in folder.rglob('*'):
                if path.is_file() and zipped.read(label+'/'+path.relative_to(folder).as_posix())!=path.read_bytes():
                    raise ValueError('ZIP 来源校验失败')


def convert(jar, work, output, config, progress=lambda phase,message:None):
    jar,work,output=Path(jar).resolve(),Path(work).resolve(),Path(output).resolve()
    work.mkdir(parents=True,exist_ok=True)
    before=digest(jar)
    result={'version':VERSION,'status':'FAILED','stage':'inspection','input_sha256':before,
            'engine_verified':False,'format_preview_only':False,'translated':False,'diagnostics':[]}
    temporary=output.with_suffix('.partial')
    try:
        if output.exists() or temporary.exists():raise ValueError('输出已存在，请创建新转换任务')
        progress('inspection','检查 JAR 与模组声明')
        info=inspect_jar(jar)
        if not re.fullmatch(r'[a-z][a-z0-9_]{1,47}',info['mods'][0]['id']):raise ValueError('模组 ID 不能用于当前打包协议')
        source=work/'prepared';source.mkdir(exist_ok=False)
        with zipfile.ZipFile(jar) as zipped:
            entries=checked_entries(zipped)
            members=[e for e in entries if not e.is_dir()]
            if any(e.filename.lower().endswith('.jar') for e in members):
                raise ValueError('检测到嵌套 JAR 依赖，需要独立准备与审查，当前未自动合并')
            if any(e.filename.lower().endswith(('.py','.pyc','.pyo','.exe','.dll','.so')) for e in members):
                raise ValueError('输入含原生二进制或 Python 脚本，当前不自动混入转换内容')
            classes=[e.filename for e in members if e.filename.endswith('.class')]
            for entry in members:
                if entry.filename.endswith('.class') or classes and entry.filename.endswith('.java'):continue
                dest=source/entry.filename
                if not dest.resolve().is_relative_to(source):raise ValueError('JAR 路径越界')
                dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(zipped.read(entry))
        env=environment(config)
        if info['platform']!='NeoForge' and (classes or any(source.rglob('*.java'))):raise ValueError('当前 Java 转换只接入 NeoForge；该 JAR 为 '+info['platform'])
        if not env['ready']:raise ValueError(env['message'])
        dev=Path(env['dev_root']);sys.path.insert(0,str(dev))
        # Reject a version-mismatched source before CFR or data conversion.
        import importlib.util
        from build_source_bundle import SCRIPTS
        spec=importlib.util.spec_from_file_location('_source_version_rules',SCRIPTS/'core/mod_versions.py')
        versions=importlib.util.module_from_spec(spec);spec.loader.exec_module(versions)
        for dependency in info.get('dependencies',[]):
            name=dependency.get('modId');required=str(dependency.get('type','required')).lower()=='required'
            if required and name in ('minecraft','neoforge'):
                version={'minecraft':'1.21.1','neoforge':'21.1.233'}[name]
                if not versions.matches(version,dependency.get('versionRange','')):
                    raise ValueError('来源平台版本不匹配：'+name+' '+str(dependency.get('versionRange'))+'；当前固定参考 '+version)
        from validation_report import source_fingerprint
        from workspace_paths import PACK_ROOT
        def backend_fingerprint():
            value=source_fingerprint(str(PACK_ROOT))
            for name in ('conversion.py','pipeline_artifacts.py','jar_input.py','app.py','cli.py','process_control.py','diagnostic_export.py','decompiler_evidence.py'):
                value['workbench/'+name]=digest(Path(__file__).parent/name)
            for path in sorted((dev/'profiles').glob('*.json')):
                value['profiles/'+path.name]=digest(path)
            return value
        fingerprint=backend_fingerprint()
        result['backend_source_sha256']=fingerprint
        if not classes and not any(source.rglob('*.java')) and (source/'pack.mcmeta').is_file():
            from data_only094 import run as convert_data,validate_source
            try:
                validate_source(source,info)
            except ValueError as error:
                result.update(status='BLOCKED',stage='data_source_validation',message=str(error),
                    source_mode='DATA_ONLY',data_only=True,java_translation_applicable=False)
                result['diagnostics'].append(dict(file='pack.mcmeta',category='DATA_SOURCE_UNVERIFIED',reason=str(error)))
                write_json(work/'result.json',result)
                return result
            result.update(convert_data(source,work,output,info,archive_distribution,progress))
            if fingerprint!=backend_fingerprint():raise ValueError('数据转换期间工具源码变化，请重试')
            if digest(jar)!=before:raise ValueError('导入副本发生变化，请重新导入')
            write_json(work/'result.json',result)
            return result
        if classes:
            result['stage']='decompile';progress('decompile','正在准备 Java 源码，不运行模组代码')
            from decompile_mod import JAVA_EXE,BYTECODE_VIEWER_JAR,build_command
            if not Path(JAVA_EXE).is_file() or not Path(BYTECODE_VIEWER_JAR).is_file():
                raise ValueError('找不到现有 JDK/CFR，请检查本机反编译工具配置')
            # Reuse existing CFR invocation; ASCII temporary paths avoid old JDK path decoding issues.
            with tempfile.TemporaryDirectory(prefix='neocore092_'+work.name+'_',ignore_cleanup_errors=True) as tmp:
                tmp=Path(tmp);local=tmp/'input.jar';out=tmp/'out';out.mkdir()
                register_decompiler(work,tmp,before)
                shutil.copyfile(jar,local)
                with (work/'decompile.log').open('wb') as log:
                    proc=OwnedProcess(build_command(str(local),str(out)),log)
                    try:returncode=proc.wait(180)
                    except BaseException:
                        recover_decompiler(work,work.name,before)
                        raise
                if returncode:
                    recover_decompiler(work,work.name,before)
                    raise ValueError('反编译器退出异常，详见 decompile.log')
                generated={p.relative_to(out).as_posix() for p in out.rglob('*.java')}
                expected={name.split('$')[0]+'.java' if '$' in name else name[:-6]+'.java' for name in classes}
                missing=sorted(expected-generated)
                if missing:
                    result['diagnostics']=[{'file':name,'reason':'反编译未生成对应顶层源码'} for name in missing]
                    recover_decompiler(work,work.name,before)
                    raise ValueError('部分 Java 源码缺失，未继续打包')
                for name in sorted(generated):
                    dest=source/name
                    if dest.exists():raise ValueError('反编译源码与原资源路径冲突：'+name)
                    dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(out/name,dest)
            result['source_mode']='cfr';result['decompiled_files']=len(generated)
        else:result['source_mode']='embedded_java' if any(source.rglob('*.java')) else 'non_java_content'
        result['stage']='translation';progress('translation','正在实际转换、生成入口并检查打包条件')
        from run_translation_job import run_job
        task={'input':str(source),'output_root':str(work/'jobs'), 'partial_transformers':config.get('partial_transformers',True),
              'distribution':{'pack_id':info['mods'][0]['id'],'layout':'resources',
                              'items':'auto',
                              'platform_versions':{'minecraft':'1.21.1','neoforge':'21.1.233'}}}
        purpose=config.get('purpose','mod')
        if config.get('python2'):
            task['distribution']['python2']=config['python2']
        if purpose not in ('mod','library'):raise ValueError('处理用途应为 mod 或 library')
        if purpose=='library':task.pop('distribution')
        dependencies=config.get('dependency_artifacts',[])
        for record in dependencies:verify_dependency(record)
        for key in ('dependency_abis','optional_dependency_packages','defer_external_symbols'):
            if key in config:task[key]=config[key]
        if any(not Path(path).is_absolute() for path in task.get('dependency_abis',[])):raise ValueError('后台依赖 ABI 清单请填写绝对路径')
        task['dependency_abis']=task.get('dependency_abis',[])+[record['manifest'] for record in dependencies]
        if any(source.rglob('*.java')):
            task['export_dependency_abi']={'source_jar':str(jar),'version':info['mods'][0]['version'],'dependency_id':info['mods'][0]['id'],'neocore_abi':7}
        write_json(work/'translation.json',task)
        report=run_job(work/'translation.json');result['translation_report']=str(Path(report['output'])/'job_report.json')
        result['translation']=report.get('translation',{})
        result['content']=report.get('content',{})
        result['translated_dependencies']=report.get('translated_dependencies',[])
        if report.get('dependency_abi'):result['dependency_abi']=dependency_artifact(report['dependency_abi']['manifest'],Path(report['output'])/'converted'/source.name)
        result['purpose']=purpose
        result['pipeline']={'inspection':'COMPLETE','source_preparation':result['source_mode'],'conversion':report['status'],
            'dependency_abi':'EXPORTED' if result.get('dependency_abi') else 'NOT_AVAILABLE','packaging':report.get('packaging',''),
            'engine_verified':False}
        result['source_output']=str(Path(report['output'])/'converted'/source.name)
        result['diagnostics'] += result['translation'].get('skipped_optional',[]) + result['translation'].get('capability_blockers',[])
        for path in (Path(report['output'])/'converted').rglob('translation_report.json'):
            data=json.loads(path.read_bytes())
            result['diagnostics'] += [{k:row[k] for k in ('file','status','line','reason','details','missing_generated_dependencies') if k in row}
                for row in data.get('results',[]) if row.get('status')!='GENERATED_REVIEW_REQUIRED' or row.get('missing_generated_dependencies')]
        issues=[item for row in report.get('distribution',{}).get('contents',[]) for item in row.get('compatibility_issues',[])]
        item_reports=[row['item_content'] for row in report.get('distribution',{}).get('contents',[]) if row.get('item_content')]
        result['item_content']=item_reports
        result['item_registration']=report.get('item_registration')
        result['python2_executed']=report.get('python2_executed',False)
        result['diagnostics'] += [issue for row in item_reports for issue in row.get('issues',[])]
        if issues:
            result['diagnostics']+=issues
            report.update(status='TRANSLATION_INCOMPLETE',packaging='BLOCKED: content compatibility issues require review')
            result['pipeline'].update(conversion=report['status'],packaging=report['packaging'])
            write_json(Path(report['output'])/'job_report.json',report)
        if report['status']!='PACKAGED_REVIEW_REQUIRED':
            if fingerprint!=backend_fingerprint():raise ValueError('转换期间工具源码变化，请重试')
            if digest(jar)!=before:raise ValueError('导入副本发生变化，请重新导入')
            if report['status']=='FAILED':raise ValueError(report.get('error','后台处理失败'))
            output.parent.mkdir(parents=True,exist_ok=True)
            review_archive(temporary,report,result['source_output'],before,dependencies,
                hashlib.sha256(json.dumps(fingerprint,sort_keys=True).encode('utf-8')).hexdigest())
            status=report['status'];message=('非 Java 内容已原样保留；审查包不含网易行为包' if status=='CONTENT_STAGED_REVIEW_REQUIRED' else
                '已生成前置库 ABI 与源码审查包' if purpose=='library' and result.get('dependency_abi',{}).get('available_types') else
                '已生成源码审查包；仍有未满足的转换或打包条件')
            result.update(status=status,stage='complete',translated=False,content_staged=True,
                artifact_kind='SOURCE_REVIEW_ZIP',output=output.name,output_sha256=digest(temporary),
                message=message,tree='源码与资源审查包（不是网易测试 ZIP）\ntranslated_sources/\njava_context/\ncontent/\nreports/\ndependencies/')
            temporary.replace(output)
            write_json(work/'result.json',result)
            return result
        if fingerprint!=backend_fingerprint():raise ValueError('转换期间工具源码变化，请重试')
        result['stage']='archive';progress('archive','核对转换来源并生成待审查 ZIP')
        output.parent.mkdir(parents=True,exist_ok=True)
        archive_distribution(Path(report['output'])/'distribution',temporary,report['distribution'])
        if digest(jar)!=before:raise ValueError('导入副本发生变化，请重新导入')
        with zipfile.ZipFile(temporary) as zipped:
            names=zipped.namelist()
            tree='实际 ZIP 内容（前 100 项）\n'+'\n'.join(names[:100])
            if len(names)>100:tree+='\n… 共 '+str(len(names))+' 项'
        result.update(status='PACKAGED_REVIEW_REQUIRED',stage='complete',translated=True,
            artifact_kind='NETEASE_TEST_ZIP',
            output=output.name,output_sha256=digest(temporary),tree=tree,message='实际转换已完成，ZIP 待审查；尚未验证网易玩法')
        content_gaps=[issue for report_row in item_reports for issue in report_row.get('issues',[]) if issue.get('category')!='SOURCE_INVALID_TAG']
        result['item_content_complete'] = not content_gaps if item_reports else None
        if content_gaps:
            result['pipeline']['native_item_binding']='BLOCKED_UNCONVERTED_CONTENT_OR_BEHAVIOR'
            result['message']='已生成定义与资源候选；仍有明确的内容/行为缺口，运行时绑定将阻断，尚未验证网易玩法'
        elif any(row.get('blocks') for row in item_reports):
            result['pipeline']['native_block_binding']='AWAITING_ENGINE_DEFINITION_QUERY'
            result['message']='普通方块与资源测试包已生成；原件数据警告已保留，放置、挖掘、掉落及爆炸差异待网易实机验证'
        # Publish the download only after all checks succeed.
        temporary.replace(output)
    except Exception as error:
        temporary.unlink(missing_ok=True)
        result.update(status='TIMED_OUT' if isinstance(error,TimedOut) else 'BLOCKED',message=str(error) or type(error).__name__)
        (work/'failure.log').write_text(traceback.format_exc(),encoding='utf-8')
    write_json(work/'result.json',result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('request');args=parser.parse_args()
    request=json.loads(Path(args.request).read_bytes());work=Path(request['work'])
    os.environ['NEOCORE_OBSERVABILITY_DIR']=str(work)
    os.environ['NEOCORE_PARSE_JOB_CONTEXT']=hashlib.sha256(Path(args.request).read_bytes()+digest(request['jar']).encode()).hexdigest()
    sys.path.insert(0,str(Path(request['config']['dev_root']).resolve()))
    from translation_observer import event
    current=[None,time.perf_counter()]
    def progress(phase,message):
        now=time.perf_counter()
        if current[0]:event(current[0],'FINISHED',elapsed_seconds=now-current[1])
        current[:]=[phase,now];event(phase,'STARTED',message=message)
        write_json(work/'progress.json',{'phase':phase,'message':message})
    convert(request['jar'],work,request['output'],request['config'],progress)
    if current[0]:event(current[0],'FINISHED',elapsed_seconds=time.perf_counter()-current[1])


if __name__=='__main__':main()
