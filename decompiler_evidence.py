"""Task-owned ASCII CFR workspace recovery, with checked cleanup targets."""
import json,shutil,tempfile
from pathlib import Path

def register(work,temporary,input_sha256):
    work=Path(work).resolve();temporary=Path(temporary).resolve()
    identity=dict(attempt=work.name,input_sha256=input_sha256)
    (temporary/'neocore_owner.json').write_text(json.dumps(identity),encoding='utf-8')
    (work/'external_workspace.json').write_text(json.dumps(dict(identity,path=str(temporary))),encoding='utf-8')

def recover(work,attempt,input_sha256):
    work=Path(work).resolve();record=work/'external_workspace.json'
    if not record.exists():return dict(status='NOT_CREATED')
    info=json.loads(record.read_bytes());target=Path(info['path']);temp_root=Path(tempfile.gettempdir()).resolve()
    expected=dict(attempt=attempt,input_sha256=input_sha256)
    if work.name!=attempt or {k:info.get(k) for k in expected}!=expected:raise ValueError('CFR workspace task mismatch')
    if target.is_symlink() or (hasattr(target,'is_junction') and target.is_junction()):raise ValueError('CFR workspace link refused')
    absolute=target.resolve()
    # Verify the absolute target immediately before any recursive removal.
    if absolute.parent!=temp_root or not absolute.name.startswith('neocore092_'+attempt+'_') or absolute==temp_root:
        raise ValueError('CFR cleanup target is not this task temporary directory')
    if not absolute.exists():return dict(status='ALREADY_RELEASED')
    if json.loads((absolute/'neocore_owner.json').read_bytes())!=expected:raise ValueError('CFR workspace owner marker mismatch')
    saved=[];source=absolute/'out';destination=work/'decompile_partial'
    if source.exists():
        for p in sorted(source.rglob('*')):
            if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()) or not p.resolve().is_relative_to(source.resolve()):raise ValueError('CFR evidence link/path refused')
            if not p.is_file() or p.suffix!='.java':continue
            relative=p.relative_to(source);out=destination/relative
            out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,out);saved.append(relative.as_posix())
    # It remains exactly one verified task directory under the OS temp root.
    if absolute.resolve().parent!=temp_root or absolute.is_symlink():raise ValueError('CFR cleanup target changed')
    shutil.rmtree(absolute)
    result=dict(status='PARTIAL_SOURCES_PRESERVED_AND_WORKSPACE_RELEASED',files=saved)
    (work/'decompiler_recovery.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

def release_parser_caches(work):
    root=Path(work).resolve();released=[]
    for target in root.glob('.parser_ir_cache_*'):
        absolute=target.resolve()
        if absolute.parent!=root or not absolute.name.startswith('.parser_ir_cache_') or target.is_symlink() or (hasattr(target,'is_junction') and target.is_junction()):
            raise ValueError('Parser cache cleanup target escaped task directory')
        if not target.is_dir():raise ValueError('Parser cache cleanup target is not a directory')
        shutil.rmtree(absolute);released.append(absolute.name)
    return released
