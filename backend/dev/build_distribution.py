"""Build independent NeoCore protocol-2 and content behavior packs for engine testing."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import uuid
import zipfile
from build_source_bundle import SCRIPTS, core_bundle, content_bundle

DEV = Path(__file__).resolve().parent
RELEASE_VERSION = (1, 0, 0)


def copy_runtime_files(root, destination, allowed, excluded):
    """Project delivery policy, not a claim about NetEase's complete whitelist."""
    root, destination = Path(root), Path(destination)
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise ValueError('Runtime delivery refuses links: ' + str(path))
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if '__pycache__' in relative.parts or path.suffix.lower() not in allowed:
            excluded.append({'source': str(path), 'reason': 'Outside selected runtime file types'})
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def snapshot(path, bundle):
    payload = json.dumps(bundle, ensure_ascii=True, sort_keys=True)
    path.write_text('# -*- coding: utf-8 -*-\n# Generated source snapshot; regenerate after edits.\n'
                    'import json\nBUNDLE = json.loads(' + repr(payload) + ')\n', encoding='utf-8')


def manifest(pack_id, script_package, dependencies=()):
    make_uuid = lambda suffix: str(uuid.uuid5(uuid.NAMESPACE_URL, 'neocore:distribution:' + pack_id + ':' + suffix))
    return {'format_version': 2, 'header': {'name': pack_id,
        'description': 'NeoCore source distribution: engine validation pending',
        'uuid': make_uuid('header'), 'version': list(RELEASE_VERSION), 'min_engine_version': [1, 20, 0]},
        # NetEase Python is discovered through Scripts/modMain.py and Mod.Binding.
        # The international Bedrock script module selects a different runtime.
        'modules': [{'type': 'data', 'uuid': make_uuid('data'), 'version': list(RELEASE_VERSION)}],
        'dependencies': list(dependencies)}


def write_pack_archive(pack, destination):
    """Retain empty engine marker directories such as entities/ in ZIPs."""
    pack, destination = Path(pack), Path(destination)
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(pack.rglob('*')):
            if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                raise ValueError('Pack archive refuses links: ' + str(path))
            name = pack.name + '/' + path.relative_to(pack).as_posix()
            if path.is_dir():
                archive.writestr(name + '/', b'', compress_type=zipfile.ZIP_STORED)
            elif path.is_file():
                if path.stat().st_size == 0:
                    archive.writestr(name, b'', compress_type=zipfile.ZIP_STORED)
                else:
                    archive.write(path, name)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def build_data(output, pack_id, files, report, partial=False):
    """The same pack/manifest writer, without inventing a Python mod entrypoint."""
    if not re.fullmatch(r'[a-z][a-z0-9_]{1,63}',pack_id):raise ValueError('Invalid data pack ID')
    if not files:raise ValueError('Cannot publish an empty data candidate')
    output=Path(output)
    if output.exists():raise ValueError('Distribution output already exists')
    label=pack_id+'_subset' if partial else pack_id
    pack=output/('behavior_pack-'+label);pack.mkdir(parents=True)
    (pack/'entities').mkdir()
    for name,raw in files.items():
        if not name.startswith('behavior/netease_recipes/') or not name.endswith('.json'):
            raise ValueError('Data-only output is not a reviewed recipe')
        data=json.loads(raw)
        kinds=set(data)-{'format_version'}
        if len(kinds)!=1 or not kinds<={'minecraft:recipe_shaped','minecraft:recipe_shapeless'} or data.get('format_version') not in ('1.12','1.20.10'):
            raise ValueError('Unreviewed native recipe schema')
        body=data[next(iter(kinds))]
        if not {'description','tags','result'}<=set(body):raise ValueError('Incomplete native recipe')
        relative=Path(name.split('/',1)[1])
        if relative.is_absolute() or '..' in relative.parts:raise ValueError('Data output path escapes pack')
        path=pack/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    value=manifest(label,None)
    target_version=(report.get('native_profile_source') or {}).get('vanilla_manifest_min_engine_version')
    if target_version is not None:
        if not isinstance(target_version,list) or len(target_version)!=3 or any(type(x) is not int or x<0 for x in target_version):
            raise ValueError('Invalid version-locked native profile')
        value['header']['min_engine_version']=target_version
    value['header']['name']=label+(' [PARTIAL EXPERIMENT - NOT FULL MOD]' if partial else ' [ENGINE VALIDATION PENDING]')
    write_json(pack/'manifest.json',value)
    write_json(pack/'data_conversion_scope.json',dict(source_mod=pack_id,partial=partial,engine_verified=False,
        input_recipes=report['input_recipes'],active_recipes=report['active_recipes'],status_counts=report['status_counts']))
    result=dict(protocol=2,source_kind='DATA_ONLY',engine_verified=False,partial=partial,
        contents=[dict(pack_id=label,pack_path=pack.name,script_package=None,modules=0,mod_ids=[pack_id],compatibility_issues=[])],
        core_modules=0,dependency_on_neocore=False)
    write_json(output/'distribution_report.json',result)
    return result


