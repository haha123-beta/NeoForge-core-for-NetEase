from __future__ import print_function
import io,json,sys
with io.open(sys.argv[1],'r',encoding='utf-8') as stream:data=json.load(stream)
scope={'__name__':'interfaces082_loader'}
eval(compile(data['loader_source'].encode('utf-8'),'source_modules.py','exec'),scope)
runtime=scope['SourceModuleLoader'](data['sources'])
api=runtime.load('core.java_api');imports=api.JavaApiImports(runtime).install(api.collect_java_api())
try:
    module=runtime.load(data['module']);actual=str(getattr(module,data['class_name'])().run())
    assert actual==data['expected'],repr((actual,data['expected']))
    print(json.dumps({'actual':actual,'python2_executed':True}))
finally:imports.close();runtime.close()
