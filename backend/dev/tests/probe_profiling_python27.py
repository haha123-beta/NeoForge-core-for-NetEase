from __future__ import print_function
import io,json,sys
with io.open(sys.argv[1],'r',encoding='utf-8') as stream:data=json.load(stream)
ns={'__name__':'probe_source_loader'}
eval(compile(data['loader_source'].encode('utf-8'),'source_modules.py','exec'),ns)
runtime=ns['SourceModuleLoader'](data['core']['sources'])
runtime.add_sources(data['converted_sources'])
api=runtime.load('core.java_api');scope=api.JavaApiImports(runtime).install(api.collect_java_api())
try:
    assert runtime.load('generic.selector.Logic').Logic.run()==12
    profiling=runtime.load('minecraft.profiling');p=profiling.InactiveProfiler.INSTANCE
    assert profiling.ProfilerFiller.tee(p,None) is None
    calls=[]
    class Supplier:
        def get(self):calls.append('bad');return 'x'
    p.push(Supplier());p.incrementCounter(Supplier(),1);p.popPush(Supplier())
    assert calls==[]
    assert p.getResults() is profiling.EmptyProfileResults.EMPTY
    assert p.getResults().getTimes('root').isEmpty()
    assert p.getResults().getTickDuration()==0
    assert profiling.ProfileResults.demanglePath('a\x1eb')=='a.b'
    assert [str(v.name()) for v in profiling.MetricCategory.values()][-2:]==['CPU','GPU']
    goals=runtime.load('minecraft.goals');trace=[];selector=goals.GoalSelector();extra=None
    class P(goals.Goal):
        def __init__(self,name):goals.Goal.__init__(self);self.name=name
        def canUse(self):trace.append(self.name+'?');return True
        def start(self):
            trace.append(self.name+'+')
            if self.name=='A':selector.addGoal(3,extra)
        def tick(self):trace.append(self.name+'!')
    extra=P('C');selector.addGoal(1,P('A'));selector.addGoal(2,P('B'));selector.tick()
    assert trace==data['append_jvm_trace'],repr(trace)
    selector.stopAll()
finally:scope.close();runtime.close()
for side in ('SERVER','CLIENT'):
    runtime=ns['SourceModuleLoader'](data['core']['sources'])
    session=runtime.load('core.bundled_mods').BundledModSession(data['core']['sources'],[data['content']],side=side,runtime=runtime)
    try:
        row=session.loader.activate()['runtime_selector_example']
        assert row['state']=='blocked' and 'neoforge' in row['message'],repr(row)
        assert row['phase']=='dependencies'
        assert all(context.instance is None for context in session.loader.contexts.values())
    finally:session.close();runtime.close()
print(json.dumps({'python':sys.version,'original_source_logic':12,'inactive_supplier_calls':0,'reentrant_append_matches_original_jvm':True,'mod_entry':'blocked_missing_declared_neoforge_platform_version','engine_verified':False}))
