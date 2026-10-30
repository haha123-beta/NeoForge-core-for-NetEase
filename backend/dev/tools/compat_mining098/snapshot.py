"""Portable source snapshot shared by candidate validation and release packing."""
from pathlib import Path
import re,shutil,os,subprocess
from .engine import DEV,save

def dependency_link(source,target):
    source=Path(source).resolve();target=Path(target).absolute()
    if not source.is_dir() or target.exists():raise ValueError('Dependency link needs an existing source and unused destination')
    if os.name=='nt':
        def quote(value):return "'"+str(value).replace("'","''")+"'"
        command='New-Item -ItemType Junction -Path '+quote(target)+' -Target '+quote(source)+' | Out-Null'
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True)
        if result.returncode:raise ValueError('Cannot reuse dependency directory: '+result.stderr.decode(errors='replace'))
    else:target.symlink_to(source,target_is_directory=True)
    if target.resolve()!=source:raise ValueError('Dependency link target mismatch')

def snapshot(out,validation_refs=False,reuse_dependencies=False,omit_paths=()):
    from workspace_paths import SCRIPTS_ROOT
    out=Path(out);dest=out/'backend/dev';dest.mkdir(parents=True,exist_ok=False)
    omitted=set(omit_paths)
    def ignore(directory,names):
        relative=Path(directory).relative_to(DEV) if Path(directory).is_relative_to(DEV) else None
        return [n for n in names if n=='__pycache__' or n.endswith(('.pyc','.pyo')) or relative is not None and (relative/n).as_posix() in omitted]
    for p in DEV.glob('*.py'):
        if p.name not in omitted:shutil.copyfile(p,dest/p.name)
    for name in ('java_import_index.json','java_frontend_requirements.txt','translation_job.example.json','translation_job.sample.json'):
        shutil.copyfile(DEV/name,dest/name)
    for folder in ('profiles','vendor','templates','examples','fixtures','tests'):
        if (DEV/folder).exists():
            if reuse_dependencies and folder=='vendor':dependency_link(DEV/folder,dest/folder)
            else:shutil.copytree(DEV/folder,dest/folder,ignore=ignore)
    for folder in ('compat_analyzer_091','compat_analyzer_092','compat_mining098','neocore_gui_090','neocore_gui_092'):
        target=dest/'tools'/folder;target.mkdir(parents=True)
        for p in (DEV/'tools'/folder).iterdir():
            if p.is_file() and p.suffix in ('.py','.md','.html','.cmd','.json'):shutil.copyfile(p,target/p.name)
    shutil.copytree(SCRIPTS_ROOT.parent,out/'backend/core',ignore=ignore)
    resource=SCRIPTS_ROOT.parent.parent/'resource_pack_kFreO1qQ'
    if resource.exists():shutil.copytree(resource,out/'backend/resource_pack_kFreO1qQ',ignore=ignore)
    wp=dest/'workspace_paths.py';text=wp.read_text(encoding='utf-8')
    text,n=re.subn(r'^PACK_ROOT = .+$','PACK_ROOT = DEV_ROOT.parent / "core"',text,flags=re.M)
    if n!=1:raise ValueError('Unexpected workspace path declaration')
    wp.write_text(text,encoding='utf-8')
    config=dict(dev_root=str(dest),python2=r'D:\NeoCore工具\python27_validation\runtime\python.exe')
    save(dest/'tools/neocore_gui_092/backend.json',config)
    if validation_refs:
        refs=Path(os.environ.get('NEOCORE_REFERENCE_ROOT',str(DEV/'references')))
        if not (refs/'minecraft-1.21.1/reference_manifest.json').is_file():
            raise ValueError('Pinned full-regression references missing; set NEOCORE_REFERENCE_ROOT to an existing reference collection')
        # Private validation fixtures, not part of the distributable. Several
        # existing Java-oracle tests require these original pinned references.
        if reuse_dependencies:dependency_link(refs,dest/'references')
        else:shutil.copytree(refs,dest/'references',ignore=ignore)
        builds=Path(os.environ.get('NEOCORE_VALIDATION_BUILD_ROOT',str(refs.parent/'builds')))
        (dest/'builds').mkdir()
        for name in ('ds_config.py','DS-03/official_evidence.json','DS-10/official_evidence.json'):
            source=builds/'deepseek_collaboration'/name
            if not source.is_file():raise ValueError('Pinned regression fixture missing: '+str(source))
            target=dest/'builds/deepseek_collaboration'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        shutil.copytree(builds/'deepseek_collaboration/DS-16',dest/'builds/deepseek_collaboration/DS-16',ignore=ignore)
        name='manaita_087/input/sen/manaita_plus_legacy/client/model/PerspectiveModelState.java'
        target=dest/'builds'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(builds/name,target)
        name='mixin_r75/input.json';target=dest/'builds'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(builds/name,target)
        python2=Path(os.environ.get('NEOCORE_PYTHON2',r'D:\NeoCore工具\python27_validation\runtime\python.exe'))
        if not python2.is_file():raise ValueError('Real Python 2 validation runtime missing: '+str(python2))
        if reuse_dependencies:
            (out/'backend/python27_validation').mkdir(exist_ok=True)
            dependency_link(python2.parent,out/'backend/python27_validation/runtime')
        else:shutil.copytree(python2.parent,out/'backend/python27_validation/runtime',ignore=ignore)
    return out
