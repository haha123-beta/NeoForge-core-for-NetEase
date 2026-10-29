"""Mechanical source callback weaving for a fully validated same-content plan."""
from collections import defaultdict
import json
from pathlib import Path
from java_frontend import isolated_parse
from java_mixin_modify_arg import wrapper as modify_arg_wrapper
from java_mixin_plan import CALLBACK,MANIFEST,MixinPlanError,plan,digest,children,walk,text

def edits(raw,changes):
    last=len(raw)+1
    for start,end,replacement in sorted(changes,key=lambda r:(r[0],r[1]),reverse=True):
        if end>last:raise ValueError('Overlapping source weaving edits')
        raw=raw[:start]+replacement.encode('utf-8')+raw[end:];last=start
    return raw

def weave(root,contract):
    root=Path(root);groups=defaultdict(list);output={}
    for row in contract['injections']:groups[row['target_file']].append(row)
    for file,entries in groups.items():
        raw=(root/file).read_bytes();ir=isolated_parse(raw,file,[]);changes=[]
        for span in sorted({tuple(b['remove_final_span']) for b in contract.get('field_bindings',[]) if b['target_file']==file and b['remove_final_span']}):
            changes.append((span[0],span[1],''))
        methods=defaultdict(list);extra_handlers=[];call_changes=[]
        for row in entries:
            if row['at']=='MODIFY_ARG':
                for index,call in enumerate(row['calls']):
                    replacement,helper=modify_arg_wrapper(row,index)
                    start,end=call['span'];call_changes.append((start,end,replacement));extra_handlers.append(helper)
            else:methods[tuple(row['body_span'])].append(row)
        for index,(start,end,replacement) in enumerate(call_changes):
            if any(i!=index and not (end<=other_start or start>=other_end) for i,(other_start,other_end,_) in enumerate(call_changes)):
                raise MixinPlanError(file,'Nested/overlapping ModifyArg call sites require composed lowering')
        consumed_calls=set()

        def callbacks(rows,ret=None):
            code=[]
            for row in sorted(rows,key=lambda r:(-r['priority'],r['serial'])):
                name='_nc_mixin_cb_'+str(row['serial'])
                kind=CALLBACK+('CallbackInfo' if row['return_type']=='void' else 'CallbackInfoReturnable<java.lang.'+('Boolean' if row['return_type']=='boolean' else 'Integer')+'>')
                args=json.dumps(row['descriptor'].split('(',1)[0])+','+str(row['cancellable']).lower()
                if ret is not None and row['return_type']!='void':args+=','+ret
                code.append(kind+' '+name+'=new '+kind+'('+args+');')
                captured=row['parameter_names'] if row['capture_arguments'] else []
                code.append(row['handler']+'('+','.join(captured+[name])+');')
                code.append('if('+name+'.isCancelled()){'+('return;' if row['return_type']=='void' else 'return '+name+('.getReturnValueZ();' if row['return_type']=='boolean' else '.getReturnValueI();'))+'}')
            return ''.join(code)
        for span,rows in methods.items():
            heads=[r for r in rows if r['at']=='HEAD'];returns=[r for r in rows if r['at'] in ('RETURN','TAIL')]
            if heads:changes.append((span[0]+1,span[0]+1,callbacks(heads)))
            if returns:
                first=returns[0]
                for index,(start,end) in enumerate(first['return_spans']):
                    node=next(n for n in walk(ir['tree']) if n['kind']=='return_statement' and n['span']==[start,end])
                    if first['return_type']!='void':
                        value=next(c for c in children(node) if c['kind']!='return')
                        temp='_nc_mixin_result_'+str(first['serial'])+'_'+str(index)
                        vs,ve=value['span'];nested=[]
                        for number,(cs,ce,replacement) in enumerate(call_changes):
                            if vs<=cs and ce<=ve:
                                nested.append((cs-vs,ce-vs,replacement));consumed_calls.add(number)
                        expression=edits(raw[vs:ve],nested).decode('utf-8')
                        code='{'+first['return_type']+' '+temp+'='+expression+';'+callbacks(returns,temp)+'return '+temp+';}'
                    else:code='{'+callbacks(returns)+'return;}'
                    changes.append((start,end,code))
                if first['implicit_void_return']:changes.append((span[1]-1,span[1]-1,callbacks(returns)))
        changes.extend(change for number,change in enumerate(call_changes) if number not in consumed_calls)
        imports=set()
        handlers=list(extra_handlers)
        seen=set()
        for row in entries:
            mix_ir=isolated_parse((root/row['mixin_file']).read_bytes(),row['mixin_file'],[])
            imports.update(i['name'] for i in mix_ir['imports'] if not i['name'].startswith('org.spongepowered.asm.mixin.') or i['name'].startswith(CALLBACK))
            if row['handler'] not in seen:handlers.append(row['handler_source']);seen.add(row['handler'])
        # Imports are copied only after the planner checks package/name context.
        position=next((n['span'][1] for n in ir['tree']['children'] if n['kind']=='package_declaration'),0)
        if imports:changes.append((position,position,'\n'+''.join('import '+name+';\n' for name in sorted(imports))))
        cls=next(n for n in ir['tree']['children'] if n['kind']=='class_declaration')
        body=next(n for n in cls['children'] if n.get('field')=='body')
        changes.append((body['span'][1]-1,body['span'][1]-1,'\n'+'\n'.join(handlers)+'\n'))
        output[file]=edits(raw,changes)
    for binding in contract.get('native_bindings',[]):
        file=binding['mixin_file']
        if file in output:raise MixinPlanError(file,'Native and source-owned weaving overlap')
        output[file]=edits((root/file).read_bytes(),binding['source_edits'])
    return output

def validate(root,sources):
    root=Path(root);path=root/MANIFEST
    if not path.exists():return None
    proof=json.loads(path.read_text(encoding='utf-8-sig'))
    if proof.get('schema_version')!=1 or proof.get('scope')!='same_content_source_callbacks':raise ValueError('Invalid source weaving manifest')
    current=plan(root)
    if current is None or proof.get('plan')!=current:raise ValueError('Stale or incomplete source weaving plan')
    actual={name:digest(row['source'].encode('utf-8')) for name,row in sources.items()}
    if proof.get('generated_modules')!=actual:raise ValueError('Source weaving generated modules changed')
    return current
