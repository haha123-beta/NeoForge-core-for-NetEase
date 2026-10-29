from __future__ import print_function
import io,json,sys
with io.open(sys.argv[1],'r',encoding='utf-8') as stream:data=json.load(stream)
ns={'__name__':'probe_source_loader'}
eval(compile(data['loader_source'].encode('utf-8'),'source_modules.py','exec'),ns)
for side in ('SERVER','CLIENT'):
    runtime=ns['SourceModuleLoader'](data['core']['sources'])
    session=runtime.load('core.bundled_mods').BundledModSession(data['core']['sources'],data['contents'],side=side,runtime=runtime)
    try:
        results=session.loader.activate()
        assert len(results)==2 and all(row.get('ready') for row in results.values()),repr(results)
        driver=runtime.load('core.content_events').ContentTickDriver(session.loader,side)
        for unused in range(150):driver.on_tick()
        assert driver.ticks==100
        expected=2 if side=='SERVER' else 0
        for binding in data['bindings']:
            context=session.loader.contexts[binding['mod_id']]
            goal=context.instance.goal
            assert goal.ticks==expected
            if binding['flags']:
                assert [str(value.name()) for value in goal.getFlags()]==binding['flags']
        session.close()
        assert all(row['state']=='unloaded' for row in session.loader.results.values())
        assert all(ctx.game_bus.listenerCount()==0 for ctx in session.loader.contexts.values())
        print(json.dumps({'side':side,'driver_ticks':100,'business_ticks':expected,'independent_java_mods':2,'closed':True}))
    finally:session.close();runtime.close()
