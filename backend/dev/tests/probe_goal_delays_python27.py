from __future__ import print_function
import io,json,sys
with io.open(sys.argv[1], 'r', encoding='utf-8') as stream:
    data=json.load(stream)
namespace={'__name__':'probe_source_loader'}
eval(compile(data['loader_source'].encode('utf-8'),'source_modules.py','exec'),namespace)
runtime=namespace['SourceModuleLoader'](data['core']['sources'])
runtime.add_sources({'example.Delay':{'source':data['generated_source'],'is_package':False}})
api=runtime.load('core.java_api');scope=api.JavaApiImports(runtime).install(api.collect_java_api())
try:
    cls=runtime.load('example.Delay').Delay;obj=cls();Integer=runtime.load('java_stdlib.lang').Integer
    for value,expected in zip(data['values'],data['expected']):
        assert type(runtime.load('java_stdlib.primitives').Int32.wrap(value)) is int
        assert obj.run(value)==expected
        assert cls.reduce(value)==expected
        for name in ('bound','parent','reduced'):
            result=getattr(obj,name)().apply(Integer.valueOf(value))
            assert isinstance(result,Integer)
            assert result.intValue()==expected
    obj.exact=True
    for value in data['values']:assert obj.run(value)==value
    for name in ('bound','parent','reduced'):
        try:getattr(obj,name)().apply(None)
        except runtime.load('java_stdlib.lang').NullPointerException:pass
        else:raise AssertionError('Missing unboxing null check')
    print(json.dumps({'python':sys.version,'int_cases':len(data['values']),'generated_delays':True,'boxed_method_references':True,'null_unboxing':True}))
finally:
    scope.close();runtime.close()
