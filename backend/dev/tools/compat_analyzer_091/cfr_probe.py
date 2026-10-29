"""Separate process using the locked 0.9.0 parser, never its generator."""
import json,sys,zipfile,hashlib
from pathlib import Path

def main():
    lock=json.loads(Path(sys.argv[1]).read_text());sys.path.insert(0,str(Path(lock['frozen_release'])/'backend/dev'))
    from java_frontend import parse_source
    rows={}
    with zipfile.ZipFile(lock['inputs']['review_zip']['path']) as archive:
        for entry in sorted(archive.namelist()):
            if not entry.startswith('java_context/') or not entry.endswith('.java'):continue
            raw=archive.read(entry);name=entry[len('java_context/'):]
            ir=parse_source(raw,name,())
            declarations=[];calls=[];types=[];features=[]
            data=ir['source_utf8'].encode('utf-8')
            def walk(node):
                kind=node['kind'];text=data[node['span'][0]:node['span'][1]].decode('utf-8')
                if kind in ('class_declaration','interface_declaration','record_declaration','enum_declaration','annotation_type_declaration'):
                    child=next((c for c in node.get('children',[]) if c.get('field')=='name'),None)
                    if isinstance(child,dict):declarations.append(data[child['span'][0]:child['span'][1]].decode())
                if kind=='method_invocation':
                    child=next((c for c in node.get('children',[]) if c.get('field')=='name'),None)
                    if isinstance(child,dict):calls.append({'name':data[child['span'][0]:child['span'][1]].decode(),'line':node['line']})
                if kind in ('type_identifier','scoped_type_identifier'):types.append({'text':text,'line':node['line']})
                if kind in ('lambda_expression','method_reference','switch_expression','record_declaration','generic_type','try_with_resources_statement','synchronized_statement','annotation','marker_annotation'):
                    features.append({'kind':kind,'line':node['line']})
                for child in node.get('children',[]):walk(child)
            # IR retains the lossless CST under tree; refuse a silently empty probe.
            tree=ir.get('tree') or ir.get('root')
            if tree is None:raise ValueError('Locked parser tree schema changed: '+str(ir.keys()))
            walk(tree)
            rows[name]={'sha256':hashlib.sha256(raw).hexdigest(),'parse_status':ir['parse_status'],'declarations':declarations,
                'method_invocations':calls,'types':types,'features':features,'imports':ir.get('imports',[]),'syntax_errors':ir.get('syntax_errors',[])}
    Path(sys.argv[2]).write_text(json.dumps(rows,sort_keys=True,ensure_ascii=True,indent=2),encoding='utf-8')
    print('CFR_CST_FILES',len(rows))
if __name__=='__main__':main()
