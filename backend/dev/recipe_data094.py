"""Versioned, bounded recipe IR. Development only; never executes source Java."""
import hashlib,itertools,json,re
from pathlib import Path

ID=re.compile(r'[a-z0-9_.-]+:[a-z0-9_./-]+\Z')
class Unsupported(ValueError):
    def __init__(self,category,message):self.category=category;super().__init__(message)
def identifier(value):
    if not isinstance(value,str) or not ID.fullmatch(value) or any(x in ('','.','..') for x in value.split(':')[1].split('/')):
        raise Unsupported('INVALID_ID','Invalid resource identity: '+str(value))
    return value
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'))

class Resolver:
    def __init__(self,items,tags=None):
        self.items=items;self.tags=tags or {};self.references=set();self.tag_evidence={}
    def item(self,name):
        name=identifier(name);self.references.add(name)
        if name not in self.items:
            raise Unsupported('NATIVE_ID_UNMAPPED' if name.startswith('minecraft:') else 'MISSING_EXTERNAL_DEPENDENCY','No reviewed target item identity: '+name)
        return self.items[name].get('target_id',name)
    def ingredient(self,value,seen=()):
        if isinstance(value,list):
            if not value:raise Unsupported('INVALID_INGREDIENT','Empty ingredient alternatives')
            return sorted({x for row in value for x in self.ingredient(row,seen)})
        if not isinstance(value,dict) or len(value)!=1:raise Unsupported('INVALID_INGREDIENT','Expected exactly item or tag')
        if 'item' in value:
            target=self.item(value['item']);metadata=self.items[value['item']]
            if metadata.get('max_stack_size',64)==1 and not metadata.get('is_block',False):
                raise Unsupported('ITEM_STATE_MAPPING_UNVERIFIED','Non-stackable ingredient requires reviewed damage/state matching: '+value['item'])
            return [target]
        if 'tag' not in value:raise Unsupported('INVALID_INGREDIENT','Unknown ingredient fields')
        name=identifier(value['tag'])
        if name in seen:raise Unsupported('TAG_CYCLE','Cyclic item tag: '+name)
        if name not in self.tags:raise Unsupported('UNKNOWN_TAG','No version-locked Java tag definition: '+name)
        data=self.tags[name]
        if not isinstance(data,dict) or set(data)-{'replace','values'} or not isinstance(data.get('values'),list) or type(data.get('replace',False)) is not bool:
            raise Unsupported('INVALID_TAG','Unknown tag semantics: '+name)
        members=[]
        for member in data['values']:
            required=True
            if isinstance(member,dict):
                if set(member)!={'id','required'} or type(member['required']) is not bool:raise Unsupported('INVALID_TAG','Invalid tag member')
                member,required=member['id'],member['required']
            if not isinstance(member,str):raise Unsupported('INVALID_TAG','Invalid tag member identity')
            identity=identifier(member[1:] if member.startswith('#') else member)
            absent=identity not in (self.tags if member.startswith('#') else self.items)
            if not required and absent and (member.startswith('#') or not identity.startswith('minecraft:')):
                self.tag_evidence.setdefault(name,[]).append({'optional_member':member,'status':'ABSENT_OPTIONAL','reason':'Identity absent from the selected closed tag/item profile'})
                continue
            # An existing optional tag must still resolve its required children.
            # Cycles, invalid data and item-state gaps can never become absence.
            members.extend(self.ingredient({'tag':identity} if member.startswith('#') else {'item':identity},seen+(name,)))
        if not members:raise Unsupported('EMPTY_TAG','No available tag members: '+name)
        self.tag_evidence.setdefault(name,[]).append({'resolved_members':sorted(set(members))})
        return sorted(set(members))

