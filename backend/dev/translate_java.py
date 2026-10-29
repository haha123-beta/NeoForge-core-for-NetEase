"""Non-destructive Java directory conversion using the current explicit backend subset."""
import argparse
import json
from pathlib import Path
import shutil
import traceback
import os,sys
from translation_observer import call as observed,event as observe_event
from java_project_types import add_unit
from java_frontend import isolated_parse, api_index
from java_codegen import generate, NeedsLowering
from java_mixin_plan import plan as mixin_plan, MixinPlanError, MANIFEST, digest
from java_mixin_weave import weave


def _translate(root, output=None, dry_run=False, partial_transformers=False, dependency_abis=(), optional_dependency_packages=(), defer_external_symbols=True, parser_cache=None,parser_backend=None):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError('Input directory is missing')
    output = Path(output).resolve() if output is not None else None
    if output is not None and (output.exists() or root == output or root in output.parents or output in root.parents):
        raise ValueError('Output exists or overlaps input')
    if not dry_run and output is None:
        raise ValueError('Output required unless --dry-run')
    known, stale = observed('api_index_validation',api_index)
    if stale:
        raise ValueError('Java API index missing/stale; run dev/export_java_import_index.py')
    def parse_unit(source,origin,known_types):
        backend=parser_backend or isolated_parse
        if parser_cache is None:return backend(source,origin,known_types)
        return parser_cache.parse(source,origin,known_types,backend,
            notify=lambda **values:observe_event('parser_cache',**values))
    from dependency_abi import Index as DependencyIndex
    dependency_index=observed('dependency_abi_resolution',DependencyIndex,dependency_abis,known,optional_packages=optional_dependency_packages)
    for path in root.rglob('*'):
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise ValueError('Input contains a link; resolve its intended content before conversion')
    if not dry_run:
        output.mkdir(parents=True)
        shutil.copytree(root, output / root.name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    report = {'files': 0, 'generated_for_review': 0, 'manual_review': 0, 'failed': 0,
        'engine_verified': False, 'python2_executed': False, 'ready_mods': 0, 'results': []}
    bugs = []
    paths = sorted(root.rglob('*.java'))
    project_types = {}
    # Two bounded passes avoid retaining all full CSTs for large mod directories.
    for number,path in enumerate(paths):
        try:
            observation={'file':path.relative_to(root).as_posix(),'processed':number,'total':len(paths)}
            ir = observed('declaration_parse',parse_unit,path.read_bytes(),path.relative_to(root).as_posix(),known,observation=observation)
            observed('type_declarations',add_unit,project_types,ir,observation=observation)
        except Exception:
            # The conversion pass records the actual failure for this file.
            continue
    adaptation = None; woven = {}; woven_ir = {}; adaptation_error = None
    requirements = None
    if partial_transformers:
        from java_optional_transformers import partition
        requirements, skipped, unsupported = partition(root)
        report['skipped_optional'] = skipped
        report['capability_blockers'] = unsupported
        report['degraded_conversion'] = bool(skipped or unsupported)
    original_project_types = {name:list(rows) for name,rows in project_types.items()}
    try:
        adaptation = mixin_plan(root, project_types, requirements)
        if adaptation:
            if (root / MANIFEST).exists():
                raise MixinPlanError(MANIFEST, 'Reserved generated weaving manifest already exists')
            affected={row['target_file'] for row in adaptation['injections']}
            affected.update(row.get('mixin_file') for row in adaptation.get('native_bindings',[]))
            for records in project_types.values():
                for record in records:
                    metadata=record.get('inheritance_metadata',{})
                    if record['file'] in affected and (metadata.get('record_components') is not None or metadata.get('anonymous_codec')):
                        raise MixinPlanError(record['file'],'Record/anonymous codec source spans require composed Mixin lowering')
            woven = weave(root, adaptation)
            for file, source in woven.items():
                transformed = isolated_parse(source, file, known)
                transformed['native_mixin_handlers']=[entry['handler'] for binding in adaptation.get('native_bindings',[]) if binding['mixin_file']==file for entry in binding['entries']]
                woven_ir[file] = transformed
                for identity in list(project_types):
                    project_types[identity] = [row for row in project_types[identity] if row['file'] != file]
                    if not project_types[identity]: del project_types[identity]
                add_unit(project_types, transformed)
            report['mixin_plan'] = adaptation
    except (MixinPlanError, ValueError) as error:
        adaptation_error = str(error)
        if partial_transformers:
            report['capability_blockers'].append({'kind':'mixin','category':'required_mixin',
                'status':'UNSUPPORTED','source':getattr(error,'source','source'),'message':str(error)})
            report['degraded_conversion'] = True
            adaptation = None; woven = {}; woven_ir = {}
            project_types = original_project_types
    for number,path in enumerate(paths):
        relative = path.relative_to(root)
        ir = {}
        report['files'] += 1
        try:
            if adaptation_error and not partial_transformers:
                raise NeedsLowering({'line':1}, adaptation_error, {'category':'mixin_plan'})
            if path.with_suffix('.py').exists():
                raise NeedsLowering({'line': 1}, 'Existing Python counterpart must not be overwritten')
            source_bytes = path.read_bytes()
            if adaptation and digest(source_bytes) != adaptation['source_sha256'].get(relative.as_posix()):
                raise NeedsLowering({'line':1}, 'Source changed after injection planning')
            observation={'file':relative.as_posix(),'processed':number,'total':len(paths)}
            ir = woven_ir.get(relative.as_posix()) or observed('generation_parse',parse_unit,source_bytes,relative.as_posix(),known,observation=observation)
            if ir['parse_status'] != 'PARSED':
                errors = ir['syntax_errors']
                raise NeedsLowering(errors[0] if errors else {'line': 1},
                    'Parser reported syntax errors; inspect syntax_errors in this report',
                    {'category': 'syntax', 'syntax_errors': errors})
            native_files={b['mixin_file'] for b in adaptation.get('native_bindings',[])} if adaptation else set()
            if adaptation and relative.as_posix() in adaptation['mixin_files'] and relative.as_posix() not in native_files:
                result = {'python_source':'# -*- coding: utf-8 -*-\n# Handler bodies consumed by validated source targets; no standalone Mixin class.\n',
                    'status':'GENERATED_REVIEW_REQUIRED','limits':['Mixin handlers mechanically merged into source-owned targets.'],
                    'project_dependencies':[], 'annotation_metadata':[], 'required_api_types':[], 'required_runtime_helpers':[]}
            else:
                combined={name:list(rows) for name,rows in project_types.items()}
                for identity,records in dependency_index.project_records().items():
                    if identity in combined:raise NeedsLowering({'line':1},'Dependency/local symbol ownership conflict: '+identity,{'category':'TRANSLATED_DEPENDENCY_SYMBOL'})
                    combined[identity]=records
                result = observed('codegen_including_linking',generate,ir,combined,dependency_index=dependency_index,defer_external_symbols=defer_external_symbols,observation=observation)
            if relative.as_posix() in native_files:
                hook_abi=max(entry.get('hook_abi',1) for binding in adaptation['native_bindings'] if binding['mixin_file']==relative.as_posix() for entry in binding['entries'])
                result['required_api_types'].append('neocore.runtime.MixinHooks')
                result['required_runtime_helpers'].append('neocore.runtime.MixinHooks@'+str(hook_abi))
                result['python_source']+="\nfrom neocore.runtime import MixinHooks as _nc_NativeMixinHooks\nif getattr(_nc_NativeMixinHooks, 'ABI_VERSION', 0) < "+str(hook_abi)+":\n    raise RuntimeError('Native MixinHooks ABI"+str(hook_abi)+" required')\n"
            result['source_sha256'] = digest(source_bytes)
            if not dry_run:
                destination = output / root.name / relative.with_suffix('.py')
                destination.write_text(result['python_source'], encoding='utf-8')
            report['generated_for_review'] += 1
            row = {'file': relative.as_posix(), 'status': result['status'],
                'source_sha256': result['source_sha256'], 'limits': result['limits'],
                'project_dependencies': result['project_dependencies'],
                'annotation_metadata': result['annotation_metadata'],
                'mod_entrypoints': result.get('mod_entrypoints',[]),
                'event_subscribers': result.get('event_subscribers',[]),
                'required_api_types': result['required_api_types'],
                'required_runtime_helpers': result['required_runtime_helpers']}
            row['external_symbols']=result.get('external_symbols',[])
            row['translated_dependencies']=result.get('translated_dependencies',[])
        except NeedsLowering as error:
            report['manual_review'] += 1
            row = {'file': relative.as_posix(), 'status': 'MANUAL_REVIEW',
                'line': error.line, 'reason': error.reason, 'details': error.details}
            row['additional_requirements'] = [
                {'symbol': item['name'], 'evidence': 'STATIC_IMPORT_ONLY',
                 'implementation_status': 'NOT_PROVEN_BY_IMPORT'}
                for item in ir.get('imports', []) if isinstance(item, dict) and item.get('name')]
        except Exception as error:
            report['failed'] += 1
            row = {'file': relative.as_posix(), 'status': 'FAILED', 'reason': str(error)}
            bugs.append(relative.as_posix() + '\n' + traceback.format_exc())
        from tools.neocore_gui_092.diagnostic_contract import file_diagnostic
        row['diagnostic'] = file_diagnostic(row)
        report['results'].append(row)
        observe_event('file_result','RECORDED',file=relative.as_posix(),processed=number+1,total=len(paths),status=row['status'])
        if __import__('os').environ.get('NEOCORE_OBSERVABILITY_DIR'):
            checkpoint=Path(__import__('os').environ['NEOCORE_OBSERVABILITY_DIR'])/'partial_translation.json'
            temporary_checkpoint=checkpoint.with_suffix('.tmp')
            temporary_checkpoint.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');temporary_checkpoint.replace(checkpoint)
    observe_event('dependency_closure','STARTED')
    generated = {row['file'] for row in report['results'] if row['status'] == 'GENERATED_REVIEW_REQUIRED'}
    for row in report['results']:
        if row['status'] == 'GENERATED_REVIEW_REQUIRED':
            row['missing_generated_dependencies'] = [name for name in row['project_dependencies'] if name not in generated]
    report['ambiguous_project_types'] = sorted(name for name, rows in project_types.items() if len(rows) > 1)
    observe_event('dependency_closure','FINISHED')
    if not dry_run:
        if adaptation and not report['failed'] and not report['manual_review'] and not any(row.get('missing_generated_dependencies') for row in report['results']):
            from build_source_bundle import collect_sources
            sources = collect_sources(output / root.name)
            proof = {'schema_version':1,'scope':adaptation['scope'],'plan':adaptation,
                'generated_modules':{name:digest(row['source'].encode('utf-8')) for name,row in sources.items()}}
            (output / root.name / MANIFEST).write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
        (output / 'translation_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        manual = [row for row in report['results'] if row['status'] == 'MANUAL_REVIEW']
        (output / 'manual_review.txt').write_text('\n'.join(row['file'] + ':' + str(row['line']) + ' ' + row['reason'] for row in manual), encoding='utf-8')
        (output / 'failures.log').write_text('\n'.join(bugs), encoding='utf-8')
        (output / 'README.txt').write_text('Generated Python files require review. No runnable behavior pack or engine verification is claimed.\n', encoding='utf-8')
    return report


def translate(root, output=None, dry_run=False, partial_transformers=False, dependency_abis=(), optional_dependency_packages=(), defer_external_symbols=True,parse_cache_enabled=True):
    if type(parse_cache_enabled) is not bool:raise ValueError('parse_cache_enabled must be boolean')
    if not parse_cache_enabled:
        return _translate(root,output,dry_run,partial_transformers,dependency_abis,optional_dependency_packages,defer_external_symbols)
    from java_parse_cache import ParseCache
    from validation_report import source_fingerprint
    from workspace_paths import PACK_ROOT
    before=source_fingerprint(PACK_ROOT)
    context={'source_snapshot':before,'python':sys.version,'input_root':str(Path(root).resolve()),
        'job_context':os.environ.get('NEOCORE_PARSE_JOB_CONTEXT'),'dependency_abis':dependency_abis,
        'optional_dependency_packages':optional_dependency_packages,'partial_transformers':partial_transformers,
        'defer_external_symbols':defer_external_symbols}
    from java_parser_worker import ParserWorker
    with ParseCache(context) as cache,ParserWorker(cache.context_sha) as worker:
        report=_translate(root,output,dry_run,partial_transformers,dependency_abis,optional_dependency_packages,defer_external_symbols,cache,worker.parse)
    if before!=source_fingerprint(PACK_ROOT):raise ValueError('Compiler/runtime/parser snapshot changed during cached translation')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root')
    parser.add_argument('--output')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--no-parse-cache',action='store_true',help='Reparse every phase for independent cache equivalence checks')
    parser.add_argument('--partial-transformers', action='store_true', help='Explicitly skip optional Mixin configs and retain partial sources; no runnable compatibility claim')
    args = parser.parse_args()
    report = translate(args.root, args.output, args.dry_run, args.partial_transformers,parse_cache_enabled=not args.no_parse_cache)
    print(json.dumps({k:v for k,v in report.items() if k != 'results'}, ensure_ascii=False, indent=2))
    raise SystemExit(1 if report['failed'] or report['manual_review'] else 0)
