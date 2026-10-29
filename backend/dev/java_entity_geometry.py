"""Read a bounded, static Mojmap LayerDefinition method without executing Java.

Only the reviewed mesh/part/cube/pose DSL is evaluated. Every unknown statement
or call rejects the layer. Other class methods are reported, never discarded.
"""
import copy,hashlib,json,math,re,struct
from java_frontend import parse_source
from java_symbols import declarations

BUILDERS='net.minecraft.client.model.geom.builders.'
TYPES={BUILDERS+n for n in ('MeshDefinition','PartDefinition','CubeListBuilder','CubeDeformation','LayerDefinition')}
TYPES.add('net.minecraft.client.model.geom.PartPose')

class GeometryError(ValueError):pass

def convert(raw,origin,method_name,identifier):
    if isinstance(raw,str):raw=raw.encode('utf-8')
    if len(raw)>2*1024*1024:raise GeometryError('Model source exceeds 2 MiB')
    ir=parse_source(raw,origin)
    if ir['parse_status']!='PARSED':raise GeometryError('Model contains Java syntax errors')
    data=ir['source_utf8'].encode('utf-8');symbols=declarations(ir)
    def text(n):return data[n['span'][0]:n['span'][1]].decode('utf-8') if n else ''
    def field(n,key):return next((c for c in n.get('children',[]) if c.get('field')==key),None) if n else None
    def children(n):return [c for c in (n or {}).get('children',[]) if c['kind'] not in ('(',')','{','}',',',';','return','line_comment','block_comment')]
    def fail(n,msg):raise GeometryError(origin+':'+str((n or {}).get('line',1))+': '+msg)
    imports={}
    for imp in ir['imports']:
        if imp['static'] or imp['wildcard']:fail(imp,'Model layer requires explicit imports')
        short=imp['name'].rsplit('.',1)[-1]
        if short in imports:fail(imp,'Duplicate model import binding')
        imports[short]=imp['name']
    if len(symbols['classes'])!=1:fail(None,'Model layer requires one top-level class')
    cls=symbols['classes'][0]
    if cls['name'] in imports:fail(cls,'Class shadows imported model type')
    methods=[m for m in cls['methods'] if m['name']==method_name and not m['constructor']]
    if len(methods)!=1:fail(cls,'Unique layer method required')
    method=methods[0]
    if not method['static'] or method['parameters'] or imports.get(method['return_type'],method['return_type'])!=BUILDERS+'LayerDefinition' or method['body'] is None:
        fail(method,'Layer method requires static zero-argument LayerDefinition')
    env={};nodes=[];returned=None
    def number(value,n):
        if type(value) not in (int,float) or not math.isfinite(value) or abs(value)>65536:fail(n,'Finite bounded model number required')
        return value
    def nums(values,n):return [number(v,n) for v in values]
    def f32(value):return struct.unpack('f',struct.pack('f',value))[0]
    def typed(value,tag,n):
        if not isinstance(value,dict) or value.get('kind')!=tag:fail(n,'Expected model '+tag)
        return value
    def evaluate(n):
        if n is None:fail(n,'Missing model expression')
        kind=n['kind'];raw=text(n)
        if kind in ('decimal_integer_literal','decimal_floating_point_literal'):
            token=raw.replace('_','')
            if kind=='decimal_integer_literal':return int(token)
            value=float(token.rstrip('fFdD'))
            return number(f32(value) if token[-1:] in 'fF' else value,n)
        if kind=='unary_expression':
            cc=children(n)
            if len(cc)==2 and text(cc[0]) in ('-','+'):
                value=number(evaluate(cc[1]),n);return -value if text(cc[0])=='-' else value
        if kind=='string_literal':
            if '\\' in raw:fail(n,'Escaped part names require separate conversion')
            return json.loads(raw)
        if raw in ('true','false'):return raw=='true'
        if kind=='parenthesized_expression':return evaluate(children(n)[0])
        if kind=='cast_expression':
            target=text(field(n,'type'));value=evaluate(field(n,'value'))
            if imports.get(target,target)==BUILDERS+'MeshDefinition':return typed(value,'mesh',n)
            if target not in ('float','int') or type(value) not in (int,float):fail(n,'Only numeric float/int model casts reviewed')
            return f32(value) if target=='float' else int(value)
        if kind in ('identifier','scoped_identifier'):
            if raw in env:return env[raw]
            resolved=imports.get(raw,raw)
            if resolved in TYPES:return {'kind':'type','name':resolved.rsplit('.',1)[-1]}
            fail(n,'Unresolved model value/type: '+raw)
        if kind=='field_access':
            obj=evaluate(field(n,'object'));name=text(field(n,'field'))
            if obj=={'kind':'type','name':'PartPose'} and name=='ZERO':return {'kind':'pose','offset':[0,0,0],'rotation':[0,0,0]}
            fail(n,'Unreviewed model field access')
        if kind=='object_creation_expression':
            identity=imports.get(text(field(n,'type')),text(field(n,'type')))
            args=[evaluate(a) for a in children(field(n,'arguments'))]
            if identity==BUILDERS+'MeshDefinition' and not args:
                root={'kind':'part','name':'root','parent':None,'offset':[0,0,0],'rotation':[0,0,0],'cubes':[]}
                nodes.append(root);return {'kind':'mesh','root':root}
            if identity==BUILDERS+'CubeDeformation' and len(args)==1:return {'kind':'inflate','value':number(args[0],n)}
            fail(n,'Unreviewed model constructor')
        if kind=='method_invocation':
            obj=evaluate(field(n,'object'));name=text(field(n,'name'));args=[evaluate(a) for a in children(field(n,'arguments'))]
            if not isinstance(obj,dict):fail(n,'Model call receiver is not a builder')
            if obj.get('kind')=='type':
                owner=obj['name']
                if owner=='CubeListBuilder' and name=='create' and not args:return {'kind':'cubes','uv':[0,0],'mirror':False,'boxes':[]}
                if owner=='PartPose' and name in ('offset','offsetAndRotation') and len(args)==(3 if name=='offset' else 6):
                    values=nums(args,n);return {'kind':'pose','offset':values[:3],'rotation':values[3:] if len(values)==6 else [0,0,0]}
                if owner=='LayerDefinition' and name=='create' and len(args)==3:
                    mesh=typed(args[0],'mesh',n);w,h=args[1:]
                    if type(w)!=int or type(h)!=int or not 1<=w<=4096 or not 1<=h<=4096:fail(n,'Texture dimensions require 1..4096 integers')
                    return {'kind':'layer','mesh':mesh,'width':w,'height':h}
            if obj.get('kind')=='mesh' and name=='getRoot' and not args:return obj['root']
            if obj.get('kind')=='part' and name=='addOrReplaceChild' and len(args)==3:
                part_name,builder,pose=args;typed(builder,'cubes',n);typed(pose,'pose',n)
                if not isinstance(part_name,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',part_name):fail(n,'Simple explicit bone name required')
                if any(p['name']==part_name for p in nodes):fail(n,'Replacing or duplicate/global-ambiguous bone name requires review')
                node={'kind':'part','name':part_name,'parent':obj,'offset':pose['offset'],'rotation':pose['rotation'],'cubes':copy.deepcopy(builder['boxes'])}
                nodes.append(node)
                if len(nodes)>512:fail(n,'Model exceeds 512 bones')
                return node
            if obj.get('kind')=='cubes':
                if name=='texOffs' and len(args)==2:
                    if any(type(v)!=int or not 0<=v<=8192 for v in args):fail(n,'Texture offsets require bounded integers')
                    obj['uv']=args;return obj
                if name=='mirror' and len(args)<=1 and (not args or type(args[0])==bool):obj['mirror']=args[0] if args else True;return obj
                if name=='addBox' and len(args) in (6,7):
                    values=nums(args[:6],n)
                    if any(v<0 for v in values[3:]) or all(v==0 for v in values[3:]):fail(n,'Invalid cube size')
                    inflate=typed(args[6],'inflate',n)['value'] if len(args)==7 else 0
                    obj['boxes'].append({'position':values[:3],'size':values[3:],'inflate':inflate,'uv':list(obj['uv']),'mirror':obj['mirror']})
                    if len(obj['boxes'])>2048:fail(n,'Model cube count exceeded')
                    return obj
            fail(n,'Unreviewed model call: '+name)
        fail(n,'Unreviewed model expression: '+kind)
    for stmt in children(method['body']):
        if returned is not None:fail(stmt,'Statements after model return')
        if stmt['kind']=='local_variable_declaration':
            declared=imports.get(text(field(stmt,'type')),text(field(stmt,'type')))
            tags={BUILDERS+'MeshDefinition':'mesh',BUILDERS+'PartDefinition':'part',BUILDERS+'CubeListBuilder':'cubes','net.minecraft.client.model.geom.PartPose':'pose'}
            if declared not in tags:fail(stmt,'Unreviewed model local type')
            for decl in [c for c in children(stmt) if c['kind']=='variable_declarator']:
                name=text(field(decl,'name'))
                if name in env or name in imports:fail(stmt,'Model local shadowing/redeclaration')
                env[name]=typed(evaluate(field(decl,'value')),tags[declared],stmt)
        elif stmt['kind']=='expression_statement':evaluate(children(stmt)[0])
        elif stmt['kind']=='return_statement':returned=typed(evaluate(children(stmt)[0]),'layer',stmt)
        else:fail(stmt,'Unreviewed model statement: '+stmt['kind'])
    if returned is None:fail(method,'Missing model layer return')
    # Multiple meshes or unattached data are rejected, so no geometry silently disappears.
    if len([p for p in nodes if p['parent'] is None])!=1 or returned['mesh']['root'] is not nodes[0]:fail(method,'Multiple model meshes require review')
    bones=[];pivots={};path_lengths={};radius=1.0;cube_count=0
    for part in nodes:
        parent=part['parent'];base=pivots[parent['name']] if parent else [0,0,0]
        pivot=[a+b for a,b in zip(base,part['offset'])];pivots[part['name']]=pivot
        # Parent rotations can undo cancellation in unrotated absolute pivots.
        # Sum segment lengths before cancellation to bound every descendant.
        path_lengths[part['name']]=(path_lengths[parent['name']] if parent else 0)+sum(abs(v) for v in part['offset'])
        bone={'name':part['name'],'pivot':[pivot[0],24-pivot[1],pivot[2]]}
        if parent:bone['parent']=parent['name']
        if any(part['rotation']):bone['rotation']=[math.degrees(v) for v in part['rotation']]
        cubes=[]
        for box in part['cubes']:
            x,y,z=box['position'];dx,dy,dz=box['size'];cube_count+=1
            cube={'origin':[pivot[0]+x,24-pivot[1]-y-dy,pivot[2]+z],'size':[dx,dy,dz],'uv':box['uv']}
            if box['inflate']:cube['inflate']=box['inflate']
            if box['mirror']:cube['mirror']=True
            cubes.append(cube)
            # Deliberately conservative bounds include every possible parent rotation.
            distance=path_lengths[part['name']]+sum(abs(v) for v in box['position']+box['size'])+abs(box['inflate'])*3+24
            radius=max(radius,distance/16)
        if cubes:bone['cubes']=cubes
        bones.append(bone)
    if not cube_count:fail(method,'Empty model layer')
    geometry={'format_version':'1.12.0','minecraft:geometry':[{'description':{
        'identifier':identifier,'texture_width':returned['width'],'texture_height':returned['height'],
        'visible_bounds_width':radius*2,'visible_bounds_height':radius*2,'visible_bounds_offset':[0,0,0]},'bones':bones}]}
    return {'geometry':geometry,'source_sha256':hashlib.sha256(raw).hexdigest(),'class':cls['java_name'],'layer_method':method_name,
        'bones':len(bones),'cubes':cube_count,'scope':'static_layer_only','engine_verified':False,
        'unconverted_methods':[m['name'] for m in cls['methods'] if m is not method],
        'limits':['Animation/render/constructor/gameplay methods are retained in the original source; none are converted by this geometry pass.']}
