"""Validated dependency handoff and review archives, separate from engine packs."""
import hashlib,json,zipfile,re
from pathlib import Path

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def dependency_artifact(manifest_path,source_root):
    path=Path(manifest_path).resolve();manifest=json.loads(path.read_bytes())
    return {'manifest':str(path),'source_root':str(Path(source_root).resolve()),'manifest_sha256':digest(path),
        'dependency_id':manifest['dependency_id'],'version':manifest['version'],'source_jar_sha256':manifest['source_jar_sha256'],
        'available_types':sum(bool(row['implementation_available'] and row['abi_complete']) for row in manifest['types'].values()),
        'declared_types':len(manifest['types']),'requires_translated_dependencies':manifest.get('requires_translated_dependencies',[]),'engine_verified':False}

def verify_dependency(record):
    path=Path(record['manifest']);original_root=Path(record['source_root']);root=original_root.resolve()
    if path.is_symlink() or not path.is_file() or digest(path)!=record['manifest_sha256']:raise ValueError('前置库 ABI 清单缺失或已变化，请重新转换前置库')
    if not root.is_dir() or original_root.is_symlink() or getattr(original_root,'is_junction',lambda:False)():raise ValueError('前置库生成目录缺失或为链接')
    manifest=json.loads(path.read_bytes())
    if manifest['dependency_id']!=record['dependency_id'] or manifest['source_jar_sha256']!=record['source_jar_sha256']:raise ValueError('前置库来源与清单不一致')
    if not re.fullmatch(r'[a-z][a-z0-9_.-]*',manifest['dependency_id']):raise ValueError('前置库标识不合法')
    checked={}
    for identity,row in manifest['types'].items():
        if not(row['implementation_available'] and row['abi_complete']):continue
        relative=Path(row['source_record']['file']).with_suffix('.py');module=root/relative
        if relative.is_absolute() or '..' in relative.parts or not module.resolve().is_relative_to(root):raise ValueError('前置库模块路径不安全')
        cursor=module
        while cursor!=root:
            if cursor.is_symlink() or getattr(cursor,'is_junction',lambda:False)():raise ValueError('前置库模块路径包含链接')
            cursor=cursor.parent
        if not module.is_file() or digest(module)!=row['python_sha256']:raise ValueError('前置库生成模块缺失或已变化：'+identity)
        checked[relative.as_posix()]=module
    if not checked:raise ValueError('前置库还没有可用的已生成类型')
    return manifest,checked

def review_archive(output,report,source_root,source_sha256,dependencies=(),backend_sha256=None):
    output=Path(output);job=Path(report['output']);source_root=Path(source_root)
    manifest={'schema_version':1,'artifact_kind':'SOURCE_REVIEW_ZIP','translation_status':report['status'],
        'input_jar_sha256':source_sha256,'engine_verified':False,'netease_pack':False,
        'backend_fingerprint_sha256':backend_sha256,
        'limits':['Review material only; original resources have not been mapped to NetEase schemas.'],
        'dependencies':[{'dependency_id':r['dependency_id'],'version':r['version'],'source_jar_sha256':r['source_jar_sha256']} for r in dependencies]}
    seen=set()
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED) as archive:
        def add(path,name):
            if name in seen:raise ValueError('审查包路径冲突：'+name)
            if path.is_symlink() or getattr(path,'is_junction',lambda:False)():raise ValueError('审查包不接受文件链接')
            seen.add(name);archive.write(path,name)
        for path in sorted(source_root.rglob('*.py')):add(path,'translated_sources/'+path.relative_to(source_root).as_posix())
        for path in sorted(source_root.rglob('*.java')):add(path,'java_context/'+path.relative_to(source_root).as_posix())
        content=job/'content'
        if content.is_dir():
            for path in sorted(content.rglob('*')):
                if path.is_file():add(path,'content/'+path.relative_to(content).as_posix())
        for path in [job/'job_report.json',job/'dependency_abi.json',job/'converted/translation_report.json',job/'converted/manual_review.txt',job/'converted/failures.log']:
            if path.is_file():add(path,'reports/'+path.name)
        for record in dependencies:
            _,modules=verify_dependency(record);prefix='dependencies/'+record['dependency_id']+'/'
            add(Path(record['manifest']),prefix+'dependency_abi.json')
            for relative,path in modules.items():add(path,prefix+'translated_sources/'+relative)
        archive.writestr('review_manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8'))
        archive.writestr('阅读说明.md','# 源码与资源审查包\n\n这不是网易行为包。translated_sources保留实际生成的Python；java_context是对应原Java上下文；content是原样保留内容；reports包含完整阻断与ABI报告。依赖保持独立目录，不并入核心。\n'.encode('utf-8'))
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():raise ValueError('审查包校验失败')
    return manifest
