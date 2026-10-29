from __future__ import print_function
import io,json,sys
with io.open(sys.argv[1],'r',encoding='utf-8') as stream:data=json.load(stream)
scope={'__name__':'interface_probe_loader'}
eval(compile(data['loader_source'].encode('utf-8'),'source_modules.py','exec'),scope)
runtime=scope['SourceModuleLoader'](data['sources'])
api=runtime.load('core.java_api');imports=api.JavaApiImports(runtime).install(api.collect_java_api())
try:
    first=runtime.load('x.First').First();second=runtime.load('x.Second').Second()
    actual=str(first.total())+','+str(second.total())
    assert actual==data['expected'],repr(actual)
    try:runtime.load('x.Values').Values();raise AssertionError('interface instantiated')
    except TypeError:pass
    assert isinstance(first,runtime.load('x.Values').Values)
    print(json.dumps({'actual':actual,'python2_executed':True}))
finally:imports.close();runtime.close()