def build(output, contents, layout='legacy', platform_versions=None):
    if layout not in ('legacy', 'resources'):
        raise ValueError('Unsupported content layout: ' + str(layout))
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Distribution output already exists')
    prepared, ids = [], set()
    visual_data = {}
    item_data = {}
    excluded_files = []
    for content in contents:
        pack_id = content['pack_id']
        if not re.fullmatch(r'[a-z][a-z0-9_]{1,63}', pack_id) or pack_id in ids or pack_id == 'neocore':
            raise ValueError('Invalid or duplicate content pack ID')
        ids.add(pack_id)
        root = Path(content['folder']).resolve()
        if root == output or root in output.parents or output in root.parents:
            raise ValueError('Distribution output overlaps a content input')
        for path in root.rglob('*'):
            if root not in path.resolve().parents:
                raise ValueError('Input link escapes content root')
        if root.name == pack_id + "Scripts":
            raise ValueError("Original folder conflicts with generated Scripts folder")
        bundle = content_bundle(root, content['entrypoints'], content.get('side', 'BOTH'))
        if layout == 'resources':
            if 'runtime_requirements' not in bundle:
                raise ValueError('Resources layout requires generated translation requirements')
            if (root/'_nc_resources.py').exists() or (root/'__init__.py').exists():
                raise ValueError('Content conflicts with generated native resources package/index')
        prepared.append((pack_id, root, bundle))
        if content.get('items') is not None:
            from build_item_content import build as build_items
            data = build_items(root, pack_id, content['items'])
            owners = sorted(row['mod_id'] for row in bundle['mods'])
            if any(row['identifier'].split(':')[0] not in owners for row in data['contract']['items']):
                raise ValueError('Content items cannot claim another mod namespace')
            bundle['item_content'] = dict(data['contract'], owners=owners)
            item_data[pack_id] = data
        if content.get('visuals') is not None:
            from build_entity_visuals import build as build_visuals
            options=content['visuals']
            if not isinstance(options,dict) or set(options)!={'source','declaration'}:raise ValueError('Visuals require source and declaration')
            declaration=options['declaration']
            if not isinstance(declaration,dict) or declaration.get('pack_id')!=pack_id:raise ValueError('Visual pack ID differs from content owner')
            namespaces={row['mod_id'] for row in bundle['mods']}
            if any(row.get('identifier','').split(':')[0] not in namespaces for row in declaration.get('entities',[])):
                raise ValueError('Content visuals cannot claim another mod namespace')
            with tempfile.TemporaryDirectory(prefix='neocore_visual_binding_') as tmp:
                staged=Path(tmp)/'visuals';visual_report=build_visuals(options['source'],staged,declaration)
                visual_data[pack_id]={'report':visual_report,'files':{p.relative_to(staged).as_posix():p.read_bytes() for p in staged.rglob('*') if p.is_file()}}
    core = core_bundle()
    core_path = output / 'NeoCore_behavior_pack'
    scripts = core_path / 'NeoCoreSourceScripts'
    scripts.mkdir(parents=True)
    (core_path / 'entities').mkdir(exist_ok=True)
    (scripts / '__init__.py').write_text('', encoding='utf-8')
    for filename in ('source_modules.py', 'runtime_host.py'):
        shutil.copyfile(SCRIPTS / 'core' / filename, scripts / filename)
    core_entry = (DEV / 'templates/source_core_modMain.py').read_text(encoding='utf-8')
    core_entry = core_entry.replace('PLATFORM_VERSIONS = {}','PLATFORM_VERSIONS = '+repr(dict(platform_versions or {})))
    (scripts/'modMain.py').write_text(core_entry,encoding='utf-8')
    snapshot(scripts / 'source_snapshot.py', core)
    resource_source = SCRIPTS.parent.parent / 'resource_pack_kFreO1qQ'
    dependencies = []
    if resource_source.is_dir():
        copy_runtime_files(resource_source, output / 'NeoCore_resource_pack',
            {'.json', '.png', '.jpg', '.jpeg', '.tga', '.ogg', '.lang'}, excluded_files)
        resource_manifest = json.loads((resource_source / 'manifest.json').read_text(encoding='utf-8-sig'))
        dependencies.append({key: resource_manifest['header'][key] for key in ('uuid', 'version')})
    if (SCRIPTS.parent / 'entities').is_dir():
        copy_runtime_files(SCRIPTS.parent / 'entities', core_path / 'entities', {'.json'}, excluded_files)
    core_manifest = manifest('neocore', 'NeoCoreSourceScripts', dependencies)
    write_json(core_path / 'manifest.json', core_manifest)
    reports = []
    template_name = 'source_resource_modMain.py' if layout == 'resources' else 'source_content_modMain.py'
    template = (DEV / 'templates'/template_name).read_text(encoding='utf-8')
    for pack_id, root, bundle in prepared:
        pack = output / ('behavior_pack-' + pack_id if layout == 'resources' else pack_id + '_behavior_pack')
        script_name = pack_id + 'Scripts'
        if root.name == script_name:
            raise ValueError('Original folder conflicts with generated Scripts folder')
        content_scripts = pack / script_name
        content_scripts.mkdir(parents=True)
        # NetEase PC explicitly warns that entities/ is needed for behavior discovery.
        # Keep this empty for script-only content; do not invent an entity.
        (pack / 'entities').mkdir(exist_ok=True)
        (content_scripts / '__init__.py').write_text('', encoding='utf-8')
        (content_scripts / 'modMain.py').write_text(template.replace('__CONTENT_SCRIPT__', script_name)
            .replace('__PACK_ID__', pack_id), encoding='utf-8')
        if layout == 'resources':
            resource_root = content_scripts/'resources'
            resource_root.mkdir()
            # Non-Python resources retain their original paths; no asset conversion is claimed.
            excluded_types={'.java','.class','.jar','.pyc','.pyo','.dll','.so','.exe'}
            for original in sorted(root.rglob('*')):
                if not original.is_file():continue
                if original.suffix.lower() in excluded_types or '__pycache__' in original.parts:
                    excluded_files.append({'source':str(original),'reason':'Development/native payload excluded from resources'})
                    continue
                target=resource_root/original.relative_to(root)
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(original,target)
            (resource_root/'__init__.py').write_text('',encoding='utf-8')
            source_index={}
            for name,record in bundle['sources'].items():
                physical=resource_root/record['origin']
                if hashlib.sha256(physical.read_bytes()).hexdigest()!=record['sha256']:
                    raise ValueError('Resources physical source differs from compiled input: '+name)
                source_index[name]={'path':script_name+'/resources/'+record['origin'],
                    'file_sha256':record['sha256'],
                    'text_sha256':hashlib.sha256(record['source'].encode('utf-8')).hexdigest()}
            resource={'schema_version':1,'kind':'neocore_resource_content','pack_id':pack_id,
                'script_package':script_name,'resource_root':script_name+'/resources',
                'format_preview_only':False,'bundle':bundle,'source_index':source_index}
            payload=json.dumps(resource,ensure_ascii=True,sort_keys=True)
            (resource_root/'_nc_resources.py').write_text('# -*- coding: utf-8 -*-\n'
                '# Generated resources index; rebuild after source edits.\nimport json\nRESOURCE = json.loads('+repr(payload)+')\n',encoding='utf-8')
        else:
            snapshot(content_scripts / 'source_snapshot.py', bundle)
            # Preserve translated package paths, not the original Java development payload.
            copy_runtime_files(root, pack / root.name, {'.py'}, excluded_files)
        write_json(pack / 'manifest.json', manifest(pack_id, script_name,
            [{key: core_manifest['header'][key] for key in ('uuid', 'version')}]))
        if pack_id in visual_data:
            visual=visual_data[pack_id];resource_name='resource_pack-'+pack_id
            for name,raw in visual['files'].items():
                if name.startswith('behavior_pack-'+pack_id+'/entities/'):
                    destination=pack/'entities'/name.rsplit('/',1)[1]
                elif name.startswith(resource_name+'/'):
                    destination=output/name
                else:continue
                if destination.exists():raise ValueError('Visual binding collides with an existing pack file')
                destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(raw)
            resource_manifest=json.loads((output/resource_name/'manifest.json').read_bytes())
            # The original translated entrypoint remains the only gameplay source.
            content_manifest=json.loads((pack/'manifest.json').read_bytes())
            content_manifest['dependencies'].append({key:resource_manifest['header'][key] for key in ('uuid','version')})
            write_json(pack/'manifest.json',content_manifest)
            visual['report']=dict(visual['report'],status='STATIC_VISUALS_ATTACHED',gameplay_loaded=None,
                limits=['Only declared static appearance is converted; original gameplay stays in translated source.',
                        'Animation/render code and engine appearance require separate validation.'])
            write_json(pack/'entity_visual_report.json',visual['report'])
        if pack_id in item_data:
            if pack_id in visual_data:
                raise ValueError('Combined item/entity resource packs require an explicit merged manifest')
            data = item_data[pack_id]
            resource_name = 'resource_pack-' + pack_id
            for name, raw in data['files'].items():
                lane, relative = name.split('/', 1)
                destination = (pack if lane == 'behavior' else output/resource_name) / relative
                if destination.exists():
                    raise ValueError('Item content output collision: ' + name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(raw)
            resource_manifest = manifest(pack_id + '_items', None)
            resource_manifest['modules'][0]['type'] = 'resources'
            write_json(output/resource_name/'manifest.json', resource_manifest)
            content_manifest = json.loads((pack/'manifest.json').read_bytes())
            if data['report'].get('recipe_unlocks'):
                content_manifest['header']['min_engine_version'] = [1,20,30]
            content_manifest['dependencies'].append({key:resource_manifest['header'][key] for key in ('uuid','version')})
            write_json(pack/'manifest.json', content_manifest)
            write_json(pack/'item_content_report.json', data['report'])
        reports.append({'pack_id': pack_id, 'pack_path':pack.name,'script_package':script_name,
            'resource_root':script_name+'/resources' if layout=='resources' else None,
            'modules': len(bundle['sources']),
            'mod_ids': [row['mod_id'] for row in bundle['mods']],
            'compatibility_issues': [issue for row in bundle['mods'] for issue in row.get('compatibility_issues', [])]})
        if pack_id in visual_data:
            reports[-1]['resource_pack_path']='resource_pack-'+pack_id
            reports[-1]['entity_visuals']=visual_data[pack_id]['report']
        if pack_id in item_data:
            reports[-1]['resource_pack_path'] = 'resource_pack-' + pack_id
            reports[-1]['item_content'] = item_data[pack_id]['report']
    report = {'protocol': 2, 'content_layout':layout,'resource_content_protocol':1 if layout=='resources' else None,
        'engine_verified': False, 'core_modules': len(core['sources']),
        'contents': reports, 'limits': [
            'compile/eval source loading and generated manifests require NetEase PC engine validation.',
            'No JVM bytecode execution. Static model geometry requires explicit source bindings; animations and recipes remain unconverted.',
            'Regenerate source snapshots after editing Python. Original input folders were not changed.',
            'Enable the independent core and content packs together. Content packs contain no core implementation.']}
    report['target'] = {'minecraft': '1.21.1', 'neoforge_reference': '21.1.233',
        'neoforge_branch': '21.1.x', 'fml_reference': '4.0.42', 'platform': 'netease_pc',
        'verified_compatibility': False}
    report['declared_reference_profile'] = dict(platform_versions or {})
    inventory = {'selection': 'API catalog and runtime dependency closure',
        'content_layout':layout,
        'review_status': 'Inventory is provenance, not semantic approval of every module.',
        'core': {name: {key: record[key] for key in ('origin', 'sha256')}
            for name, record in sorted(core['sources'].items())},
        'contents': {pack_id: {name: {key: record[key] for key in ('origin', 'sha256')}
            for name, record in sorted(bundle['sources'].items())}
            for pack_id, root, bundle in prepared},
        'native_core': {filename: hashlib.sha256((scripts / filename).read_bytes()).hexdigest()
            for filename in ('__init__.py', 'source_modules.py', 'runtime_host.py', 'modMain.py')},
        'excluded_core_sources': sorted(path.relative_to(SCRIPTS).as_posix()
            for path in SCRIPTS.rglob('*.py')
            if path.relative_to(SCRIPTS).as_posix() not in
            set(record['origin'] for record in core['sources'].values()))}
    write_json(output / 'source_inventory.json', inventory)
    report['source_inventory'] = 'source_inventory.json'
    report['excluded_development_files'] = excluded_files
    report['file_policy'] = {'behavior': 'generated Python, declarations and preserved original resource data' if layout=='resources' else 'generated Python and selected game JSON only',
        'content_mirror': 'Original package/resource paths preserved under Scripts/resources; assets/data are not converted engine resources' if layout=='resources' else 'Python only; original JSON/assets require resource conversion',
        'limits': 'Selected project delivery types, not the complete official NetEase allowlist.'}
    write_json(output / 'distribution_report.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    parser.add_argument('--config', help='JSON array of pack_id/folder/entrypoints records; omit for the two examples')
    args = parser.parse_args()
    if args.config:
        contents = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    else:
        contents = [{'pack_id': name, 'folder': str(DEV / 'examples/multi_mod' / name),
            'entrypoints': {name: 'example.' + name + '.Main:start'}}
            for name in ('neocore_example_base', 'neocore_example_addon')]
    print(json.dumps(build(args.output, contents), ensure_ascii=False, indent=2))
