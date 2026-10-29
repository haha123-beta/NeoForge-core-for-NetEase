"""0.9.2 read-only evidence corrections; shares the 0.9.1 parser and locks."""
import argparse,hashlib,html,json,sys
from pathlib import Path
from resolution import Index,SHARED
from refine import refine
from bytecode_compare import observations
from locking import load,save,verify,digest
from abi import load_index
from classfile import read,descriptor_types
import analysis
from ranking import rank

def source_hashes():
    return {str(p.relative_to(SHARED.parent)):digest(p) for directory in (SHARED,Path(__file__).parent)
            for p in sorted(directory.rglob('*.py'))}

def normalize_read(raw,**kwargs):
    row=read(raw,**kwargs)
    # CP member owners can be arrays (e.g. enum values().clone()). Their
    # component types are dependencies, never an independent third-party ABI.
    types=set()
    for name in row['type_references']:
        if name.startswith('['):types.update(descriptor_types(name.replace('.','/')))
        else:types.add(name)
    types.discard(row['name']);row['type_references']=sorted(types)
    return row

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('evidence091',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();lock=load(a.evidence091/'versions.lock.json');verify(lock)
    a.output.mkdir(parents=True,exist_ok=False);save(a.output/'versions.lock.json',lock)
    before=source_hashes();old=load(a.evidence091/'analysis.json')
    # Module-local substitutions are confined to this standalone process.
    # No compiler/runtime imports or descriptor overrides are installed.
    analysis.Index=Index;analysis.read=normalize_read
    graph=refine(analysis.analyze(lock,load_index(a.evidence091/'official_abi.json.gz'),load(a.evidence091/'cfr_index.json')))
    ranking=rank(graph);save(a.output/'analysis.json',graph);save(a.output/'ranking.json',ranking)
    save(a.output/'bytecode_observations.json',observations(graph['class_facts']))
    oldmembers={ (r['owner'],r['name'],r['descriptor'],r['kind']):r['resolution'] for r in old['member_resolutions'] }
    def meaning(r):return {k:r.get(k) for k in ('status','declaring_type','member','candidates','unresolved_ancestors')}
    changed=[dict(symbol={k:r[k] for k in ('owner','name','descriptor','kind')},before=oldmembers.get((r['owner'],r['name'],r['descriptor'],r['kind'])),after=r['resolution'])
             for r in graph['member_resolutions'] if meaning(oldmembers.get((r['owner'],r['name'],r['descriptor'],r['kind']),{}))!=meaning(r['resolution'])]
    save(a.output/'resolution_differences.json',dict(changes=changed,dispatch_access_initialization='NOT_VERIFIED'))
    table=[]
    for n,r in graph['files'].items():
        if r['baseline_status']=='MANUAL_REVIEW':table.append('<tr><td>'+html.escape(n)+'</td><td>'+html.escape(r['baseline_diagnostic']['reason'])+'</td><td>'+html.escape(', '.join(r['measured_blockers']))+'</td></tr>')
    body='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
    body+='<title>NeoCore 0.9.2 诊断审计</title><style>body{font:15px system-ui;margin:30px}td{border:1px solid #ccc;padding:8px;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%}pre{white-space:pre-wrap}</style>'
    body+='<h1>NeoCore 0.9.2 诊断审计</h1><p>冻结 0.9.0：32/130。以下仍为静态预测；新生成、Python2执行、网易验证分别计量。九个泛型诊断按真实父类拆分，引用链见 nine_file_audit.json。没有生产字节码锚点。</p>'
    body+='<h2>候选集合（预测）</h2><pre>'+html.escape(json.dumps(ranking['greedy_sets'],ensure_ascii=False,indent=2))+'</pre><h2>逐文件原始诊断及修复组</h2><table>'+''.join(table)+'</table>'
    (a.output/'report.html').write_text(body,encoding='utf-8')
    verify(lock);assert before==source_hashes(),'Tool sources changed during run'
    save(a.output/'run_manifest.json',dict(version='0.9.2',status='PASSED',sources=before,
        shared_parser='compat_analyzer_091/classfile.py',frozen_inputs_unchanged=True,
        generation_baseline='32/130',engine_verified=False,production_overrides=0,
        outputs={f.name:digest(f) for f in sorted(a.output.iterdir()) if f.is_file()}))
    print(json.dumps(dict(status='PASSED',nodes=len(graph['blocker_nodes']),method_resolution_differences=len(changed)),ensure_ascii=True))

if __name__=='__main__':main()
