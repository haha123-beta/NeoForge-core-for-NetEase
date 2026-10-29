"""Bounded Java item resources -> NetEase 1.10 definitions, by registered ID.

This is a build tool. No input code is executed and no engine success is inferred.
"""
import hashlib
import json
import re
from pathlib import Path

PROFILE = 'netease_pc_item_1_10'
ID = re.compile(r'[a-z0-9_.-]+:[a-z0-9_./-]+\Z')


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError('Invalid item/resource ID: ' + str(value))
    if any(part in ('', '.', '..') for part in value.split(':')[1].split('/')):
        raise ValueError('Unsafe resource ID: ' + value)
    return value


def build(source, pack_id, declaration):
    source = Path(source).resolve()
    if set(declaration)-{'schema_version', 'profile', 'items', 'native_items','blocks'} or not {'schema_version','profile','items','native_items'}<=set(declaration):
        raise ValueError('Expected explicit item identity declaration')
    if declaration['schema_version'] != 1 or declaration['profile'] != PROFILE:
        raise ValueError('Unsupported target item profile')
    files, identities, texture_data, issues, evidence = {}, {}, {}, [], []
    def encode(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')
    def read(relative):
        path = source / relative
        if source not in path.resolve().parents or path.is_symlink():
            raise ValueError('Item resource escapes source: ' + relative)
        data = path.read_bytes()
        evidence.append({'path': relative, 'sha256': hashlib.sha256(data).hexdigest()})
        return data
    def item_ref(value):
        name = identifier(value)
        if name not in identities and name not in declaration['native_items']:
            raise ValueError('Unmapped recipe item ID: ' + name)
        return {'item': name}
    native = declaration['native_items']
    if not isinstance(native, list) or len(native) != len(set(native)):
        raise ValueError('native_items must list unique explicitly reviewed native IDs')
    for name in native:
        if not identifier(name).startswith('minecraft:'):
            raise ValueError('Native identity list cannot claim mod content: ' + name)
    for row in declaration['items']:
        required = {'identifier', 'java_class', 'max_stack_size', 'unverified_behaviors'}
        if not required <= set(row) or set(row)-required-{'fuel','creative_tab'}:
            raise ValueError('Item row requires class, stack size and explicit behavior gaps')
        name = identifier(row['identifier'])
        if name.startswith('minecraft:') or name in identities:
            raise ValueError('Duplicate/reserved item identity: ' + name)
        if type(row['max_stack_size']) is not int or not 1 <= row['max_stack_size'] <= 64:
            raise ValueError('Unsupported max stack size: ' + name)
        if not isinstance(row['java_class'], str) or not row['java_class']:
            raise ValueError('Missing registered Java class: ' + name)
        if (not isinstance(row['unverified_behaviors'], list)
                or any(not isinstance(reason,str) or not reason for reason in row['unverified_behaviors'])):
            raise ValueError('Behavior gaps must be explicit')
        identities[name] = dict(row)
    if not identities:
        raise ValueError('No registered item identities supplied')
    from build_block_content import build as build_blocks
    block_data=build_blocks(declaration.get('blocks',[]),identities,read,encode)
    files.update(block_data['files'])
    for name, row in sorted(identities.items()):
        if row.get('block'):continue
        ns, path = name.split(':')
        model_path = 'assets/' + ns + '/models/item/' + path + '.json'
        model = json.loads(read(model_path))
        if set(model) != {'parent', 'textures'} or model['parent'] != 'minecraft:item/generated' or set(model['textures']) != {'layer0'}:
            raise ValueError('Only plain generated single-layer item models are supported: ' + model_path)
        texture = identifier(model['textures']['layer0'])
        tn, tp = texture.split(':')
        raw = read('assets/' + tn + '/textures/' + tp + '.png')
        if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('Invalid item PNG: ' + texture)
        target = 'textures/' + tn + '/' + tp
        files['resource/' + target + '.png'] = raw
        texture_data[name] = {'textures': target}
        # Namespaced path stays a path, avoiding lossy underscore collisions.
        filename = ns + '/' + path + '.json'
        components = {'minecraft:max_stack_size':row['max_stack_size']}
        if row.get('fuel') is not None:
            fuel=row['fuel']
            if (not isinstance(fuel,dict) or set(fuel)!={'ticks','proof'} or type(fuel['ticks']) is not int
                    or not 0 <= fuel['ticks'] <= 2147483647 or not isinstance(fuel['proof'],dict)
                    or set(fuel['proof'])!={'abi','kind','field','java_source_sha256','descriptor'}
                    or fuel['proof'].get('abi')!=1 or fuel['proof'].get('kind')!='CONSTANT_FUEL_PRIVATE_FIELD'
                    or not re.fullmatch(r'[0-9a-f]{64}',fuel['proof'].get('java_source_sha256',''))):
                raise ValueError('Fuel requires a compiler-proven context-independent accessor: '+name)
            if fuel['ticks']:
                components['netease:fuel'] = {'duration':fuel['ticks']/20.0}
        tab = row.get('creative_tab')
        if tab not in (None,'minecraft:ingredients'):
            raise ValueError('Creative tab requires an explicit target mapping: '+str(tab))
        description = {'identifier':name,'register_to_create_menu':tab is not None}
        if tab is not None:
            description['category'] = 'Items'
        files['behavior/netease_items_beh/' + filename] = encode({
            'format_version': '1.10', 'minecraft:item': {
                'description':description, 'components':components}})
        files['resource/netease_items_res/' + filename] = encode({
            'format_version': '1.10', 'minecraft:item': {
                'description': {'identifier': name}, 'components': {'minecraft:icon': name}}})
        for reason in row['unverified_behaviors']:
            issues.append({'item': name, 'category': 'RUNTIME_BEHAVIOR_UNVERIFIED', 'reason': reason})
    files['resource/textures/item_texture.json'] = encode({
        'resource_pack_name': pack_id, 'texture_name': 'atlas.items', 'texture_data': texture_data})
    from build_localization import build as build_language
    key_map={'item.'+name.replace(':','.'):['item.'+name+'.name'] for name in identities}
    for block in block_data['blocks']:
        name=block['identifier'];key_map.pop('item.'+name.replace(':','.'),None)
        key_map['block.'+name.replace(':','.')]=['tile.'+name+'.name']
    localization=build_language(source,key_map,read)
    files.update(localization['files']);issues.extend(localization['issues'])
    recipes = []
    unlocks, advancement_paths = {}, set()
    for path in sorted((source/'data').rglob('*.json')):
        parts=path.relative_to(source).parts
        if len(parts)<4 or parts[2] not in ('advancement','advancements'):
            continue
        relative=path.relative_to(source).as_posix()
        data=json.loads(read(relative))
        try:
            if (set(data)-{'parent','criteria','requirements','rewards'} or data.get('parent')!='minecraft:recipes/root'
                    or set(data.get('rewards',{}))!={'recipes'} or len(data['rewards']['recipes'])!=1):
                raise ValueError('Not a pure recipe-unlock advancement')
            recipe_id=identifier(data['rewards']['recipes'][0])
            criteria=data['criteria'];requirements=data['requirements']
            if len(requirements)!=1 or set(requirements[0])!=set(criteria):
                raise ValueError('Only one OR group is supported')
            inventory=[];self_unlock=False
            for row in criteria.values():
                if set(row)!={'trigger','conditions'}:
                    raise ValueError('Unknown criterion fields')
                condition=row['conditions']
                if row['trigger']=='minecraft:recipe_unlocked' and condition=={'recipe':recipe_id}:
                    self_unlock=True
                elif row['trigger']=='minecraft:inventory_changed' and set(condition)=={'items'}:
                    predicates=condition['items']
                    if len(predicates)!=1 or set(predicates[0])!={'items'} or len(predicates[0]['items'])!=1:
                        raise ValueError('Complex inventory predicate')
                    item=predicates[0]['items'][0];item_ref(item)
                    inventory.append(item)
                else:raise ValueError('Unknown recipe-unlock trigger')
            if not inventory or not self_unlock or recipe_id in unlocks:
                raise ValueError('Ambiguous recipe unlock')
            unlocks[recipe_id]=inventory;advancement_paths.add(relative)
        except (ValueError,KeyError,TypeError) as error:
            issues.append({'source':relative,'category':'UNCONVERTED_DATA','reason':str(error)})
    recipe_version_skips=[]
    for path in sorted((source / 'data').rglob('*.json')):
        relative = path.relative_to(source).as_posix()
        parts = path.relative_to(source).parts
        if relative in block_data['consumed']:continue
        if block_data['blocks'] and len(parts)>=5 and parts[2:4]==('tags','block'):
            data=json.loads(read(relative))
            values=data.get('values') if isinstance(data,dict) else None
            # Invalid IDs are rejected by Java ResourceLocation too. Preserve
            # the source defect and never turn a spaced ID into another block.
            if isinstance(values,list) and any(not isinstance(value,str) or not ID.fullmatch(value) for value in values):
                issues.append({'source':relative,'category':'SOURCE_INVALID_TAG','reason':'Invalid Java resource identifier; original tag is not repaired or applied','values':values})
                continue
        if len(parts) < 4 or parts[2] not in ('recipe', 'recipes'):
            if relative not in advancement_paths and not any(i.get('source')==relative for i in issues):
                issues.append({'source': relative, 'category': 'UNCONVERTED_DATA'})
            continue
        if parts[2]=='recipes':
            read(relative)
            recipe_version_skips.append({'source':relative,'status':'VERSION_NOT_APPLICABLE','source_version':'1.21.1'})
            continue
        data = json.loads(read(relative))
        from recipe_data094 import Resolver,convert_recipe
        reviewed = dict(identities)
        reviewed.update({name:{'target_id':name,'max_stack_size':64} for name in native})
        recipe_id=identifier(parts[1]+':'+ '/'.join(parts[3:])[:-5])
        ir,targets=convert_recipe(data,recipe_id,Resolver(reviewed),unlocks.get(recipe_id))
        if len(targets)!=1:
            raise ValueError('Item content recipe variants require an explicit expanded resource contract')
        files['behavior/netease_recipes/'+parts[1]+'/'+ '/'.join(parts[3:])] = encode(targets[0])
        recipes.append(recipe_id)
    contract = {'schema_version':1, 'profile':PROFILE, 'pack_id':pack_id,
                'items':list(identities.values()), 'native_items':list(native)}
    if block_data['blocks']:contract['blocks']=block_data['blocks']
    for name in set(unlocks)-set(recipes):
        issues.append({'source':name,'category':'UNCONVERTED_DATA','reason':'Unlock references a missing recipe'})
    consumed = {row['path'] for row in evidence}
    for path in sorted((source/'assets').rglob('*')):
        if path.is_file() and path.relative_to(source).as_posix() not in consumed:
            issues.append({'source':path.relative_to(source).as_posix(), 'category':'UNCONVERTED_ASSET'})
    contract['unconverted_content'] = [row for row in issues if row['category'] not in ('RUNTIME_BEHAVIOR_UNVERIFIED','SOURCE_INVALID_TAG')]
    return {'contract':contract, 'files':files, 'report':{
        'status':'ITEM_CONTENT_CANDIDATE', 'engine_verified':False,
        'items':sorted(identities),'recipes':recipes,'locales':localization['locales'],'localization_fallbacks':localization['fallbacks'],
        'blocks':block_data['blocks'],
        'issues':issues,'source_evidence':evidence,'recipe_unlocks':unlocks,'recipe_version_skips':recipe_version_skips,
        'limits':(['Ordinary stateless cube placement, collision, mining and self-drop use native block definitions; real-engine verification is pending.',
                   'Java building_blocks maps to native block creative registration; layout/order differs.',
                   'Java survives_explosion and random_sequence remain recorded; native explosion decay/RNG equivalence requires real-engine evidence.',
                   'Native hardness and explosion resistance parameter mapping requires target-engine measurement.'] if block_data['blocks'] else [])+['Java ingredients tab maps to the native Items category; native layout/order differs.',
                  'Fuel supports only compiler-proven constant private fields without dynamic fuel listeners.',
                  'Only listed native item identities are accepted; review their target version.',
                  'Required behavior gaps remain explicit; definitions do not prove gameplay.']}}
