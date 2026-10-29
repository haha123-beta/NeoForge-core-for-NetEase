"""Bounded Java source lowerings. Original files/hash stay intact; unsupported forms reject."""

def lower(ir):
    if ir.get('source_lowerings') or ir.get('parse_status')!='PARSED':return ir
    raw=ir['source_utf8'].encode('utf-8');original=raw;positions=list(range(len(raw)));records={};anonymous={};edits=[];helpers=[]
    def text(node):return raw[node['span'][0]:node['span'][1]].decode('utf-8') if node else ''
    def field(node,name):return next((c for c in node.get('children',[]) if c.get('field')==name),None)
    def named(node):return [c for c in (node or {}).get('children',[]) if c['kind'] not in ('(',')','{','}',',',';')]
    def reject(node,message):
        from java_codegen import NeedsLowering
        raise NeedsLowering(node,message,{'category':'source_lowering'})
    roots=[n for n in ir['tree'].get('children',[]) if n['kind'] in ('record_declaration','class_declaration')]
    all_names={text(field(n,'name')) for n in roots}
    def visit(node,top=None,static_field=False):
        if node['kind']=='record_declaration':
            if node not in roots:reject(node,'Nested/local records require owner and capture lowering')
            name=text(field(node,'name'));body=field(node,'body');params=field(node,'parameters')
            if any(c['kind']=='type_parameters' for c in node.get('children',[])):reject(node,'Generic record declaration requires type substitution')
            components=[]
            for c in named(params):
                if c['kind']!='formal_parameter' or any(x['kind']=='modifiers' for x in c.get('children',[])):reject(c,'Annotated/varargs record component propagation requires lowering')
                kind=text(field(c,'type'))+text(field(c,'dimensions'));member=text(field(c,'name'))
                if kind in ('float','double','char'):reject(c,'Record primitive conversion requires reviewed constructor narrowing: '+kind)
                if member in ('clone','finalize','getClass','hashCode','notify','notifyAll','toString','wait') or member.startswith('_nc_'):reject(c,'Invalid/reserved record component: '+member)
                if any(x['name']==member for x in components):reject(c,'Duplicate record component')
                components.append({'name':member,'declared_type':kind,'storage':'_nc_record_'+str(len(components))})
            members=named(body)
            if any(m['kind'] in ('constructor_declaration','compact_constructor_declaration','block') for m in members):reject(node,'Explicit/compact record constructor or instance initializer requires lowering')
            for m in members:
                if m['kind']=='field_declaration' and not any(c.get('text')=='static' for mod in m.get('children',[]) if mod['kind']=='modifiers' for c in mod.get('children',[])):reject(m,'Record cannot declare additional instance fields')
            methods=[m for m in members if m['kind']=='method_declaration']
            synthetic=''.join('private final '+c['declared_type']+' '+c['name']+';' for c in components)
            synthetic+='public '+name+'('+','.join(c['declared_type']+' '+c['name'] for c in components)+'){'+''.join('this.'+c['name']+'='+c['name']+';' for c in components)+'}'
            for c in components:
                matches=[m for m in methods if text(field(m,'name'))==c['name'] and not named(field(m,'parameters'))]
                if not matches:synthetic+='public '+c['declared_type']+' '+c['name']+'(){return this.'+c['name']+';}'
                elif text(field(matches[0],'type'))!=c['declared_type']:reject(matches[0],'Record accessor type must match component')
            keyword=next(c for c in node['children'] if c['kind']=='record')
            edits.extend([(keyword['span'][0],keyword['span'][1],b'class'),(params['span'][0],params['span'][1],b''),(body['span'][0]+1,body['span'][0]+1,synthetic.encode('utf-8'))])
            records[name]=components
        if node['kind']=='object_creation_expression' and any(c['kind']=='class_body' for c in node.get('children',[])):
            type_node=field(node,'type');kind=text(type_node);base=kind.split('<',1)[0]
            identity=next((r['name'] for r in ir['imports'] if not r['static'] and not r['wildcard'] and r['name'].rsplit('.',1)[-1]==base),base)
            if identity!='net.minecraft.network.codec.StreamCodec':return
            if not static_field:reject(node,'Anonymous StreamCodec requires a direct static field initializer; captures are not lowered')
            if named(field(node,'arguments')):reject(node,'StreamCodec interface constructor takes no arguments')
            from java_library_signatures import generic_arguments
            arguments=generic_arguments(kind.replace(' ',''))
            if len(arguments)!=2:reject(node,'StreamCodec requires two explicit type arguments')
            body=next(c for c in node['children'] if c['kind']=='class_body')
            if any(c['kind'] not in ('{','}','method_declaration','line_comment','block_comment') for c in body.get('children',[])):reject(node,'Anonymous codec fields/initializers/nested declarations require lowering')
            name='_nc_AnonymousCodec'+str(len(anonymous))+'_'+ir['source_sha256'][:12]
            if name in all_names:reject(node,'Generated anonymous codec name collides with source type')
            anonymous[name]={'arguments':arguments,'owner':'.'.join(filter(None,(ir.get('package'),top)))};helpers.append('class '+name+' implements '+kind+' '+text(body)+'\n')
            edits.append((node['span'][0],node['span'][1],('new '+name+'()').encode('utf-8')))
            return
        for child in node.get('children',[]):
            is_static=static_field
            if child['kind'] in ('lambda_expression','method_declaration','constructor_declaration'):is_static=False
            if child['kind']=='field_declaration':
                is_static=any(c.get('text')=='static' for mod in child.get('children',[]) if mod['kind']=='modifiers' for c in mod.get('children',[]))
            visit(child,top,is_static)
    for node in roots:visit(node,text(field(node,'name')))
    if not edits:return ir
    if helpers:
        first=min(n['span'][0] for n in roots);edits.append((first,first,''.join(helpers).encode('utf-8')))
    for a,b,replacement in sorted(edits,reverse=True):
        raw=raw[:a]+replacement+raw[b:]
        positions=positions[:a]+[a]*len(replacement)+positions[b:]
    from java_frontend import parse_source
    lowered=parse_source(raw,ir['origin'],ir.get('known_api_types',[]))
    if lowered['parse_status']!='PARSED':reject(ir['tree'],'Generated record/codec lowering failed to parse')
    from bisect import bisect_left
    newlines=[i for i,b in enumerate(original) if b==10]
    def restore_lines(node):
        offset=node['span'][0]
        node['line']=bisect_left(newlines,positions[offset] if offset<len(positions) else len(original))+1
        for c in node.get('children',[]):restore_lines(c)
    restore_lines(lowered['tree'])
    lowered.update(source_sha256=ir['source_sha256'],original_source_utf8=ir['source_utf8'],source_lowerings={'records':records,'anonymous_codecs':anonymous})
    lowered['features']=sorted(set(ir['features'])|set(lowered['features']))
    return lowered
