"""Build explicit, reusable static entity visual bindings from original Java layers.

The same declaration works for any namespace/model/texture. This exports an
appearance probe, never a replacement for blocked original entity gameplay.
"""
import argparse,hashlib,json,re,struct,tempfile,uuid,zlib
from pathlib import Path,PurePosixPath
from java_entity_geometry import convert,GeometryError

def digest(raw):return hashlib.sha256(raw).hexdigest()

def input_file(root,name):
    if not isinstance(name,str) or not name or '\\' in name or ':' in name or name.startswith('/'):
        raise ValueError('Visual input must be a relative POSIX resource path')
    parts=name.split('/')
    if any(p in ('','.','..') for p in parts):raise ValueError('Unsafe visual resource path')
    path=root.joinpath(*parts)
    for ancestor in [path]+list(path.parents):
        if ancestor==root:break
        if ancestor.is_symlink() or (hasattr(ancestor,'is_junction') and ancestor.is_junction()):raise ValueError('Visual inputs cannot contain links')
    if root not in path.resolve().parents or not path.is_file():raise ValueError('Visual input missing/escaping: '+name)
    return path

def png_dimensions(raw):
    if len(raw)>16*1024*1024 or not raw.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Bounded PNG texture required')
    position=8;size=None;ended=False;compressed=[]
    while position<len(raw):
        if position+12>len(raw):raise ValueError('Truncated PNG chunk')
        length=struct.unpack('>I',raw[position:position+4])[0];kind=raw[position+4:position+8];end=position+12+length
        if end>len(raw):raise ValueError('Truncated PNG payload')
        payload=raw[position+8:position+8+length]
        if zlib.crc32(kind+payload)&0xffffffff!=struct.unpack('>I',raw[end-4:end])[0]:raise ValueError('PNG checksum differs')
        if size is None and kind!=b'IHDR':raise ValueError('PNG header must be first')
        if kind==b'IHDR':
            if size is not None or length!=13:raise ValueError('Invalid/duplicate PNG header')
            w,h,depth,color,compression,filtering,interlace=struct.unpack('>IIBBBBB',payload)
            if not 1<=w<=4096 or not 1<=h<=4096 or depth!=8 or color not in (0,2,4,6) or compression or filtering or interlace:
                raise ValueError('Texture requires noninterlaced 8-bit grayscale/RGB/alpha PNG up to 4096')
            size=(w,h);channels={0:1,2:3,4:2,6:4}[color]
        elif kind==b'IDAT':compressed.append(payload)
        elif kind==b'IEND':
            if length or end!=len(raw):raise ValueError('Invalid PNG ending')
            ended=True;break
        elif kind[:1].isupper() and kind!=b'PLTE':raise ValueError('Unreviewed critical PNG chunk')
        position=end
    if not ended or not compressed:raise ValueError('PNG image data/ending missing')
    expected=h*(1+w*channels);decoder=zlib.decompressobj();image=decoder.decompress(b''.join(compressed),expected+1)
    if len(image)!=expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError('PNG decompressed scanline length differs')
    if any(image[i*(1+w*channels)]>4 for i in range(h)):raise ValueError('PNG scanline filter invalid')
    return size

