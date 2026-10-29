"""Strict stateless cube_all + exact BlockItem -> NetEase native block candidate.

No mod IDs, guessed variant collapse, rewritten source, or ordinary Item fallback.
"""
import json,math
from build_item_content import identifier

def build(rows,items,read,encode):
    files={};blocks={};textures={};consumed=set();evidence=[]
    def load(path):
        consumed.add(path);return json.loads(read(path))
    for row in rows:
        required={'identifier','java_class','item','destroy_time','explosion_resistance','sound','shape','states'}
        if set(row)!=required or row['java_class']!='net.minecraft.world.level.block.Block' or row['shape']!='cube' or row['states'] or row['sound']!='gravel':raise ValueError('Block requires exact supported stateless cube receipt')
        name=identifier(row['identifier']);ns,path=name.split(':')
        if name.startswith('minecraft:') or name in blocks:raise ValueError('Reserved/duplicate block ID')
        item=items.get(row['item'])
        if row['item']!=name or not item or item['java_class']!='net.minecraft.world.item.BlockItem' or item['max_stack_size']!=64:raise ValueError('Cube requires same-ID exact BlockItem with stack size 64')
        gap=['Subclass gameplay requires target bridge: net.minecraft.world.item.BlockItem']
        if item['unverified_behaviors']!=gap or set(item)-{'identifier','java_class','max_stack_size','unverified_behaviors','creative_tab'}:raise ValueError('Unsupported BlockItem behavior')
        for key in ('destroy_time','explosion_resistance'):
            if type(row[key]) not in (int,float) or not math.isfinite(row[key]) or row[key]<0:raise ValueError('Unsupported block numeric property')
        state=load('assets/'+ns+'/blockstates/'+path+'.json')
        if set(state)!={'variants'} or set(state['variants'])!={''} or set(state['variants'][''])!={'model'}:raise ValueError('Only one stateless block model is supported')
        model_id=identifier(state['variants']['']['model']);mn,mp=model_id.split(':')
        model=load('assets/'+mn+'/models/'+mp+'.json')
        if set(model)!={'parent','textures'} or model['parent']!='minecraft:block/cube_all' or set(model['textures'])!={'all'}:raise ValueError('Only exact cube_all models are supported')
        item_model=load('assets/'+ns+'/models/item/'+path+'.json')
        if item_model!={'parent':model_id}:raise ValueError('Block item model must inherit its block model')
        texture=identifier(model['textures']['all']);tn,tp=texture.split(':')
        png_path='assets/'+tn+'/textures/'+tp+'.png';raw=read(png_path);consumed.add(png_path)
        if not raw.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Invalid cube PNG')
        target_texture='textures/'+tn+'/'+tp;files['resource/'+target_texture+'.png']=raw
        textures[name]={'textures':target_texture}
        loot_path='data/'+ns+'/loot_table/blocks/'+path+'.json';loot=load(loot_path)
        if set(loot)-{'type','pools','random_sequence'} or loot.get('type')!='minecraft:block' or len(loot.get('pools',[]))!=1:raise ValueError('Only single-pool block loot is supported')
        pool=loot['pools'][0]
        if set(pool)-{'rolls','bonus_rolls','entries','conditions'} or pool.get('rolls')!=1 or pool.get('bonus_rolls',0)!=0 or pool.get('entries')!=[{'type':'minecraft:item','name':name}] or pool.get('conditions',[]) not in ([],[{'condition':'minecraft:survives_explosion'}]):raise ValueError('Only single self-drop loot supports the ordinary cube candidate')
        target_loot='loot_tables/blocks/'+ns+'/'+path+'.json'
        files['behavior/'+target_loot]=encode({'pools':[{'rolls':1,'entries':[{'type':'item','name':name,'weight':1}]}]})
        tab=item.get('creative_tab')
        if tab not in (None,'minecraft:building_blocks'):raise ValueError('Unreviewed block creative tab')
        description={'identifier':name,'register_to_creative_menu':tab is not None}
        components={'minecraft:destroy_time':{'value':row['destroy_time']},
                    'minecraft:explosion_resistance':{'value':row['explosion_resistance']},
                    'minecraft:loot':{'table':target_loot},'netease:solid':{'value':True},
                    'netease:aabb':{'collision':{'min':[0,0,0],'max':[1,1,1]},'clip':{'min':[0,0,0],'max':[1,1,1]}}}
        files['behavior/netease_blocks/'+ns+'/'+path+'.json']=encode({'format_version':'1.10.0','minecraft:block':{'description':description,'components':components}})
        blocks[name]={'textures':name,'sound':row['sound']}
        item['unverified_behaviors']=[];item['block']=name
        evidence.append(dict(row,target={'destroy_time':row['destroy_time'],'explosion_resistance':row['explosion_resistance']},loot={'table':target_loot,'source_conditions':pool.get('conditions',[]),'random_sequence':loot.get('random_sequence'),'explosion_parity':'PENDING_REAL_ENGINE'}))
    if blocks:
        files['resource/blocks.json']=encode(dict({'format_version':[1,1,0]},**blocks))
        files['resource/textures/terrain_texture.json']=encode({'resource_pack_name':'neocore_blocks','texture_name':'atlas.terrain','padding':8,'num_mip_levels':4,'texture_data':textures})
    return {'files':files,'blocks':evidence,'consumed':consumed}
