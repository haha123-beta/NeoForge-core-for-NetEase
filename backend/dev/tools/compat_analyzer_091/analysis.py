"""Evidence graph: measured diagnostics, exhaustive static refs, explicit unknowns."""
from pathlib import Path
import ast,collections,hashlib,json,re,zipfile
from abi import Index,archive_classes
from classfile import read
from locking import load,save

def canonical(name):return (name or '').replace('$','.')
def symbol_key(ref):return ref['owner']+'#'+ref['name']+ref['descriptor']
def source_name(row):
    package=row['name'].rsplit('.',1)[0] if '.' in row['name'] else ''
    return (package.replace('.','/')+'/' if package else '')+row.get('source_file','<UNKNOWN>')
def components(files,edges,kind):
    adjacency={f:set() for f in files}
    for edge in edges:
        if edge['kind']==kind and edge['from'] in adjacency and edge['to'] in adjacency:adjacency[edge['from']].add(edge['to'])
    index={};low={};stack=[];active=set();result=[]
    def visit(v):
        index[v]=low[v]=len(index);stack.append(v);active.add(v)
        for w in sorted(adjacency[v]):
            if w not in index:visit(w);low[v]=min(low[v],low[w])
            elif w in active:low[v]=min(low[v],index[w])
        if low[v]==index[v]:
            group=[]
            while True:
                w=stack.pop();active.remove(w);group.append(w)
                if w==v:break
            if len(group)>1 or v in adjacency[v]:result.append(sorted(group))
    for v in sorted(adjacency):
        if v not in index:visit(v)
    return sorted(result)
def category(symbol):
    if symbol.startswith(('org.objectweb.asm.','cpw.mods.modlauncher.','org.spongepowered.asm.mixin.','java.lang.reflect.','java.lang.invoke.')):return 'JVM_ASM_LIMIT'
    if symbol.startswith(('net.minecraft.','com.mojang.','net.neoforged.','net.minecraftforge.','java.','javax.','io.netty.','org.joml.','com.google.common.','org.slf4j.')):return 'API_METADATA'
    return 'THIRD_PARTY_DEPENDENCY'
def first_diagnostic(row):
    reason=row.get('reason','');details=row.get('details') or {};symbol=details.get('symbol','')
    if symbol:return category(symbol),symbol
    if reason.startswith('Entity registration argument differs'):return 'COMPILER_SEMANTICS',reason
    if reason.startswith('MerchantOffer source construction'):return 'API_METADATA',reason
    if reason.startswith('Tool/holder-set API requires review'):return 'RUNTIME_BEHAVIOR',reason
    if any(s in reason.lower() for s in ('generic','annotation','lowering','lowered','condition','cast','class kind','namespaces collide','assignment','reference equality','instanceof','numeric','synchronized')):
        return 'COMPILER_SEMANTICS',re.sub(r':.*$', '',reason)
    if any(s in reason for s in ('method','abstract','field','ByteBufCodecs')):return 'API_METADATA',reason
    return 'UNCLASSIFIED_REVIEW',reason

