"""Explicit source-owned callback injection plans; no JVM/native transformations."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tomllib
from java_frontend import isolated_parse
from java_symbols import declarations
from java_method_overloads import canonical
from java_mixin_fields import bind_fields,check_handler
from workspace_paths import SCRIPTS_ROOT

from java_mixin_modify_arg import MODIFY_ARG,build as modify_arg_plan

MIXIN='org.spongepowered.asm.mixin.Mixin'
INJECT='org.spongepowered.asm.mixin.injection.Inject'
AT='org.spongepowered.asm.mixin.injection.At'
CALLBACK='org.spongepowered.asm.mixin.injection.callback.'
MANIFEST='_nc_source_weave.json'

class MixinPlanError(ValueError):
    def __init__(self,source,reason):
        self.source=source;self.reason=reason
        super().__init__(source+': '+reason)

def digest(value):return hashlib.sha256(value).hexdigest()
def field(node,name):return next((c for c in node.get('children',[]) if c.get('field')==name),None)
def walk(node):
    yield node
    for c in node.get('children',[]):yield from walk(c)
def children(node):return [c for c in (node or {}).get('children',[]) if c['kind'] not in ('(',')','{','}',',',';','line_comment','block_comment')]
def text(ir,node):return ir['source_utf8'].encode('utf-8')[node['span'][0]:node['span'][1]].decode('utf-8')
def annotations(node):
    mods=next((c for c in node.get('children',[]) if c['kind']=='modifiers'),{})
    return [c for c in mods.get('children',[]) if c['kind'] in ('annotation','marker_annotation')]
def identity(ir,node):
    name=text(ir,field(node,'name'))
    names=[i['name'] for i in ir['imports'] if not i['static'] and not i['wildcard'] and i['name'].rsplit('.',1)[-1]==name]
    return name if '.' in name else names[0] if len(names)==1 else None

def arguments(ir,node,allowed):
    result={}
    for c in children(field(node,'arguments')):
        key=text(ir,field(c,'key')) if c['kind']=='element_value_pair' else 'value'
        if key not in allowed or key in result:raise MixinPlanError(ir['origin'],'Unsupported/duplicate annotation option: '+key)
        result[key]=field(c,'value') if c['kind']=='element_value_pair' else c
    return result

def literal(ir,node,kind):
    if node is None:raise MixinPlanError(ir['origin'],'Missing annotation value')
    raw=text(ir,node)
    if kind is str and node['kind']=='string_literal' and chr(92) not in raw:return ast.literal_eval(raw)
    if kind is bool and raw in ('true','false'):return raw=='true'
    if kind is int and re.fullmatch(r'[0-9]+',raw):return int(raw)
    raise MixinPlanError(ir['origin'],'Annotation requires a direct '+kind.__name__+' literal')


def singleton(ir,node,label):
    """Normalize only annotation members whose Java contract is an array."""
    if node is not None and node['kind']=='element_value_array_initializer':
        values=children(node)
        if len(values)!=1:raise MixinPlanError(ir['origin'],label+' requires exactly one element; multiple targets/sites need separate planning')
        return values[0]
    return node

def config_requirements(root):
    spec=importlib.util.spec_from_file_location('_mixin_metadata',SCRIPTS_ROOT/'core/alpha_neoforge.py')
    metadata=importlib.util.module_from_spec(spec);spec.loader.exec_module(metadata)
    toml=root/'META-INF/neoforge.mods.toml'
    if not toml.exists():toml=root/'META-INF/mods.toml'
    data=tomllib.loads(toml.read_text(encoding='utf-8-sig')) if toml.exists() else {}
    return metadata.inspect_bytecode_requirements(str(root),data)

def descriptor(method,owner,unit):
    from java_mixin_types import method_descriptor
    return method_descriptor(method,owner,unit)


def plan(root,project_types=None,requirements=None):
    root=Path(root);issues=config_requirements(root) if requirements is None else requirements
    if not issues:return None
    for issue in issues:
        if issue['kind']!='mixin':raise MixinPlanError(issue['source'],'Bytecode transformer remains unsupported')
    configs=[];listed=[]
    for issue in issues:
        name=issue['source'];path=(root/name).resolve()
        if root.resolve() not in path.parents or not path.is_file():raise MixinPlanError(name,'Missing/escaping config')
        try:config=json.loads(path.read_text(encoding='utf-8-sig'))
        except Exception as e:raise MixinPlanError(name,'Unreadable config: '+str(e))
        allowed={'required','minVersion','compatibilityLevel','package','mixins','injectors','refmap'}
        if not isinstance(config,dict) or set(config)-allowed:raise MixinPlanError(name,'Plugin, side lists or unknown config options require review')
        from java_mixin_refmap import inspect as inspect_refmap
        refmap=inspect_refmap(root,config,name)
        package=config.get('package');names=config.get('mixins')
        if not isinstance(package,str) or not re.fullmatch(r'[A-Za-z_]\w*(\.[A-Za-z_]\w*)*',package) or not isinstance(names,list) or not names:
            raise MixinPlanError(name,'Explicit package and nonempty common mixins list required')
        if 'required' in config and type(config['required']) is not bool:raise MixinPlanError(name,'Invalid required flag')
        if config.get('minVersion','0.8.7') not in ('0.8','0.8.7'):raise MixinPlanError(name,'Unreviewed Mixin minimum version')
        if config.get('compatibilityLevel','JAVA_21') not in ('JAVA_8','JAVA_9','JAVA_10','JAVA_11','JAVA_16','JAVA_17','JAVA_18','JAVA_21'):raise MixinPlanError(name,'Unreviewed Java compatibility level')
        injector=config.get('injectors',{})
        if not isinstance(injector,dict) or set(injector)-{'defaultRequire'}:raise MixinPlanError(name,'Unsupported injector config')
        require=injector.get('defaultRequire',1)
        if type(require) is not int or require<0:raise MixinPlanError(name,'Invalid defaultRequire')
        for cls in names:
            if not isinstance(cls,str) or not re.fullmatch(r'[A-Za-z_]\w*',cls):raise MixinPlanError(name,'Only direct top-level mixin classes supported')
            java=package+'.'+cls
            if any(row[1]==java for row in listed):raise MixinPlanError(name,'Duplicate configured mixin: '+java)
            listed.append((name,java,require))
        configs.append({'file':name,'sha256':digest(path.read_bytes()),'config':config,'reference_map':refmap})
    if project_types is None:
        from java_project_types import add_unit
        project_types={}
        for path in sorted(root.rglob('*.java')):add_unit(project_types,isolated_parse(path.read_bytes(),path.relative_to(root).as_posix(),[]))
    if any(name in (MIXIN,INJECT,AT,MODIFY_ARG,'org.spongepowered.asm.mixin.Shadow','org.spongepowered.asm.mixin.Final','org.spongepowered.asm.mixin.Mutable') or name.startswith(CALLBACK) for name in project_types):raise MixinPlanError('source','Mixin API identity is shadowed by source')
    cached={}
    def load(java):
        rows=project_types.get(java,[])
        if len(rows)!=1 or not rows[0]['layout_matches_package'] or len(rows[0]['attribute_chain'])!=1:raise MixinPlanError(java,'Unique project source target with canonical layout required')
        record=rows[0];file=record['file']
        if file not in cached:
            ir=isolated_parse((root/file).read_bytes(),file,[])
            classes=declarations(ir)['classes']
            cls=next((c for c in classes if c['java_name']==java),None)
            if len(classes)!=1:raise MixinPlanError(file,'One top-level source class per file required')
            if '_nc_mixin_' in ir['source_utf8']:raise MixinPlanError(file,'Reserved generated injection identifier collision')
            if cls is None or cls['kind']!='class_declaration' or cls['superclass'] or cls['interfaces']:raise MixinPlanError(file,'Only direct source class without inheritance supported')
            cached[file]=(ir,cls)
        return cached[file]
    entries=[];mixin_files=[];used_names={};field_bindings=[];native_bindings=[]
    for config_name,java,default_require in listed:
        ir,cls=load(java);mixin_files.append(ir['origin'])
        node=next(n for n in ir['tree']['children'] if n['kind']=='class_declaration')
        anns=annotations(node)
        if len(anns)!=1 or identity(ir,anns[0])!=MIXIN:raise MixinPlanError(ir['origin'],'Configured class requires exactly @Mixin')
        args=arguments(ir,anns[0],{'value','priority'})
        value=singleton(ir,args.get('value'),'Mixin.value')
        if value is None or value['kind']!='class_literal':raise MixinPlanError(ir['origin'],'Single source class literal target required')
        target=canonical(text(ir,children(value)[0]),dict(cls,external=True,imports=ir['imports'],package=ir['package']),{'_project_types':project_types})
        if target not in project_types:
            from java_mixin_native import build as native_plan
            native_bindings.append(native_plan(ir,cls,node,target,config_name,default_require,project_types))
            continue
        target_ir,target_cls=load(target)
        if target in [j for _,j,_ in listed]:raise MixinPlanError(ir['origin'],'Mixin target cannot itself be a Mixin class')
        if ir['package']!=target_ir['package'] and 'public' not in target_cls['modifiers']:raise MixinPlanError(ir['origin'],'Cross-package target must be public')
        bindings=bind_fields(ir,cls,target_ir,target_cls,node,project_types)
        field_bindings.extend(bindings)
        if any(i['kind']!='field' for i in cls['initialization_order']) or any(m['constructor'] for m in cls['methods']):raise MixinPlanError(ir['origin'],'Mixin constructors or initializers unsupported')
        if any(i['static'] or i['wildcard'] for i in ir['imports']):raise MixinPlanError(ir['origin'],'Mixin wildcard/static imports require context lowering')
        if any(i['static'] or i['wildcard'] for i in target_ir['imports']):raise MixinPlanError(ir['origin'],'Target wildcard/static import context requires separate binding review')
        target_bindings={i['name'].rsplit('.',1)[-1]:i['name'] for i in target_ir['imports'] if not i['static'] and not i['wildcard']}
        for imp in ir['imports']:
            simple=imp['name'].rsplit('.',1)[-1]
            if any(n['kind'] in ('type_identifier','identifier') and text(target_ir,n)==simple for n in walk(target_ir['tree'])):
                prior=canonical(simple,dict(target_cls,external=True,imports=target_ir['imports'],package=target_ir['package']),{'_project_types':project_types})
                if prior!=imp['name']:raise MixinPlanError(ir['origin'],'Handler import would change target implicit type/name binding: '+simple)
            if simple in target_bindings and target_bindings[simple]!=imp['name']:raise MixinPlanError(ir['origin'],'Handler import conflicts with target context')
        priority=literal(ir,args['priority'],int) if 'priority' in args else 1000
        members=[m for m in children(field(node,'body')) if m['kind']=='method_declaration']
        if not members or len(members)!=len(cls['methods']):raise MixinPlanError(ir['origin'],'Only injection handler methods supported')
        for index,member in enumerate(members):
            method=cls['methods'][index];anns=annotations(member)
            if method['body'] is not None:check_handler(ir,cls,target_ir,target_cls,method,bindings,project_types)
            if method['body'] and any(n['kind'] in ('type_identifier','identifier') and text(ir,n) in {j.rsplit('.',1)[-1] for _,j,_ in listed} for n in walk(method['body'])):
                raise MixinPlanError(ir['origin'],'Handler references a standalone Mixin class')
            if len(anns)==1 and identity(ir,anns[0])==MODIFY_ARG:
                names=used_names.setdefault(target,{m['name'] for m in target_cls['methods']}|{f['name'] for f in target_cls['fields']})
                if method['name'] in names:raise MixinPlanError(ir['origin'],'Handler member collision: '+method['name'])
                names.add(method['name'])
                context={'config':config_name,'mixin':java,'mixin_file':ir['origin'],'target':target,'target_file':target_ir['origin'],'priority':priority,'serial':len(entries)}
                entries.append(modify_arg_plan(ir,cls,target_ir,target_cls,member,method,anns[0],default_require,project_types,load,context))
                continue
            if len(anns)!=1 or identity(ir,anns[0])!=INJECT:raise MixinPlanError(ir['origin'],'Each handler requires exactly @Inject')
            options=arguments(ir,anns[0],{'method','at','cancellable','require'})
            selector=literal(ir,singleton(ir,options.get('method'),'Inject.method'),str)
            at=singleton(ir,options.get('at'),'Inject.at')
            if at is None or at['kind']!='annotation' or identity(ir,at)!=AT:raise MixinPlanError(ir['origin'],'Exactly one @At required')
            location=literal(ir,arguments(ir,at,{'value'}).get('value'),str)
            if location not in ('HEAD','RETURN','TAIL'):raise MixinPlanError(ir['origin'],'Unsupported injection point: '+location)
            matches=[m for m in target_cls['methods'] if (descriptor(m,dict(target_cls,imports=target_ir['imports'],package=target_ir['package']),{'_project_types':project_types})==selector if '(' in selector else ('<init>' if m['constructor'] else m['name'])==selector)]
            if len(matches)!=1:raise MixinPlanError(ir['origin'],'Target selector must match exactly one declared method: '+selector)
            selected=dict(matches[0]);body=selected['body']
            if selected['constructor']:
                if location!='TAIL':raise MixinPlanError(ir['origin'],'Source constructors require TAIL after initialization')
                selected['return_type']='void'
                if any(n['kind']=='explicit_constructor_invocation' for n in walk(body)):
                    raise MixinPlanError(ir['origin'],'Explicit constructor chaining requires separate review')
                exits=[n for n in walk(body) if n['kind']=='return_statement']
                direct=children(body)
                if exits and (len(exits)!=1 or not direct or exits[0]!=direct[-1]):
                    raise MixinPlanError(ir['origin'],'Constructor TAIL requires one final normal return, not earlier return branches')
            elif location=='TAIL':raise MixinPlanError(ir['origin'],'TAIL currently reviewed only for constructors')
            if descriptor(selected,dict(target_cls,imports=target_ir['imports'],package=target_ir['package']),{'_project_types':project_types}) is None:
                raise MixinPlanError(ir['origin'],'Target descriptor contains an unreviewed parameter or return type')
            if body is None or selected['return_type'] not in ('void','int','boolean') or any(p['varargs'] for p in selected['parameters']):raise MixinPlanError(ir['origin'],'Only concrete void/int/boolean targets with fixed parameters supported')
            forbidden={'try_statement','try_with_resources_statement','lambda_expression','class_declaration','synchronized_statement','for_statement','while_statement','do_statement','enhanced_for_statement'}
            if any(n['kind'] in forbidden for n in walk(body)):raise MixinPlanError(ir['origin'],'Target control flow needs exact return-point lowering')
            modifiers=next((c for c in member['children'] if c['kind']=='modifiers'),{})
            if method['return_type']!='void' or method['static']!=selected['static'] or not any(c['kind']=='private' for c in modifiers.get('children',[])):raise MixinPlanError(ir['origin'],'Private void handler with matching staticness required')
            if not all(re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_$]*',name) for name in (method['name'],selected['name'])):
                raise MixinPlanError(ir['origin'],'Non-ASCII method identity requires a source-name adapter')
            pars=method['parameters'];boxed={'int':'Integer','boolean':'Boolean'}.get(selected['return_type'])
            normalized=[canonical(p['declared_type'].split('<',1)[0],dict(cls,external=True,imports=ir['imports'],package=ir['package']),{'_project_types':project_types}) for p in pars]
            callback=CALLBACK+('CallbackInfo' if selected['return_type']=='void' else 'CallbackInfoReturnable')
            if not pars or normalized[-1]!=callback or (boxed and pars[-1]['declared_type'].replace(' ','') not in tuple(prefix+'CallbackInfoReturnable<'+qualifier+boxed+'>' for prefix in ('',CALLBACK) for qualifier in ('','java.lang.'))):
                raise MixinPlanError(ir['origin'],'Callback parameter must match void/int/boolean return contract')
            if boxed:
                inner=pars[-1]['declared_type'].split('<',1)[1].rstrip('>').strip()
                if canonical(inner,dict(cls,external=True,imports=ir['imports'],package=ir['package']),{'_project_types':project_types})!='java.lang.'+boxed:
                    raise MixinPlanError(ir['origin'],'Return callback boxed type is shadowed')
            consume=len(pars)>1
            if consume:
                from java_mixin_types import identity as mixin_type_identity
                try:
                    captured=[mixin_type_identity(p['declared_type'],dict(cls,imports=ir['imports'],package=ir['package']),{'_project_types':project_types}) for p in pars[:-1]]
                    required=[mixin_type_identity(p['declared_type'],dict(target_cls,imports=target_ir['imports'],package=target_ir['package']),{'_project_types':project_types}) for p in selected['parameters']]
                except ValueError as error:raise MixinPlanError(ir['origin'],'Capture type identity unresolved: '+str(error))
                if captured!=required:raise MixinPlanError(ir['origin'],'Handler must capture all target arguments or callback only')
            if any(p['varargs'] for p in pars):raise MixinPlanError(ir['origin'],'Handler varargs unsupported')
            names=used_names.setdefault(target,{m['name'] for m in target_cls['methods']}|{f['name'] for f in target_cls['fields']})
            if method['name'] in names:raise MixinPlanError(ir['origin'],'Handler member collision: '+method['name'])
            names.add(method['name'])
            cancellable=literal(ir,options['cancellable'],bool) if 'cancellable' in options else False
            if selected['constructor'] and cancellable:raise MixinPlanError(ir['origin'],'Constructor callbacks cannot be cancellable')
            require=literal(ir,options['require'],int) if 'require' in options else default_require
            returns=[n for n in walk(body) if n['kind']=='return_statement']
            def completes(n):
                if n['kind'] in ('return_statement','throw_statement'):return False
                if n['kind'] in ('block','constructor_body'):return not children(n) or completes(children(n)[-1])
                if n['kind']=='if_statement':return field(n,'alternative') is None or completes(field(n,'consequence')) or completes(field(n,'alternative'))
                return True
            implicit=selected['return_type']=='void' and completes(body)
            if selected['return_type']!='void' and completes(body):raise MixinPlanError(ir['origin'],'Nonvoid target has unproven return coverage')
            count=1 if location=='HEAD' else len(returns)+int(implicit)
            if not count or count<require:raise MixinPlanError(ir['origin'],'Injection match count does not satisfy require')
            raw=text(ir,member);start=member['span'][0];a,b=anns[0]['span'];raw=raw[:a-start]+raw[b-start:]
            entries.append({'config':config_name,'mixin':java,'mixin_file':ir['origin'],'target':target,'target_file':target_ir['origin'],'selector':selector,'descriptor':descriptor(selected,dict(target_cls,imports=target_ir['imports'],package=target_ir['package']),{'_project_types':project_types}),'handler':method['name'],'handler_source':raw,'at':location,'priority':priority,'serial':len(entries),'cancellable':cancellable,'require':require,'matches':count,'capture_arguments':consume,'body_span':body['span'],'return_spans':[n['span'] for n in returns],'implicit_void_return':implicit,'parameter_names':[p['name'] for p in selected['parameters']],'return_type':selected['return_type'],'constructor':selected['constructor'],'static':selected['static']})
    for path in sorted(root.rglob('*.java')):
        file=path.relative_to(root).as_posix()
        if file in mixin_files:continue
        ir=cached[file][0] if file in cached else isolated_parse(path.read_bytes(),file,[])
        if any(n['kind'] in ('type_identifier','identifier') and text(ir,n) in {j.rsplit('.',1)[-1] for _,j,_ in listed} for n in walk(ir['tree'])):raise MixinPlanError(file,'Mixin class used as a normal source type')
    files={p.relative_to(root).as_posix():digest(p.read_bytes()) for p in root.rglob('*.java')}
    return {'schema_version':1,'scope':'same_content_source_callbacks','configs':configs,'source_sha256':files,'mixin_files':mixin_files,'field_bindings':field_bindings,'native_bindings':native_bindings,'injections':entries}
