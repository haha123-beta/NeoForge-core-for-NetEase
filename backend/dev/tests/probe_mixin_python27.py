from __future__ import print_function
import io,json,sys
with io.open(sys.argv[1],'r',encoding='utf-8') as stream:data=json.load(stream)
scope={'__name__':'mixin_source_loader'}
eval(compile(data['loader_source'].encode('utf-8'),'source_modules.py','exec'),scope)
loader=scope['SourceModuleLoader'];runs=[]
for side in ('SERVER','CLIENT'):
 runtime=loader(data['core']['sources'])
 session=runtime.load('core.bundled_mods').BundledModSession(data['core']['sources'],[data['content']],side=side,runtime=runtime)
 try:
  results=session.loader.activate();assert results['runtime_source_mixin_example']['ready'],repr(results)
  state=session.loader.contexts['runtime_source_mixin_example'].instance
  assert state.cancelled==40
  driver=runtime.load('core.content_events').ContentTickDriver(session.loader,side)
  for unused in range(150):driver.on_tick()
  audit=runtime.load('demo.Audit').Audit
  assert state.total==(500 if side=='SERVER' else 0)
  assert (audit.heads,audit.bodies,audit.returns)==((101,100,100) if side=='SERVER' else (1,0,0))
  for case in data['cases']:
   sources=dict(data['core']['sources']);sources.update(case['sources'])
   case_runtime=loader(sources);api=case_runtime.load('core.java_api');imports=api.JavaApiImports(case_runtime).install(api.collect_java_api())
   try:actual=str(case_runtime.load('demo.Use').Use().run())
   finally:imports.close();case_runtime.close()
   assert actual==case['jdk_result']==str(case['expected']),repr((actual,case['jdk_result']))
  callbacks=runtime.load('neoforge.mixin_callbacks');integer=runtime.load('java_stdlib.lang').Integer
  ci=callbacks.CallbackInfo('run',False)
  try:ci.cancel();raise AssertionError('noncancellable accepted')
  except callbacks.CancellationException:pass
  assert not ci.isCancelled()
  cir=callbacks.CallbackInfoReturnable('run',True);assert cir.getReturnValue() is None and cir.getReturnValueI()==0
  cir.setReturnValue(integer(9));assert cir.isCancelled() and cir.getReturnValueI()==9
  fixed=callbacks.CallbackInfoReturnable('run',False,7)
  try:fixed.setReturnValue(integer(9));raise AssertionError('noncancellable value accepted')
  except callbacks.CancellationException:pass
  assert not fixed.isCancelled() and fixed.getReturnValueI()==7
  session.close();assert session.loader.results['runtime_source_mixin_example']['state']=='unloaded'
  assert session.loader.contexts['runtime_source_mixin_example'].game_bus.listenerCount()==0
  runs.append({'side':side,'total':state.total,'cancelled':state.cancelled,'heads':audit.heads,'bodies':audit.bodies,'returns':audit.returns,'business_ticks':100,'jdk_cases':len(data['cases']),'closed':True,'listeners':0})
 finally:session.close();runtime.close()
old=loader(data['old_core']['sources'])
old_session=old.load('core.bundled_mods').BundledModSession(data['old_core']['sources'],[data['content']],side='SERVER',runtime=old)
try:
 results=old_session.loader.activate();assert results['runtime_source_mixin_example']['phase']=='runtime_requirements',repr(results)
 assert not results['runtime_source_mixin_example'].get('ready')
 assert 'demo.Target' not in old.modules and 'demo.Main' not in old.modules
finally:old_session.close();old.close()
print(json.dumps({'python':sys.version,'runs':runs,'r53_core_blocked_before_entrypoint':True,'callback_contract_checks':6,'engine_verified':False,'jdk_scope':'mechanically woven Java with official Mixin callbacks; no Sponge bytecode transformation'}))