def runtime_inventory(root):
    mappings={};errors=[];modules={}
    for p in sorted(root.rglob('*.py')):
        rel=p.relative_to(root).as_posix()
        try:tree=ast.parse(p.read_text(encoding='utf-8-sig'))
        except (SyntaxError,UnicodeError) as error:errors.append({'file':rel,'status':'UNKNOWN','reason':str(error)});continue
        classes={}
        def classes_in(nodes,prefix=''):
            for node in nodes:
                if not isinstance(node,ast.ClassDef):continue
                name=prefix+node.name;methods={}
                for method in node.body:
                    if not isinstance(method,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
                    body=[n for n in method.body if not isinstance(n,ast.Expr) or not isinstance(n.value,ast.Constant) or not isinstance(n.value.value,str)]
                    stub=bool(body) and all(isinstance(n,ast.Raise) for n in body)
                    exceptions=[ast.unparse(n.exc) for n in body if isinstance(n,ast.Raise)]
                    methods[method.name]={'line':method.lineno,'explicit_not_implemented':stub and any('NotImplementedError' in s for s in exceptions),
                        'unconditional_raises':exceptions,'behavior':'UNVERIFIED'}
                classes[name]={'methods':methods,'bases':[ast.unparse(b) for b in node.bases]}
                attrs=set()
                for child in node.body:
                    if isinstance(child,ast.Assign):
                        attrs.update(t.id for t in child.targets if isinstance(t,ast.Name))
                def stores(child):
                    if isinstance(child,ast.ClassDef):return
                    if isinstance(child,ast.Assign):
                        attrs.update(t.attr for t in child.targets if isinstance(t,ast.Attribute) and isinstance(t.value,ast.Name) and t.value.id in ('self','cls'))
                    for nested in ast.iter_child_nodes(child):stores(nested)
                for method in node.body:
                    if isinstance(method,ast.FunctionDef):stores(method)
                classes[name]['observed_attribute_names']=sorted(attrs)
                classes_in(node.body,name+'.')
        classes_in(tree.body);modules[rel]=classes
        for node in ast.walk(tree):
            if not isinstance(node,ast.Dict):continue
            # Only actual JAVA_MAP assignments/updates, not arbitrary dicts.
            parent=next((a for a in ast.walk(tree) if isinstance(a,ast.Assign) and a.value is node and any(isinstance(t,ast.Name) and t.id=='JAVA_MAP' for t in a.targets)),None)
            update=any(isinstance(a,ast.Call) and node in a.args and isinstance(a.func,ast.Attribute) and isinstance(a.func.value,ast.Name) and a.func.value.id=='JAVA_MAP' and a.func.attr=='update' for a in ast.walk(tree))
            if parent is None and not update:continue
            for key,value in zip(node.keys,node.values):
                if isinstance(key,ast.Constant) and isinstance(key.value,str):
                    mappings[canonical(key.value)]={'file':rel,'python_identity':ast.unparse(value),'line':value.lineno}
    return {'mappings':mappings,'modules':modules,'parse_unknowns':errors,
        'limits':'Static literal JAVA_MAP only. Dynamic mappings/inherited cross-module methods remain UNKNOWN; implementation presence never proves behavior.'}

def analyze(lock,abi,cfr):
    baseline=load(lock['inputs']['baseline']['path']);report=baseline['source_reports'][0]
    expected={r['file']:r for r in report['results']}
    counts=collections.Counter(r['status'] for r in expected.values())
    if (len(expected),counts['GENERATED_REVIEW_REQUIRED'],counts['MANUAL_REVIEW'],report['failed'])!=(130,32,98,0):raise ValueError('Baseline differs; this profile requires explicit rebaseline')
    core=load(lock['inputs']['production_index']['path']);exports={canonical(n) for n in core['java_types']}
    runtime=runtime_inventory(Path(lock['frozen_release'])/'backend/core/NeoForgeCoreScripts')
    mod=[];jar_metadata={}
    with zipfile.ZipFile(lock['inputs']['mod']['path']) as archive:
        for entry in archive.namelist():
            if entry.endswith('.json') and 'mixin' in entry.lower():jar_metadata[entry]=json.loads(archive.read(entry))
            if entry.startswith('META-INF/services/') or entry.lower().endswith('accesstransformer.cfg'):
                jar_metadata[entry]=archive.read(entry).decode('utf-8')
    for entry,raw,level in archive_classes(lock['inputs']['mod']['path']):
        row=read(raw);row['entry']=entry;row['sha256']=hashlib.sha256(raw).hexdigest()
        if row['name'].replace('.','/')+'.class'!=entry:raise ValueError('Mod class entry/name mismatch')
        row['origin']={'artifact':'input_mod','entry':entry,'sha256':lock['inputs']['mod']['sha256'],'role':'input_mod'}
        mod.append(row)
    if len(mod)!=191:raise ValueError('Unexpected class count')
    project={r['name']:r for r in mod};class_file={r['name']:source_name(r) for r in mod}
    if set(class_file.values())!=set(expected):raise ValueError('Class SourceFile vs CFR/baseline mismatch')
    symbols=Index(dict(abi['classes'],**project));nodes={};files={};edges=[];calls=[];crosscheck=[];members=[]
    def node(cat,symbol,summary,certainty,evidence,group=None):
        key=cat+':'+symbol
        if key not in nodes:nodes[key]={'id':key,'category':cat,'symbol':symbol,'summary':summary,'certainty':certainty,
            'evidence':[],'repair_group':group or key,'files':[],'behavior_verified':False}
        n=nodes[key]
        if certainty=='MEASURED_DIAGNOSTIC':n['certainty']=certainty
        if evidence not in n['evidence']:n['evidence'].append(evidence)
        return key
    def attach(file,key,kind):
        if key not in files[file][kind]:files[file][kind].append(key)
        if file not in nodes[key]['files']:nodes[key]['files'].append(file)
    for name,row in sorted(expected.items()):
        files[name]={'file':name,'baseline_status':row['status'],'baseline_diagnostic':row if row['status']=='MANUAL_REVIEW' else None,
            'measured_blockers':[],'static_requirements':[],'dependencies':list(row.get('missing_generated_dependencies',[])),
            'all_reported_project_dependencies':row.get('project_dependencies',[]),'unknown_frontier':row['status']!='GENERATED_REVIEW_REQUIRED',
            'future_generation':'UNKNOWN' if row['status']=='MANUAL_REVIEW' else 'MEASURED_GENERATED_FOR_REVIEW',
            'runtime_execution':'NOT_VERIFIED','classes':[]}
        if row['status']=='MANUAL_REVIEW':
            cat,symbol=first_diagnostic(row);group=(cat+':'+canonical(symbol))
            bindings=[]
            if row.get('reason','').startswith('Unresolved declared method: '):
                method=row['reason'].split(': ',1)[1]
                for cls in mod:
                    if class_file[cls['name']]!=name:continue
                    for ref in cls['member_references']:
                        if ref['name']!=method:continue
                        result=symbols.member(ref['owner'],ref['name'],ref['descriptor'],ref['kind'])
                        if result['status']=='FOUND':
                            item={'owner':result['declaring_type'],'name':method,'descriptor':ref['descriptor']}
                            if item not in bindings:bindings.append(item)
                if len(bindings)==1:
                    symbol=symbol_key(bindings[0]);group=cat+':'+canonical(bindings[0]['owner'])
            key=node(cat,symbol if '#' in symbol else canonical(symbol),row.get('reason',''),'MEASURED_DIAGNOSTIC',{'source':'0.9.0_report','file':name,'line':row.get('line'),'details':row.get('details',{})},group)
            if bindings:nodes[key]['bytecode_descriptor_candidates']=bindings
            attach(name,key,'measured_blockers')
        for dep in row.get('missing_generated_dependencies',[]):edges.append({'from':name,'to':dep,'kind':'MEASURED_MISSING_GENERATED_DEPENDENCY','evidence':'0.9.0_report'})
    conditional={}
    for config,value in jar_metadata.items():
        if not isinstance(value,dict):continue
        for c in [value.get('plugin')]+[n for k in ('mixins','client','server') for n in value.get(k,[])]:
            if not c:continue
            identity=c if '.' in c else value.get('package','')+'.'+c
            conditional[identity]={'config':config,'required':value.get('required',False),'baseline_skip':any(r['source']==config for r in report.get('skipped_optional',[]))}
    for row in mod:
        file=class_file[row['name']];files[file]['classes'].append(row['name'])
        files[file].setdefault('conditions',[])
        if row['name'] in conditional:files[file]['conditions'].append(conditional[row['name']])
        for parent in [row['superclass']]+row['interfaces']:
            if parent:edges.append({'from':row['name'],'to':parent,'kind':'CLASS_INHERITANCE','file':file})
        direct_owners={r['target']['owner'] for r in row['calls'] if 'target' in r and r['opcode'].startswith('invoke')}
        for target in row['type_references']:
            if target in project:
                dep=class_file[target]
                if dep!=file:edges.append({'from':file,'to':dep,'kind':'STATIC_PROJECT_REFERENCE','class':row['name'],'target_class':target})
                continue
            fact=symbols.type(target);norm=canonical(target)
            synthetic=target.startswith('java.lang.invoke.') and target not in direct_owners
            annotation=target in {t[1:-1].replace('/','.') for t in row['annotations']}
            if synthetic or annotation:continue # retained in raw class facts; not an asserted runtime need
            if norm not in exports:
                cat=category(target);group=cat+':'+norm
                key=node(cat,norm,'No exported 0.9.0 type metadata/provider; execution reachability unknown','STATIC_REQUIREMENT',
                    {'source':'classfile_type_reference','class':row['name'],'entry':row['entry'],'abi_status':fact['status'],
                     'abi_origin':fact.get('definition',{}).get('origin')},group)
                attach(file,key,'static_requirements')
                if cat=='API_METADATA':
                    key=node('RUNTIME_BEHAVIOR',norm,'No registered production type provider in frozen API inventory; existing unexported code and full behavior remain unproven',
                        'NO_EXPORTED_PROVIDER',{'source':'0.9.0_java_import_index','class_reference':target},group)
                    attach(file,key,'static_requirements')
            elif fact['status']!='FOUND':
                key=node('API_METADATA','reference-abi:'+target,'Official/dependency ABI unavailable or ambiguous in selected profile; do not infer a missing target API',
                    'UNKNOWN_REFERENCE_ABI',{'source':'selected_abi','status':fact['status'],'class':row['name']},'reference-profile:'+target)
                attach(file,key,'static_requirements')
        for ref in row['member_references']:
            resolved=symbols.member(ref['owner'],ref['name'],ref['descriptor'],ref['kind'])
            members.append(dict(ref,source_class=row['name'],source_file=file,resolution=resolved))
            if resolved['status'] in ('MEMBER_NOT_FOUND','UNKNOWN_HIERARCHY'):
                # Missing dependency/class is not proven API nonexistence.
                status='UNKNOWN_REFERENCE_ABI' if resolved['status']=='UNKNOWN_HIERARCHY' else 'REFERENCE_ABI_MISMATCH'
                cat='THIRD_PARTY_DEPENDENCY' if category(ref['owner'])=='THIRD_PARTY_DEPENDENCY' else 'API_METADATA'
                key=node(cat,'member:'+symbol_key(ref),'Reference member could not be proven against selected binaries; may require missing dependencies/transform review',status,
                    {'source':'constant_pool_member','class':row['name'],'lookup':resolved},cat+':'+canonical(ref['owner']))
                attach(file,key,'static_requirements')
            # Runtime inventory only supplies concrete evidence of explicit unsupported bodies.
            mapping=runtime['mappings'].get(canonical(ref['owner']))
            if mapping:
                classes=runtime['modules'].get(mapping['file'],{});definition=classes.get(mapping['python_identity'],{})
                method=definition.get('methods',{}).get('__init__' if ref['name']=='<init>' else ref['name'])
                if method and method['explicit_not_implemented'] and not resolved.get('member',{}).get('access',0)&0x0400:
                    key=node('RUNTIME_BEHAVIOR',symbol_key(ref),'Referenced Python provider explicitly raises unsupported/not-implemented; reachability still unknown',
                        'EXPLICIT_STUB',dict(mapping,method_line=method['line'],class_reference=row['name']),'RUNTIME_BEHAVIOR:'+canonical(ref['owner']))
                    attach(file,key,'static_requirements')
        for call in row['calls']:
            if not (call['opcode'].startswith('invoke') or 'method_handle' in call or 'dynamic' in call):continue
            calls.append(dict(call,source_class=row['name'],source_file=file))
    for file,row in files.items():
        c=cfr.get(file)
        if c is None:raise ValueError('Missing CFR file '+file)
        outer={n.rsplit('.',1)[-1].split('$',1)[0] for n in row['classes']}
        missing=outer-set(c['declarations'])
        byte_names={call['target']['name'] for call in calls if call['source_file']==file and 'target' in call and not call['target']['name'].startswith(('<','lambda$'))}
        source_names={r['name'] for r in c['method_invocations']}
        cross={'file':file,'cfr_sha256':c['sha256'],'cfr_parse_status':c['parse_status'],'class_sourcefile_mapping':'EXACT',
            'outer_declarations_missing_in_cfr':sorted(missing),'bytecode_only_method_names':sorted(byte_names-source_names),
            'cfr_only_method_names':sorted(source_names-byte_names),'matched_method_names':sorted(byte_names&source_names),
            'comparison_precision':'NAME_ONLY; bytecode owner/descriptor authoritative; synthetic/lowered and dynamic calls may differ'}
        crosscheck.append(cross)
        if missing or c['parse_status']!='PARSED':
            key=node('COMPILER_SEMANTICS','cfr-crosscheck:'+file,'CFR declaration/parser discrepancy requires review','CFR_DISCREPANCY',cross)
            attach(file,key,'static_requirements');row['unknown_frontier']=True
        row['cfr_features']=c['features']
        row['unknowns']=['Execution reachability, side/config guards, reflection, dynamic dispatch and runtime behavior are not proven']
        if row['unknown_frontier']:row['unknowns'].append('Compiler stopped at first diagnostic; subsequent compiler semantic failures have not been explored')
        # A generated source with unresolved peers retains the peer's unknown frontier.
        if row['dependencies']:row['unknowns'].append('Generated dependency closure is incomplete; peer fixes may expose further failures')
    services={k:v for k,v in jar_metadata.items() if k.startswith('META-INF/services/')}
    ats={};global_requirements=[]
    for config,text in jar_metadata.items():
        if not config.lower().endswith('accesstransformer.cfg'):continue
        rules=[]
        for number,line in enumerate(text.splitlines(),1):
            rule=line.split('#',1)[0].strip()
            if not rule:continue
            parts=rule.split();item={'line':number,'rule':rule,'runtime_field_presence':'UNKNOWN_NOT_ASSUMED'}
            if len(parts)>=3:
                owner,name=parts[1],parts[2];definition=abi['classes'].get(owner,{})
                item['official_declared_members']=[dict(m,kind=k) for k in ('fields','methods') for m in definition.get(k,[]) if m['name']==name or m['name']+m['descriptor']==name]
                mapping=runtime['mappings'].get(canonical(owner))
                if mapping:
                    attrs=runtime['modules'].get(mapping['file'],{}).get(mapping['python_identity'],{}).get('observed_attribute_names',[])
                    if name in attrs:item['runtime_field_presence']='OBSERVED_NAME_ONLY_NOT_ALL_CONSTRUCTION_PATHS'
                item['affected_bytecode_files']=sorted(set(m['source_file'] for m in members if m['owner']==owner and m['name']==name))
            rules.append(item)
        ats[config]=rules
        global_requirements.append({'kind':'ACCESS_TRANSFORMER_RUNTIME_FIELD_PARITY','source':config,'rules':len(rules),
            'status':'UNKNOWN_UNTIL_RUNTIME_FIELD_AND_BEHAVIOR_VALIDATION','python_private_access_is_not_sufficient':True})
    summary={'files':130,'class_files':191,'generated_for_review':32,'manual_review':98,'failed':0,
        'generated_missing_dependency_files':sum(bool(r['dependencies']) and r['baseline_status']=='GENERATED_REVIEW_REQUIRED' for r in files.values()),
        'all_manual_files_explained':all(r['measured_blockers'] for r in files.values() if r['baseline_status']=='MANUAL_REVIEW'),
        'node_categories':dict(collections.Counter(n['category'] for n in nodes.values())),
        'source_mapping_discrepancies':sum(bool(r['outer_declarations_missing_in_cfr']) for r in crosscheck),
        'actual_new_unlocked_files':0,'new_conversion_executed':False,'runtime_verified':False}
    if summary['generated_missing_dependency_files']!=15:raise ValueError('Missing dependency baseline drift')
    for row in files.values():
        for key in ('measured_blockers','static_requirements','classes'):row[key].sort()
        for key in row['measured_blockers']:edges.append({'from':row['file'],'to':key,'kind':'MEASURED_BLOCKER'})
        for key in row['static_requirements']:edges.append({'from':row['file'],'to':key,'kind':'STATIC_REQUIREMENT_NOT_PROVEN_REACHABLE'})
    for row in nodes.values():row['files'].sort()
    return {'schema_version':1,'version':'0.9.1','summary':summary,'baseline_job':'fa9ac34fc0ec4ed19af4c7d47db9e0a3',
        'files':files,'blocker_nodes':nodes,'edges':sorted(edges,key=lambda e:json.dumps(e,sort_keys=True)),
        'class_facts':mod,'member_resolutions':members,'call_graph':calls,'cfr_crosscheck':crosscheck,
        'runtime_inventory':runtime,'optional_transformations':report.get('skipped_optional',[]),
        'service_declarations':services,'access_transformers':ats,'global_requirements':global_requirements,
        'dependency_cycles':{'measured':components(files,edges,'MEASURED_MISSING_GENERATED_DEPENDENCY'),
                             'static_potential':components(files,edges,'STATIC_PROJECT_REFERENCE')},
        'limits':['All classfile constant-pool and code references scanned; reflection/dynamic targets remain unknown',
                  'Static requirements are not measured failure diagnoses or proof of execution',
                  'Runtime mapping/body presence does not certify behavior; no production API added',
                  'First compiler diagnostics preserved verbatim; later compiler blockers explicitly unknown']}
