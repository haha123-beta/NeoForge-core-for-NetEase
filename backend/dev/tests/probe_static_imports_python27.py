from __future__ import print_function
import io
import json
import sys
with io.open(sys.argv[1], 'r', encoding='utf-8') as stream: data=json.load(stream)
scope={'__name__':'static_imports_source_loader'}
eval(compile(data['loader_source'].encode('utf-8'),'source_modules.py','exec'),scope)
loader=scope['SourceModuleLoader']
contract={}
eval(compile(data['cleanup_probe'].encode('utf-8'),'session-cleanup-contract.py','exec'),contract)
old=loader(data['old_core']['sources']);before=contract['trace'](old.load);old.close()
assert before['type']=='UnicodeEncodeError' and before['calls']==['loader','api_scope'],repr(before)
runtime=loader(data['core']['sources']);after=contract['run'](runtime.load);runtime.close()
results=[]
for core_name in ('core','old_core'):
    sources=data[core_name]['sources']
    for side in ('SERVER','CLIENT'):
        runtime=loader(sources)
        session=runtime.load('core.bundled_mods').BundledModSession(sources,[data['content']],side=side,runtime=runtime)
        try:
            assert session.loader.activate()['runtime_static_imports_example']['ready']
            driver=runtime.load('core.content_events').ContentTickDriver(session.loader,side)
            for unused in range(150): driver.on_tick()
            state=session.loader.contexts['runtime_static_imports_example'].instance
            assert state.total==(107 if side=='SERVER' else 7),repr(state.total)
            assert state.label=='static imports'
            for case in data['cases']:
                merged=dict(sources);merged.update(case['sources'])
                case_runtime=loader(merged)
                api=case_runtime.load('core.java_api')
                imports=api.JavaApiImports(case_runtime).install(api.collect_java_api())
                try: actual=str(case_runtime.load('demo.Use').Use().run())
                finally: imports.close();case_runtime.close()
                assert actual==case['jdk_result'],repr((actual,case['jdk_result']))
            session.close()
            assert session.loader.results['runtime_static_imports_example']['state']=='unloaded'
            assert session.loader.contexts['runtime_static_imports_example'].game_bus.listenerCount()==0
            results.append({'runtime':core_name,'side':side,'total':state.total,'closed':True,'jdk_cases':len(data['cases'])})
        finally:session.close();runtime.close()
print(json.dumps({'python':sys.version,'before_r50_cleanup':before,'after_r51_cleanup':after,
    'content_runs':results,'engine_verified':False}))
