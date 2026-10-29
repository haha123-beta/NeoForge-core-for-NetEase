from __future__ import print_function
import io,json,sys
with io.open(sys.argv[1],'r',encoding='utf-8') as stream:data=json.load(stream)
namespace={'__name__':'source_loader_probe'}
eval(compile(data['loader_source'].encode('utf-8'),'source_modules.py','exec'),namespace)
runtime=namespace['SourceModuleLoader'](data['core']['sources'])
runtime.add_sources({'example.Selector':{'source':data['generated_source'],'is_package':False}})
api=runtime.load('core.java_api');scope=api.JavaApiImports(runtime).install(api.collect_java_api())
try:
    module=runtime.load('example.Selector');goals=runtime.load('minecraft.goals')
    low,high=module.A(),module.A();selector=goals.GoalSelector()
    assert module.Logic.run(selector,low,high)==112
    assert module.Logic.identity(high)
    assert [w.getPriority() for w in selector.getAvailableGoals()]==[8,1]
    cursor=selector.getAvailableGoals().iterator();assert cursor.next().getPriority()==8;cursor.remove()
    assert selector.getAvailableGoals().size()==1
    selector.stopAll()
    assert selector.getRunningGoals()==[]
    # Runtime-only operation stream was independently compared with the original JVM.
    trace=[]
    class P(goals.Goal):
        def __init__(self,name,flag):
            goals.Goal.__init__(self);self.name=name;self.enabled=True;self.every=False;self.interruptible=True;self.setFlags(goals.EnumSet.of(flag))
        def canUse(self):trace.append(self.name+'?');return self.enabled
        def canContinueToUse(self):trace.append(self.name+'~');return self.enabled
        def isInterruptable(self):return self.interruptible
        def requiresUpdateEveryTick(self):return self.every
        def start(self):trace.append(self.name+'+')
        def stop(self):trace.append(self.name+'-')
        def tick(self):trace.append(self.name+'!')
    selector=goals.GoalSelector();items=[P(chr(65+i),goals.Goal.Flag._values[i%4]) for i in range(6)]
    for op,index,value in data['operations']:
        if op=='add':selector.addGoal(value,items[index])
        elif op=='remove':selector.removeGoal(items[index])
        elif op=='enabled':items[index].enabled=value
        elif op=='interruptible':items[index].interruptible=value
        elif op=='every':items[index].every=value
        elif op=='control':selector.setControlFlag(goals.Goal.Flag._values[index%4],value)
        elif op=='running':selector.tickRunningGoals(value)
        elif op=='tick':selector.tick()
        else:raise AssertionError(op)
    assert ','.join(trace)==data['jvm_trace'],repr(trace)
    print(json.dumps({'python':sys.version,'generated_selector_calls':True,'reference_identity':True,'insertion_order':True,'mixed_operations':len(data['operations']),'original_jvm_trace_match':True}))
finally:scope.close();runtime.close()