def convert_recipe(data,recipe_id,resolver,unlock=None,max_variants=128):
    recipe_id=identifier(recipe_id)
    if not isinstance(data,dict):raise Unsupported('INVALID_JSON_STRUCTURE','Recipe must be an object')
    kind=data.get('type')
    ir={'schema_version':1,'identifier':recipe_id,'source_type':kind,'raw':data,'unknown_fields':[],
        'source_version':'1.21.1','engine_verified':False}
    if kind=='minecraft:smithing':
        raise Unsupported('SOURCE_VERSION_FORMAT_INVALID','Legacy smithing type is not the 1.21.1 smithing_transform/trim format')
    if kind not in ('minecraft:crafting_shaped','minecraft:crafting_shapeless','minecraft:stonecutting'):
        raise Unsupported('TARGET_SEMANTICS_UNSUPPORTED','Smelting time/experience and smithing item state require explicit equivalent target support: '+str(kind))
    fields={'type','category','group','result','show_notification'}|({'pattern','key'} if kind.endswith('shaped') and not kind.endswith('shapeless') else {'ingredients'} if kind.endswith('shapeless') else {'ingredient','count'})
    extra=set(data)-fields;ir['unknown_fields']=sorted(extra)
    if extra:raise Unsupported('UNSUPPORTED_FIELDS','Required recipe fields not supported: '+', '.join(sorted(extra)))
    for key in ('group',):
        if key in data and not isinstance(data[key],str):raise Unsupported('INVALID_JSON_STRUCTURE','Invalid '+key)
    if kind.startswith('minecraft:crafting_'):
        # Both pinned 1.21.1 serializers use fieldOf("category").orElse(MISC):
        # a decoding error, including a wrong JSON type, also selects MISC.
        category=data.get('category')
        valid=isinstance(category,str) and category in ('building','redstone','equipment','misc')
        ir['effective_category']=category if valid else 'misc'
        if 'category' in data and not valid:
            ir['codec_fallbacks']=[dict(field='category',raw=category,effective='misc',
                evidence='Minecraft 1.21.1 ShapedRecipe/ShapelessRecipe Serializer: MapCodec.orElse(CraftingBookCategory.MISC)')]
    if 'show_notification' in data and type(data['show_notification']) is not bool:raise Unsupported('INVALID_JSON_STRUCTURE','Invalid notification flag')
    result=data.get('result')
    if not isinstance(result,dict) or set(result)-{'id','count'} or 'id' not in result:raise Unsupported('SOURCE_VERSION_FORMAT_INVALID','1.21.1 requires a result object with id/count; components need a separate contract')
    count=result.get('count',1)
    if type(count) is not int or not 1<=count<=64:raise Unsupported('INVALID_COUNT','Output count must be 1..64')
    target_result=resolver.item(result['id'])
    if count>resolver.items[result['id']].get('max_stack_size',64):raise Unsupported('INVALID_COUNT','Output exceeds reviewed native stack limit')
    shaped=kind=='minecraft:crafting_shaped'
    if shaped:
        pattern=data.get('pattern');keys=data.get('key')
        if (not isinstance(pattern,list) or not 1<=len(pattern)<=3 or any(not isinstance(row,str) or not 1<=len(row)<=3 for row in pattern)
                or len({len(row) for row in pattern})!=1 or not isinstance(keys,dict)):
            raise Unsupported('INVALID_SHAPE','Expected a rectangular 1..3 by 1..3 shape')
        symbols=set(''.join(pattern))-{' '}
        if not symbols or set(keys)!=symbols or any(len(k)!=1 or k==' ' for k in keys):raise Unsupported('INVALID_SHAPE','Unused or missing shaped ingredient symbols')
        labels=sorted(symbols);choices=[resolver.ingredient(keys[k]) for k in labels]
        ir.update(pattern=pattern,key=keys,workstation='crafting_table')
    elif kind=='minecraft:crafting_shapeless':
        ingredients=data.get('ingredients')
        if not isinstance(ingredients,list) or not 1<=len(ingredients)<=9:raise Unsupported('INVALID_INGREDIENT','Expected 1..9 shapeless ingredients')
        labels=list(range(len(ingredients)));choices=[resolver.ingredient(v) for v in ingredients]
        ir.update(ingredients=ingredients,workstation='crafting_table')
    else:
        if 'count' in data:raise Unsupported('SOURCE_VERSION_FORMAT_INVALID','Legacy stonecutting count/result syntax is not 1.21.1')
        labels=[0];choices=[resolver.ingredient(data.get('ingredient'))]
        ir.update(ingredients=[data.get('ingredient')],workstation='stonecutter')
    total=1
    for choice in choices:total*=len(choice)
    if total>max_variants:raise Unsupported('VARIANT_LIMIT','Explicit ingredient expansion exceeds '+str(max_variants))
    targets=[];seen=set()
    for combination in itertools.product(*choices):
        body={'description':{'identifier':recipe_id},'tags':[ir['workstation']], 'result':{'item':target_result,'count':count}}
        if shaped:
            body.update(pattern=data['pattern'],key={label:{'item':item} for label,item in zip(labels,combination)})
        else:body['ingredients']=[{'item':item} for item in combination]
        signature=canonical({k:v for k,v in body.items() if k!='description'})
        if signature in seen:continue
        seen.add(signature)
        if total>1:body['description']['identifier']=recipe_id+'/nc_variant_'+str(len(targets))
        if unlock:body['unlock']=[{'item':resolver.item(name)} for name in unlock]
        targets.append({'format_version':'1.20.10' if unlock else '1.12','minecraft:recipe_shaped' if shaped else 'minecraft:recipe_shapeless':body})
    ir.update(result=result,variant_count=len(targets),unlock=list(unlock or []),
              unlock_evidence_scope='Supplied advancement inventory criteria' if unlock else 'No advancement unlock supplied; manual crafting mapped, book visibility/limited-crafting not verified',
              known_ui_differences=[name for name in ('category','group','show_notification') if name in data])
    return ir,targets

