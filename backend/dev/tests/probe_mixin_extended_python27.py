from __future__ import print_function
import io,json,sys
with io.open(sys.argv[1],'r',encoding='utf-8') as stream:data=json.load(stream)
scope={'__name__':'mixin_extended_source_loader'}
eval(compile(data['loader_source'].encode('utf-8'),'source_modules.py','exec'),scope)
loader=scope['SourceModuleLoader'];runs=[]
for side in ('SERVER','CLIENT'):
 for case in data['cases']:
  sources=dict(data['core']['sources']);sources.update(case['sources'])
  runtime=loader(sources);api=runtime.load('core.java_api');imports=api.JavaApiImports(runtime).install(api.collect_java_api())
  try:actual=str(runtime.load('demo.Use').Use().run())
  finally:imports.close();runtime.close()
  assert actual==case['jdk_result']==str(case['expected']),repr((case['name'],actual,case['jdk_result']))
 runtime=loader(data['core']['sources'])
 session=runtime.load('core.bundled_mods').BundledModSession(data['core']['sources'],[data['content']],side=side,runtime=runtime)
 try:
  results=session.loader.activate();assert results['runtime_mixin_fields_example']['ready'],repr(results)
  state=session.loader.contexts['runtime_mixin_fields_example'].instance
  assert state.first.read()==5 and state.second.read()==10 and state.checks==2
  driver=runtime.load('core.content_events').ContentTickDriver(session.loader,side)
  for unused in range(150):driver.on_tick()
  assert state.total==(1500 if side=='SERVER' else 0),state.total
  session.close();assert session.loader.results['runtime_mixin_fields_example']['state']=='unloaded'
  assert session.loader.contexts['runtime_mixin_fields_example'].game_bus.listenerCount()==0
  runs.append({'side':side,'checks':state.checks,'first':state.first.read(),'second':state.second.read(),'total':state.total,'business_ticks':100,'listeners':0,'closed':True,'jdk_cases':len(data['cases'])})
 finally:session.close();runtime.close()
old=loader(data['old_core']['sources'])
session=old.load('core.bundled_mods').BundledModSession(data['old_core']['sources'],[data['content']],side='SERVER',runtime=old)
try:
 results=session.loader.activate();assert results['runtime_mixin_fields_example']['phase']=='runtime_requirements',repr(results)
 assert not results['runtime_mixin_fields_example'].get('ready')
 assert 'fielddemo.Main' not in old.modules and 'fielddemo.Target' not in old.modules
finally:session.close();old.close()
print(json.dumps({'python':sys.version,'runs':runs,'r55_core_blocked_before_entrypoint':True,'engine_verified':False,'sponge_bytecode_transformer_executed':False}))
