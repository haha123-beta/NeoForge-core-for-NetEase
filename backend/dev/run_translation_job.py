"""Run non-destructive conversion and optional independent pack assembly from JSON."""
import argparse
from datetime import datetime
import json
import hashlib
from pathlib import Path
import traceback
import uuid

from translate_java import translate
from build_distribution import build
from build_source_bundle import collect_sources
from translation_observer import call as observed


def run_job(config_path):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
    if not isinstance(config, dict) or set(config) - {'input', 'output_root', 'distribution', 'partial_transformers','dependency_abis','optional_dependency_packages','defer_external_symbols','export_dependency_abi'}:
        raise ValueError('Expected input/output_root and optional distribution in JSON object')
    def configured_path(name):
        value = config.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError('Missing path: ' + name)
        return (config_path.parent / value).resolve()
    source, output_root = configured_path('input'), configured_path('output_root')
    abi_paths=config.get('dependency_abis',[])
    if not isinstance(abi_paths,list) or any(not isinstance(p,str) or not p for p in abi_paths):raise ValueError('dependency_abis must list manifest paths')
    dependency_abis=[json.loads((config_path.parent/p).resolve().read_text(encoding='utf-8-sig')) for p in abi_paths]
    optional_packages=config.get('optional_dependency_packages',[])
    if not isinstance(optional_packages,list) or any(not isinstance(p,str) or not p for p in optional_packages):raise ValueError('optional_dependency_packages must list package names')
    if type(config.get('defer_external_symbols',True)) is not bool:raise ValueError('defer_external_symbols must be boolean')
    if not source.is_dir():
        raise ValueError('Input directory is missing')
    if source == output_root or source in output_root.parents or output_root in source.parents:
        raise ValueError('Output root overlaps input')
    distribution = config.get('distribution')
    if distribution is not None:
        if not isinstance(distribution, dict) or set(distribution) - {'pack_id', 'entrypoints', 'side', 'layout', 'visuals', 'items', 'platform_versions', 'python2'}:
            raise ValueError('Invalid distribution configuration')
        versions = distribution.get('platform_versions', {})
        if not isinstance(versions,dict) or any(k not in ('minecraft','neoforge') or not isinstance(v,str) or not v for k,v in versions.items()):
            raise ValueError('Expected explicit Minecraft/NeoForge reference profile versions')
        if distribution.get('visuals') is not None:
            visual=distribution['visuals']
            if not isinstance(visual,dict) or set(visual)!={'source','declaration'} or not isinstance(visual['source'],str):raise ValueError('Invalid visual binding source/declaration')
            distribution=dict(distribution,visuals=dict(visual,source=str((config_path.parent/visual['source']).resolve())))
        entries = distribution.get('entrypoints')
        if entries is not None and (not isinstance(entries, dict) or not entries or any(
                not isinstance(k, str) or not isinstance(v, str) or not k or ':' not in v
                for k, v in entries.items())):
            raise ValueError('Explicit mod_id=module:attribute entrypoints are required')
        if distribution.get('side', 'BOTH') not in ('BOTH', 'CLIENT', 'SERVER'):
            raise ValueError('Invalid content side')
        if not isinstance(distribution.get('pack_id'), str):
            raise ValueError('Missing content pack_id')
        if distribution.get('layout','legacy') not in ('legacy','resources'):
            raise ValueError('Unknown distribution layout')
    job = output_root / ('neocore_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8])
    job.mkdir(parents=True, exist_ok=False)
    report = {'status': 'STARTED', 'output': str(job), 'input': str(source),
              'engine_verified': False, 'python2_executed': False, 'ready_mods': 0}
    try:
        from mod_content_pipeline import stage as stage_content
        content_report=observed('content_scan',stage_content,source,job/'content')
        report['content']={'manifest':str(job/'content/content_manifest.json'),'lanes':content_report['lanes'],'data_types':content_report['data_types'],'preserved_files':content_report['preserved_files'],'invalid_json_files':content_report['invalid_json_files'],'semantic_conversion':False,'engine_verified':False}
        if type(config.get('partial_transformers',False)) is not bool:
            raise ValueError('partial_transformers must be boolean')
        conversion = translate(source, job / 'converted', partial_transformers=config.get('partial_transformers',False),
            dependency_abis=dependency_abis,optional_dependency_packages=optional_packages,defer_external_symbols=config.get('defer_external_symbols',True))
        report['translation'] = {k: v for k, v in conversion.items() if k != 'results'}
        export_config=config.get('export_dependency_abi')
        if export_config is not None:
            if not isinstance(export_config,dict) or set(export_config)!={'source_jar','version','dependency_id','neocore_abi'}:raise ValueError('Invalid dependency ABI export configuration')
            from dependency_abi import export as export_abi
            abi=observed('dependency_abi_export',export_abi,source,conversion,(config_path.parent/export_config['source_jar']).resolve(),export_config['version'],export_config['dependency_id'],export_config['neocore_abi'],job/'converted'/source.name)
            abi_path=job/'dependency_abi.json';abi_path.write_text(json.dumps(abi,ensure_ascii=False,indent=2),encoding='utf-8')
            report['dependency_abi']={'manifest':str(abi_path),'dependency_id':abi['dependency_id'],'version':abi['version'],'engine_verified':False}
        deferred=any(symbol.get('deferred') for row in conversion['results'] for symbol in row.get('external_symbols',[]))
        translated_dependencies=sorted({dep for row in conversion['results'] for dep in row.get('translated_dependencies',[])})
        report['translated_dependencies']=translated_dependencies
        missing = any(row.get('missing_generated_dependencies') for row in conversion['results'])
        if not conversion['files'] and content_report['has_non_java_content'] and not conversion['failed'] and not conversion.get('capability_blockers'):
            report['status']='CONTENT_STAGED_REVIEW_REQUIRED'
            report['packaging']='Original non-Java content staged with hashes and per-type limitations; no NetEase schema conversion or engine acceptance claimed.'
        elif conversion['failed'] or conversion['manual_review'] or missing or not conversion['files'] or conversion.get('capability_blockers'):
            report['status'] = 'TRANSLATION_INCOMPLETE'
            report['packaging'] = 'SKIPPED: conversion is incomplete or contains no Java sources'
        elif distribution is None or conversion.get('skipped_optional') or deferred or translated_dependencies:
            report['status'] = 'GENERATED_REVIEW_REQUIRED'
            report['packaging'] = ('BLOCKED: external symbols remain deferred; provide translated dependency ABI and retranslate' if deferred else
                'BLOCKED: independent translated dependency pack linking requires validation' if translated_dependencies else
                'BLOCKED: optional transformations were explicitly skipped; degraded source review only' if conversion.get('skipped_optional') else 'NOT_REQUESTED: add explicit distribution entrypoints to assemble packs')
        else:
            folder=job/'converted'/source.name
            content=dict(distribution,folder=str(folder))
            groups={};subscribers=[]
            for row in conversion['results']:
                module='.'.join(Path(row['file']).with_suffix('').parts)
                subscribers.extend(dict(entry,module=module) for entry in row.get('event_subscribers',[]))
                for entry in row.get('mod_entrypoints',[]):groups.setdefault(entry['mod_id'],[]).append((module,entry['attribute'],entry['physical_sides']))
            explicit=content.get('entrypoints')
            if explicit:
                groups={mod_id:[tuple(value.split(':',1))+(('CLIENT','DEDICATED_SERVER'),)] for mod_id,value in explicit.items()}
            generated_wrapper=None
            if not explicit or subscribers:
                if not groups:raise ValueError("No @Mod entrypoints found; configure explicit entrypoints")
                identity=json.dumps({'groups':groups,'subscribers':subscribers},sort_keys=True,separators=(',',':'))
                wrapper_name='_nc_generated_mod_entries_'+hashlib.sha256(identity.encode('utf-8')).hexdigest()[:32]
                wrapper=folder/(wrapper_name+'.py')
                if wrapper.exists():raise ValueError("Generated mod entry module conflicts with source layout")
                if len(groups)>1 and any(entry['mod_id'] is None for entry in subscribers):raise ValueError('Implicit subscriber modid in multi-mod content requires explicit ownership review')
                lines=['# -*- coding: utf-8 -*-','from __future__ import absolute_import','from neocore.runtime import ModEntrypoints as _nc_entries']
                if subscribers:lines.extend(["if getattr(_nc_entries,'ABI_VERSION',0)<2:","    raise RuntimeError('NeoCore ModEntrypoints ABI2 required for automatic subscribers')"])
                entries={}
                for index,(mod_id,targets) in enumerate(sorted(groups.items())):
                    entry_name='_nc_start_'+str(index);entries[mod_id]=wrapper_name+':'+entry_name
                    lines.extend(['def '+entry_name+'(context):','    instances=[]'])
                    for module,attribute,sides in targets:
                        # Imports happen in the original source loader, preserving package ownership.
                        lines.extend(['    if context.physical_side in '+repr(tuple(sides))+':','        module=__import__('+repr(module)+',globals(),locals(),['+repr(attribute)+'],0)',
                            '        value=getattr(module,'+repr(attribute)+')(context)',
                            '        if value is not None:instances.append(value)'])
                    for subscriber in subscribers:
                        if subscriber['mod_id'] not in (None,mod_id):continue
                        module=subscriber['module'];name=subscriber['class_name']
                        lines.extend(['    if context.physical_side in '+repr(tuple(subscriber['physical_sides']))+':',
                            '        module=__import__('+repr(module)+',globals(),locals(),['+repr(name)+'],0)',
                            '        _nc_entries.automatic(context,getattr(module,'+repr(name)+'))'])
                    lines.append('    return instances[0] if len(instances)==1 else tuple(instances)')
                wrapper.write_text('\n'.join(lines)+'\n',encoding='utf-8')
                content['entrypoints']=entries
                report['discovered_entrypoints']=entries
                generated_wrapper=wrapper_name
            requirement_file=folder/'_nc_runtime_requirements.json'
            if requirement_file.exists():raise ValueError('Generated runtime requirements conflict with an original file')
            sources=collect_sources(folder);requirements={}
            from java_mixin_plan import MANIFEST as weave_manifest, digest as weave_digest
            weave_path=folder/weave_manifest
            if weave_path.exists():
                proof=json.loads(weave_path.read_text(encoding='utf-8'))
                before=proof['generated_modules']
                after={name:weave_digest(row['source'].encode('utf-8')) for name,row in sources.items()}
                if any(after.get(name)!=digest for name,digest in before.items()) or set(after)-set(before)-{generated_wrapper}:
                    raise ValueError('Source weaving output changed while generating the entry wrapper')
                proof['generated_modules']=after
                weave_path.write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
            for row in conversion['results']:
                module='.'.join(Path(row['file']).with_suffix('').parts)
                requirements[module]={'origin':row['file'],'java_source_sha256':row['source_sha256'],
                    'code_sha256':hashlib.sha256(sources[module]['source'].encode('utf-8')).hexdigest(),
                    'required_api_types':sorted(set(row['required_api_types'])|{'java.lang.String'}),
                    'required_runtime_helpers':row['required_runtime_helpers']}
            if generated_wrapper is not None:
                requirements[generated_wrapper]={'origin':'mechanical_mod_entry_wrapper',
                    'code_sha256':hashlib.sha256(sources[generated_wrapper]['source'].encode('utf-8')).hexdigest(),
                    'required_api_types':['neocore.runtime.ModEntrypoints'],
                    'required_runtime_helpers':['neocore.runtime.ModEntrypoints@2'] if subscribers else []}
            manifest={'schema_version':1,'evidence_scope':'api_type_presence_and_helper_abi','modules':requirements}
            requirement_file.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
            report['runtime_requirements']={'schema_version':1,'manifest':str(requirement_file),
                'generated_modules':sorted(requirements),'untracked_modules':sorted(set(sources)-set(requirements)),
                'evidence_scope':manifest['evidence_scope'],
                'limits':['Not a platform version declaration or full Java method-semantic proof.']}
            if content.get('items') == 'auto':
                used = {api for row in conversion['results'] for api in row.get('required_api_types',[])}
                if ('net.neoforged.neoforge.registries.DeferredItem' in used or
                    {'net.neoforged.neoforge.registries.DeferredRegister','net.minecraft.world.item.Item'} <= used):
                    from collect_item_content import collect as collect_items
                    declaration = collect_items(folder, content['entrypoints'], job/'item_registration',
                                                'CLIENT' if content.get('side') == 'CLIENT' else 'SERVER',
                                                content.get('platform_versions'), content.get('python2'))
                    content['items'] = declaration if declaration['items'] else None
                    report['item_registration'] = {'status':'LOCAL_REGISTRATION_EXECUTED',
                        'receipt':str(job/'item_registration/receipt.json'), 'python2_executed':True,
                        'engine_verified':False}
                    report['python2_executed'] = True
                    report['execution_scope'] = 'original_generated_entry_and_registration_not_engine'
                else:
                    content['items'] = None
            report['distribution'] = observed('distribution_build',build,job / 'distribution', [content],
                layout=distribution.get('layout','legacy'),platform_versions=distribution.get('platform_versions'))
            report['status'] = 'PACKAGED_REVIEW_REQUIRED'
            report['limits'] = [
                'Generated sources require semantic review; packaging does not prove mod compatibility.',
                ('Original handlers are mechanically woven into explicitly validated source targets.' if conversion.get('mixin_plan') else
                 'Entry points use reviewed @Mod metadata or explicit configuration; no gameplay body is rewritten.'),
                'Java assets are preserved; unsupported models/recipes/GUI are not converted.',
                'Enable independent core and content packs together; NetEase PC validation is pending.']
    except Exception as error:
        report.update(status='FAILED', error=str(error))
        (job / 'failures.log').write_text(traceback.format_exc(), encoding='utf-8')
    (job / 'job_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', help='UTF-8 JSON; relative paths resolve against this file')
    args = parser.parse_args()
    try:
        report = run_job(args.config)
    except Exception:
        traceback.print_exc()
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report['status'] == 'FAILED' else (1 if report['status'] == 'TRANSLATION_INCOMPLETE' else 0)


if __name__ == '__main__':
    raise SystemExit(main())
