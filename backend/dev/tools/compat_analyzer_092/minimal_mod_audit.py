"""Generic original-JAR M0 audit. No mod IDs or production exceptions."""
import argparse,json,sys,zipfile
from pathlib import Path
from resolution import Index,SHARED
from abi import load_index
from classfile import read
from locking import digest,load,save,verify

def main():
    p=argparse.ArgumentParser();p.add_argument('jar',type=Path);p.add_argument('backend_report',type=Path);p.add_argument('evidence091',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();lock=load(a.evidence091/'versions.lock.json');verify(lock)
    report=load(a.backend_report);sha=digest(a.jar)
    if report['result']['input_sha256']!=sha:raise ValueError('Backend and original JAR identity mismatch')
    abi=load_index(a.evidence091/'official_abi.json.gz');facts=[];resources=[]
    with zipfile.ZipFile(a.jar) as z:
        for name in sorted(z.namelist()):
            if name.endswith('.class'):
                row=read(z.read(name));row['origin']=dict(artifact='original_mod',sha256=sha,entry=name);facts.append(row)
            elif not name.endswith('/'):resources.append(dict(path=name,size=len(z.read(name)),sha256=__import__('hashlib').sha256(z.read(name)).hexdigest()))
    project={r['name']:r for r in facts};index=Index(dict(abi['classes'],**project))
    byfile={r['file']:r for r in report['source_reports'][0]['results']};files={}
    exports=load(Path(lock['frozen_release'])/'backend/dev/java_import_index.json')['java_types']
    for row in facts:
        name=row['name'].rpartition('.')[0].replace('.','/')+'/'+row['source_file']
        entry=files.setdefault(name,dict(backend=byfile[name],classes=[],requirements=[],members=[],unknown_frontier=byfile[name]['status']=='MANUAL_REVIEW'))
        entry['classes'].append(row['name'])
        for t in row['type_references']:
            if t in project:entry['requirements'].append(dict(type=t,kind='PROJECT',source_file=project[t]['source_file']))
            else:
                provider=index.type(t)
                entry['requirements'].append(dict(type=t,official_status=provider['status'],official_origin=provider.get('definition',{}).get('origin'),
                    production_export=t.replace('$','.') in exports or t in exports,production_behavior='NOT_VERIFIED'))
        for ref in row['member_references']:
            entry['members'].append(dict(ref,resolution=index.member(ref['owner'],ref['name'],ref['descriptor'],ref['kind'])))
    result=dict(schema_version=1,original_jar_sha256=sha,files=files,class_facts=facts,resources=resources,
        milestones={'M0':'STATIC_EVIDENCE_COLLECTED_NOT_FULL_EXECUTION_PROOF','M1':'NOT_PASSED','M2':'NOT_PASSED','M3':'NOT_VERIFIED','M4':'NOT_VERIFIED'},
        unknowns=['Later compiler blockers','Holder binding and event lifecycle execution','Actual game fuel dispatch','Resource format conversion and engine gameplay'],
        official_profile=lock['target'],engine_verified=False)
    save(a.output,result);assert digest(a.jar)==sha;verify(lock)
    print(json.dumps(dict(files=len(files),classes=len(facts),sha256=sha)))
if __name__=='__main__':main()