def load_profile():
    root=Path(__file__).parent/'profiles'
    profile=json.loads((root/'netease_pc_3_9_items.json').read_bytes())
    if profile.get('profile')!='netease_pc_catalog_3_9_identity_aux0':raise ValueError('Wrong native identity profile')
    official=json.loads((root/'minecraft_1_21_1_item_tags.json').read_bytes())
    profile['java_tag_source']=official['source']
    profile['java_tags']={path.split('/')[1]+':'+path.split('/tags/item/',1)[1][:-5]:row['data'] for path,row in official['tags'].items()}
    profile['profile_hashes']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob('*.json'))}
    return profile

def convert_tree(source,profile,target_version='1.21.1'):
    source=Path(source)
    if target_version!='1.21.1':raise ValueError('No reviewed recipe path/format rules for this source version')
    rows,files,tags=[],{},dict(profile.get('java_tags',{}))
    for path in sorted((source/'data').glob('*/tags/item/**/*.json')):
        parts=path.relative_to(source).parts;name=parts[1]+':'+ '/'.join(parts[4:])[:-5]
        # Only this explicitly selected source pack contributes to a closed local tag.
        # Vanilla tags require their separate version-locked official definitions.
        try:
            data=json.loads(path.read_bytes())
            if name in tags and not data.get('replace',False):
                data=dict(data,values=tags[name]['values']+data['values'])
            tags[name]=data
        except (ValueError,TypeError,AttributeError,KeyError):tags[name]={'invalid':True}
    candidates=[]
    for path in sorted((source/'data').rglob('*.json')):
        parts=path.relative_to(source).parts
        if len(parts)>=4 and parts[2] in ('recipe','recipes'):candidates.append(path)
    active_ids={};all_ids={}
    for path in candidates:
        parts=path.relative_to(source).parts;key=parts[1]+':'+ '/'.join(parts[3:])[:-5]
        all_ids.setdefault(key,[]).append(path.relative_to(source).as_posix())
        if parts[2]=='recipe':active_ids.setdefault(key,[]).append(path)
    for path in candidates:
        raw=path.read_bytes();parts=path.relative_to(source).parts;key=parts[1]+':'+ '/'.join(parts[3:])[:-5]
        row=dict(source=path.relative_to(source).as_posix(),source_sha256=hashlib.sha256(raw).hexdigest(),identifier=key,
                 source_version=target_version,engine_verified=False,outputs=[],known_blockers=[])
        rows.append(row)
        if parts[2]!='recipe':row.update(status='VERSION_NOT_APPLICABLE',reason='1.21.1 loads recipe/, not legacy recipes/');continue
        resolver=Resolver(profile['items'],tags)
        try:
            identifier(key)
            if len(active_ids[key])!=1:raise Unsupported('OUTPUT_CONFLICT','Duplicate active recipe identity')
            data=json.loads(raw);row['raw']=data
            ir,targets=convert_recipe(data,key,resolver);row['ir']=ir
            for i,target in enumerate(targets):
                name='behavior/netease_recipes/'+key.replace(':','/')+('' if len(targets)==1 else '/nc_variant_'+str(i))+'.json'
                if name in files:
                    for owner in rows:
                        if name in owner['outputs']:
                            owner.update(status='OUTPUT_CONFLICT',reason='Another source recipe expands to this target identity')
                            for old in owner['outputs']:files.pop(old,None)
                            owner['outputs']=[]
                    raise Unsupported('OUTPUT_CONFLICT','Duplicate target path')
                files[name]=json.dumps(target,ensure_ascii=False,sort_keys=True,indent=2).encode('utf-8');row['outputs'].append(name)
            row.update(status='CONVERTED_REVIEW_REQUIRED',reason='Static target data generated; engine/workstation behavior pending')
        except (Unsupported,ValueError,TypeError,KeyError) as error:
            row.update(status=error.category if isinstance(error,Unsupported) else 'INVALID_JSON',reason=str(error))
            for name in row['outputs']:files.pop(name,None)
            row['outputs']=[]
        finally:
            row['item_references']=sorted(resolver.references);row['tag_resolution']=resolver.tag_evidence
            row['unknown_followup_blockers']=row['status']!='CONVERTED_REVIEW_REQUIRED'
            # Collect all independent unresolved direct item references, not only the first one.
            def scan(value,parent=None):
                if isinstance(value,dict):
                    for name,v in value.items():
                        if (name=='item' or name=='id' and parent=='result') and isinstance(v,str) and ':' in v and v not in profile['items']:
                            row['known_blockers'].append({'category':'NATIVE_ID_UNMAPPED' if v.startswith('minecraft:') else 'MISSING_EXTERNAL_DEPENDENCY','item':v})
                        scan(v,name)
                elif isinstance(value,list):
                    for v in value:scan(v,parent)
            scan(row.get('raw'))
    counts={status:sum(row['status']==status for row in rows) for status in sorted({r['status'] for r in rows})}
    return dict(files=files,report=dict(schema_version=1,source_version=target_version,source_kind='DATA_ONLY',
        input_recipes=len(rows),active_recipes=sum(row['status']!='VERSION_NOT_APPLICABLE' for row in rows),
        status_counts=counts,rows=rows,output_files=len(files),native_profile_source=profile.get('source'),
        java_tag_source=profile.get('java_tag_source'),profile_hashes=profile.get('profile_hashes'),
        path_id_overlaps={key:paths for key,paths in all_ids.items() if len(paths)>1},engine_verified=False,
        limitations=['Literal native ID presence does not establish all Java item-state equivalence.',
                     'Version-locked vanilla plus selected-pack tags only; missing required tag members block.',
                     'Crafting-book UI grouping/notification may differ; preserved in IR.',
                     'First failure plus independently scanned direct IDs; later semantic blockers remain unknown.']))
