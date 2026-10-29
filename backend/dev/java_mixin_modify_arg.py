"""Source-owned ModifyArg plans with explicit subject identity and evaluation-order wrappers."""
import re
from java_mixin_types import identity as type_identity,method_descriptor

MODIFY_ARG='org.spongepowered.asm.mixin.injection.ModifyArg'


def build(ir,cls,target_ir,target_cls,member,method,ann,default_require,project_types,load,context):
    from java_mixin_plan import arguments,literal,singleton,identity,AT,field,children,text,walk,MixinPlanError
    def error(reason):raise MixinPlanError(ir['origin'],reason)
    options=arguments(ir,ann,{'method','at','index','require'})
    selector=literal(ir,singleton(ir,options.get('method'),'ModifyArg.method'),str)
    at=options.get('at')
    if at is None or at['kind']!='annotation' or identity(ir,at)!=AT:error('ModifyArg requires one explicit @At')
    point=arguments(ir,at,{'value','target'})
    if literal(ir,point.get('value'),str)!='INVOKE':error('ModifyArg requires INVOKE')
    subject_selector=literal(ir,point.get('target'),str)
    match=re.fullmatch(r'L([\w/$]+);([\w$]+)(\([^)]*\).+)',subject_selector)
    if match is None:error('ModifyArg subject requires full owner/name/descriptor')
    owner=match[1].replace('/','.').replace('$','.')
    unit={'_project_types':project_types}
    owner_context=dict(target_cls,imports=target_ir['imports'],package=target_ir['package'])
    def desc(m):return method_descriptor(m,owner_context,unit)
    candidates=[m for m in target_cls['methods'] if not m['constructor'] and (desc(m)==selector if '(' in selector else m['name']==selector)]
    if len(candidates)!=1:error('ModifyArg target selector must match exactly one source method')
    selected=candidates[0];body=selected['body']
    if desc(selected) is None:error('ModifyArg target descriptor has unresolved types')
    if body is None or any(p['varargs'] for p in selected['parameters']):error('ModifyArg target needs a concrete fixed-arity method')
    if any(n['kind'] in ('lambda_expression','method_reference','class_declaration','try_statement','try_with_resources_statement','synchronized_statement','for_statement','enhanced_for_statement','while_statement','do_statement') for n in walk(body)):
        error('ModifyArg target control flow needs further review')
    subject_ir,subject_cls=load(owner)
    family=[m for m in subject_cls['methods'] if not m['constructor'] and m['name']==match[2]]
    subject_context=dict(subject_cls,imports=subject_ir['imports'],package=subject_ir['package'])
    if len(family)!=1 or method_descriptor(family[0],subject_context,unit)!=match[2]+match[3]:error('ModifyArg subject overload/descriptor requires exact unique declaration')
    subject=family[0]
    if any(p['varargs'] for p in subject['parameters']):error('ModifyArg subject varargs requires lowering')
    if owner!=target_cls['java_name'] and ('public' not in subject['modifiers'] or 'public' not in subject_cls['modifiers']):error('ModifyArg external subject must be public')
    mods=next((c for c in member['children'] if c['kind']=='modifiers'),{})
    if 'private' not in [c['kind'] for c in mods.get('children',[])] or method['static']!=selected['static']:error('ModifyArg requires private handler matching target staticness')
    handler_context=dict(cls,imports=ir['imports'],package=ir['package'])
    try:
        params=[type_identity(p['declared_type'],subject_context,unit) for p in subject['parameters']]
        handler_params=[type_identity(p['declared_type'],handler_context,unit) for p in method['parameters']]
        returned=type_identity(method['return_type'],handler_context,unit)
    except ValueError as e:error('ModifyArg unresolved type identity: '+str(e))
    index=literal(ir,options['index'],int) if 'index' in options else None
    if index is None:
        possible=[i for i,kind in enumerate(params) if kind==returned]
        if len(possible)!=1:error('ModifyArg index is ambiguous or absent')
        index=possible[0]
    if index<0 or index>=len(params) or params[index]!=returned:error('ModifyArg index/return type differs from subject argument')
    if any(p['varargs'] for p in method['parameters']) or handler_params not in ([returned],params):error('ModifyArg handler must consume selected argument or all subject arguments')
    capture_all=handler_params==params and len(params)>1
    locals_={p['name']:p['declared_type'] for p in selected['parameters']}
    for node in walk(body):
        if node['kind']=='local_variable_declaration':
            declared=text(target_ir,field(node,'type'))
            for variable in children(node):
                if variable['kind']=='variable_declarator':
                    name=text(target_ir,field(variable,'name'))
                    if name in locals_:error('ModifyArg local shadowing requires lexical binding')
                    locals_[name]=declared
    calls=[]
    for node in walk(body):
        if node['kind']!='method_invocation' or text(target_ir,field(node,'name'))!=match[2]:continue
        receiver=field(node,'object');spelling=text(target_ir,receiver) if receiver else 'this'
        type_receiver=False
        if spelling=='this':receiver_owner=target_cls['java_name']
        elif receiver and receiver['kind'] in ('identifier','scoped_identifier'):
            if spelling in locals_:raw=locals_[spelling]
            else:raw=spelling;type_receiver=True
            try:receiver_owner=type_identity(raw,owner_context,unit).split('<',1)[0]
            except ValueError:error('ModifyArg same-name invocation receiver is unresolved')
        else:error('ModifyArg effectful/compound receiver requires explicit evaluation lowering')
        if receiver_owner!=owner:continue
        args=children(field(node,'arguments'))
        if len(args)!=len(params):error('ModifyArg invocation arity differs')
        if type_receiver!=subject['static']:error('ModifyArg static/instance subject receiver differs')
        calls.append({'span':node['span'],'receiver':None if subject['static'] else spelling,'arguments':[text(target_ir,a) for a in args]})
    require=literal(ir,options['require'],int) if 'require' in options else default_require
    if not calls or len(calls)<require:error('ModifyArg call-site match count does not satisfy require')
    raw=text(ir,member);start=member['span'][0];a,b=ann['span'];raw=raw[:a-start]+raw[b-start:]
    return dict(context,selector=selector,descriptor=desc(selected),handler=method['name'],handler_source=raw,
                at='MODIFY_ARG',body_span=body['span'],return_type=selected['return_type'],constructor=False,static=selected['static'],
                subject_owner=owner,subject_name=subject['name'],subject_static=subject['static'],subject_parameters=params,
                subject_return=type_identity(subject['return_type'],subject_context,unit),argument_index=index,
                capture_subject_arguments=capture_all,calls=calls,matches=len(calls),require=require)


def wrapper(row,number):
    """All original arguments evaluate before the handler, including arguments after its index."""
    name='_nc_mixin_invoke_'+str(row['serial'])+'_'+str(number)
    names=['_nc_mixin_arg_'+str(i) for i in range(len(row['subject_parameters']))]
    render=lambda kind:kind.replace('?extends','? extends ').replace('?super','? super ')
    declarations=[render(kind)+' '+name for kind,name in zip(row['subject_parameters'],names)]
    args=list(row['calls'][number]['arguments'])
    if not row['subject_static']:
        declarations.insert(0,row['subject_owner']+' _nc_mixin_receiver')
        args.insert(0,row['calls'][number]['receiver'])
    chosen=names[row['argument_index']]
    handler_args=names if row['capture_subject_arguments'] else [chosen]
    invoke=(row['subject_owner'] if row['subject_static'] else '_nc_mixin_receiver')+'.'+row['subject_name']+'('+','.join(names)+')'
    code='private '+('static ' if row['static'] else '')+render(row['subject_return'])+' '+name+'('+','.join(declarations)+'){'+chosen+'='+row['handler']+'('+','.join(handler_args)+');'+('' if row['subject_return']=='void' else 'return ')+invoke+';}'
    return name+'('+','.join(args)+')',code
