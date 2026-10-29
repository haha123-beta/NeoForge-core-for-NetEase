from __future__ import print_function
import io
import json
import sys
with io.open(sys.argv[1],'r',encoding='utf-8') as stream:data=json.load(stream)
scope={'__name__':'wildcards_source_loader'}
eval(compile(data['loader_source'].encode('utf-8'),'source_modules.py','exec'),scope)
loader=scope['SourceModuleLoader']
rows=[]
for side in ('SERVER','CLIENT'):
    runtime=loader(data['core']['sources'])
    session=runtime.load('core.bundled_mods').BundledModSession(data['core']['sources'],[data['content']],side=side,runtime=runtime)
    try:
        assert session.loader.activate()['runtime_static_wildcards_example']['ready']
        driver=runtime.load('core.content_events').ContentTickDriver(session.loader,side)
        for unused in range(150):driver.on_tick()
        state=session.loader.contexts['runtime_static_wildcards_example'].instance
        assert state.total==(107 if side=='SERVER' else 7) and state.selected==3
        for case in data['cases']:
            sources=dict(data['core']['sources']);sources.update(case['sources'])
            case_runtime=loader(sources)
            api=case_runtime.load('core.java_api');imports=api.JavaApiImports(case_runtime).install(api.collect_java_api())
            try:actual=str(case_runtime.load('demo.Use').Use().run())
            finally:imports.close();case_runtime.close()
            assert actual==case['jdk_result'],repr((actual,case['jdk_result']))
        session.close()
        assert session.loader.results['runtime_static_wildcards_example']['state']=='unloaded'
        assert session.loader.contexts['runtime_static_wildcards_example'].game_bus.listenerCount()==0
        rows.append({'side':side,'total':state.total,'selected':state.selected,'jdk_cases':len(data['cases']),'closed':True,'business_ticks':100})
    finally:session.close();runtime.close()
print(json.dumps({'python':sys.version,'content_runs':rows,'engine_verified':False}))
