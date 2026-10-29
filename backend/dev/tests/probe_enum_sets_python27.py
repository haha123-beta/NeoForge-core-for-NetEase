from __future__ import print_function
import io,json,sys
with io.open(sys.argv[1],'r',encoding='utf-8') as stream:data=json.load(stream)
ns={'__name__':'probe_source_loader'}
eval(compile(data['loader_source'].encode('utf-8'),'source_modules.py','exec'),ns)
runtime=ns['SourceModuleLoader'](data['core']['sources'])
runtime.add_sources({'example.Flags':{'source':data['generated_source'],'is_package':False}})
api=runtime.load('core.java_api');scope=api.JavaApiImports(runtime).install(api.collect_java_api())
try:
    module=runtime.load('example.Flags');obj=module.A()
    assert obj.run()==9
    assert obj.named()
    assert obj.callbacks()==9
    Goal=runtime.load('minecraft.goals').Goal
    flag=Goal.Flag.MOVE
    assert isinstance(flag.name(),runtime.load('java_stdlib.lang').JavaString)
    assert obj.getFlags().contains(flag)
    EnumSet=runtime.load('java_stdlib.enum_sets').EnumSet
    assert str(EnumSet.of(Goal.Flag.TARGET,flag))=='[MOVE, TARGET]'
    assert list(Goal.Flag.values())[0] is flag
    lang=runtime.load('java_stdlib.lang');Large=type('Large',(lang.Enum,),{'_values':()})
    values=[]
    for n in range(130):
        v=Large();v._name='V'+str(n);v._ordinal=n;values.append(v)
    Large._values=tuple(values)
    large=EnumSet.of(values[0],values[64]);cursor=large.iterator()
    large.add(values[1]);large.remove(values[64]);large.add(values[65])
    assert [v.ordinal() for v in cursor]==[0,65]
    assert EnumSet.complementOf(large).size()==127
    driver=runtime.load('minecraft.goals').GoalSelector();driver.addGoal(1,obj);driver.tick();driver.stopAll()
    print(json.dumps({'python':sys.version,'java_original_flags':True,'typed_generic_chain':True,'values_array':True,'jumbo_iteration':True,'selector_accepts_generated_goal':True}))
finally:scope.close();runtime.close()
