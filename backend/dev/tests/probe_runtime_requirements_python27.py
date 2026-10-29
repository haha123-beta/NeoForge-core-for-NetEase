from __future__ import print_function
import copy
import io
import json
import sys

with io.open(sys.argv[1], 'r', encoding='utf-8') as stream:
    data = json.load(stream)
namespace = {'__name__': 'probe_source_loader'}
eval(compile(data['loader_source'].encode('utf-8'), 'source_modules.py', 'exec'), namespace)

for side in ('SERVER', 'CLIENT'):
    runtime = namespace['SourceModuleLoader'](data['core']['sources'])
    Session = runtime.load('core.bundled_mods').BundledModSession
    good = copy.deepcopy(data['contents'][0])
    bad_source = 'raise RuntimeError("incompatible source executed")\n'
    checks = runtime.load('core.runtime_requirements')
    bad = {'schema_version': 1, 'kind': 'neocore_content_sources',
           'sources': {'incompatible.Main': {'source': bad_source, 'is_package': False}},
           'mods': [{'mod_id': 'incompatible', 'entrypoint': 'incompatible.Main:start'}],
           'runtime_requirements': {'schema_version': 1,
               'evidence_scope': checks.EVIDENCE_SCOPE,
               'modules': {'incompatible.Main': {
                   'code_sha256': checks.code_digest(bad_source),
                   'required_api_types': [],
                   'required_runtime_helpers': ['neocore.runtime.Profilers@99']}}}}
    importer = {'schema_version': 1, 'kind': 'neocore_content_sources',
                'sources': {'consumer.Main': {'source':
                    'from incompatible import Main\ndef start(context):\n    return Main\n',
                    'is_package': False}},
                'mods': [{'mod_id': 'consumer', 'entrypoint': 'consumer.Main:start'}]}
    session = Session(data['core']['sources'], [bad, importer, good, data['selector']],
                      side=side, runtime=runtime)
    try:
        results = session.loader.activate()
        assert results['incompatible']['phase'] == 'runtime_requirements', repr(results)
        assert results['consumer']['state'] == 'failed'
        assert 'blocked before import' in results['consumer']['message']
        assert 'incompatible.Main' not in runtime.modules
        assert results['runtime_goal_example']['ready']
        selector = results['runtime_selector_example']
        assert selector['phase'] == 'dependencies'
        assert selector['runtime_requirements']['status'] == 'requirements_satisfied'
        assert 'neoforge' in selector['message']
        session.close()
        assert runtime._blocked_sources == {}
        assert session.loader.results['runtime_goal_example']['state'] == 'unloaded'
    finally:
        session.close()
        runtime.close()
    print(json.dumps({'side': side, 'python': sys.version,
        'future_helper_blocked': True, 'indirect_import_blocked': True,
        'healthy_java_mod_ready': True, 'source_guards_cleaned': True,
        'selector': 'requirements_satisfied_but_platform_dependency_blocked',
        'engine_verified': False}))