def build(source,output,config):
    source=Path(source).resolve();output=Path(output).resolve()
    if not source.is_dir() or source==output or source in output.parents or output in source.parents:raise ValueError('Visual output must be separate from input')
    if output.exists():raise ValueError('Visual output already exists')
    if not isinstance(config,dict) or set(config)!={'schema_version','pack_id','entities'} or type(config['schema_version'])!=int or config['schema_version']!=1:
        raise ValueError('Explicit visual declaration schema 1 required')
    pack_id=config['pack_id']
    if not isinstance(pack_id,str) or not re.fullmatch(r'[a-z][a-z0-9_]{1,63}',pack_id):raise ValueError('Invalid visual pack ID')
    entities=config['entities']
    if not isinstance(entities,list) or not 1<=len(entities)<=128:raise ValueError('Visual declarations require 1..128 entities')
    files={};reports=[];ids=set();sources={}
    for entry in entities:
        required={'identifier','model_source','layer_method','texture','collision','health'}
        if not isinstance(entry,dict) or set(entry)!=required:raise ValueError('Unknown/incomplete entity visual declaration')
        identifier=entry['identifier']
        if not isinstance(identifier,str) or not re.fullmatch(r'[a-z][a-z0-9_]*:[a-z][a-z0-9_]*',identifier) or identifier.startswith('minecraft:') or identifier in ids:
            raise ValueError('Unique non-vanilla namespace/entity required')
        ids.add(identifier);namespace,name=identifier.split(':');key=namespace+'__'+name
        if not isinstance(entry['layer_method'],str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',entry['layer_method']):raise ValueError('Invalid layer method')
        collision=entry['collision'];health=entry['health']
        if not isinstance(collision,list) or len(collision)!=2 or any(type(v) not in (float,int) or not 0<v<=16 for v in collision):raise ValueError('Positive bounded collision width/height required')
        if type(health) not in (float,int) or not 0<health<=1024:raise ValueError('Health outside 0..1024')
        model=input_file(source,entry['model_source']);texture=input_file(source,entry['texture'])
        raw=model.read_bytes();png=texture.read_bytes();width,height=png_dimensions(png)
        geometry_id='geometry.'+namespace+'.'+name;controller='controller.render.'+namespace+'.'+name
        result=convert(raw,entry['model_source'],entry['layer_method'],geometry_id)
        description=result['geometry']['minecraft:geometry'][0]['description']
        if (width,height)!=(description['texture_width'],description['texture_height']):raise ValueError('Texture pixel dimensions differ from Java layer')
        sources[entry['model_source']]=digest(raw);sources[entry['texture']]=digest(png)
        files['resource_pack-'+pack_id+'/models/entity/'+key+'.geo.json']=result['geometry']
        files['resource_pack-'+pack_id+'/textures/entity/'+key+'.png']=png
        files['resource_pack-'+pack_id+'/render_controllers/'+key+'.json']={'format_version':'1.8.0','render_controllers':{
            controller:{'geometry':'Geometry.default','materials':[{'*':'Material.default'}],'textures':['Texture.default']}}}
        files['resource_pack-'+pack_id+'/entity/'+key+'.entity.json']={'format_version':'1.10.0','minecraft:client_entity':{'description':{
            'identifier':identifier,'materials':{'default':'entity_alphatest'},'textures':{'default':'textures/entity/'+key},
            'geometry':{'default':geometry_id},'render_controllers':[controller],'spawn_egg':{'base_color':'#527C52','overlay_color':'#E1C887'}}}}
        files['behavior_pack-'+pack_id+'/entities/'+key+'.json']={'format_version':'1.16.0','minecraft:entity':{
            'description':{'identifier':identifier,'is_spawnable':True,'is_summonable':True,'is_experimental':False},
            'components':{'minecraft:collision_box':{'width':collision[0],'height':collision[1]},'minecraft:health':{'value':health,'max':health},
                'minecraft:physics':{'has_gravity':True,'has_collision':True},'minecraft:persistent':{},'minecraft:nameable':{}}}}
        reports.append(dict(entry,model_report={k:v for k,v in result.items() if k!='geometry'},texture_sha256=digest(png)))
    make_uuid=lambda name:str(uuid.uuid5(uuid.NAMESPACE_URL,'neocore:static_visuals:'+pack_id+':'+name))
    resource_header={'name':pack_id+' static appearance test','description':'Original static layer and texture; gameplay/animation not loaded',
        'uuid':make_uuid('resource_header'),'version':[0,8,0],'min_engine_version':[1,20,0]}
    files['resource_pack-'+pack_id+'/manifest.json']={'format_version':2,'header':resource_header,
        'modules':[{'type':'resources','uuid':make_uuid('resource_module'),'version':[0,8,0]}]}
    files['behavior_pack-'+pack_id+'/manifest.json']={'format_version':2,'header':dict(resource_header,uuid=make_uuid('behavior_header')),
        'modules':[{'type':'data','uuid':make_uuid('data_module'),'version':[0,8,0]}],
        'dependencies':[{key:resource_header[key] for key in ('uuid','version')}]}
    report={'schema_version':1,'status':'STATIC_VISUAL_TEST_ONLY','engine_verified':False,'gameplay_loaded':False,
        'entities':reports,'inputs':sources,'limits':['No replacement for original entity gameplay, Java animation, AI, trade UI or mod initialization.',
        'Enable these two appearance-test packs together; do not combine an identifier with a different entity definition.',
        'Geometry conversion alone does not mark a blocked JAR as translated or compatible.']}
    files['entity_visual_report.json']=report
    encoded={name:value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False).encode('utf-8') for name,value in files.items()}
    # Validate everything first. Publish a complete fresh directory as one rename.
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='neocore_visual_',dir=output.parent) as tmp:
        staging=Path(tmp)/'ready';staging.mkdir()
        for name,raw in encoded.items():
            path=staging/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        for name,sha in sources.items():
            if digest(input_file(source,name).read_bytes())!=sha:raise ValueError('Visual input changed during build')
        staging.rename(output)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source');parser.add_argument('output');parser.add_argument('--config',required=True)
    args=parser.parse_args();report=build(args.source,args.output,json.loads(Path(args.config).read_text(encoding='utf-8-sig')))
    print(json.dumps({'status':report['status'],'entities':len(report['entities']),'engine_verified':False}))
