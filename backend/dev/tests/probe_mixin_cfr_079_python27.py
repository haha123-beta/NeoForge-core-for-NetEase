from __future__ import print_function
import io,json,sys,types
with io.open(sys.argv[1],'r',encoding='utf-8') as stream:data=json.load(stream)
scope={};eval(compile(data['fake_engine_source'].encode('utf-8'),'sdk_contract_double.py','exec'),scope)
FakeEngine=scope['FakeEngine']
class Binding(object):
    @staticmethod
    def Binding(**kwargs):return lambda cls:cls
    @staticmethod
    def InitServer():return lambda method:method
    InitClient=InitServer
    DestroyServer=InitServer
    DestroyClient=InitServer
sdk=types.ModuleType('mod');sdk.__path__=[]
common=types.ModuleType('mod.common');common.__path__=[]
binding=types.ModuleType('mod.common.mod');binding.Mod=Binding
sys.modules.update({'mod':sdk,'mod.common':common,'mod.common.mod':binding})
scripts=['NeoCoreSourceScripts']+[row['script'] for row in data['contents']]
rows=[]
for side in ('SERVER','CLIENT'):
    for core_first in (True,False):
        before=list(sys.path);core=None;providers=[]
        try:
            for path in [data['core_pack']]+[row['pack'] for row in data['contents']]:sys.path.insert(0,path)
            engine=FakeEngine();engine.GetEngineCompFactory=lambda:object()
            engine.GetMinecraftEnum=lambda:type('Enums',(),{'AttrType':type('Attr',(),{'HEALTH':0})})()
            def register(namespace,name,path):
                module,unused,attribute=path.rpartition('.')
                cls=getattr(__import__(module,globals(),locals(),[attribute],0),attribute)
                instance=cls(namespace,name);engine.systems[(namespace,name)]=instance;return instance
            engine.RegisterSystem=register
            core=__import__('NeoCoreSourceScripts.modMain',globals(),locals(),['start'],0)
            if core_first:core.start(engine,side)
            for row in data['contents']:
                entry=__import__(row['script']+'.modMain',globals(),locals(),['register_provider'],0)
                providers.append(entry.register_provider(engine,side))
            if not core_first:core.start(engine,side)
            engine.emit('Minecraft','Engine','Load'+side.title()+'AddonScriptsAfter',{})
            system=engine.GetSystem('NeoCore','Loader');report=system.GetContentReport()
            assert all(r['ready'] for r in report['mods'].values()),repr(report)
            assert all(p.last_registration['accepted'] for p in providers)
            loader=system.registry._session.loader
            native=loader.contexts['cfr_native_example'].instance
            source=loader.contexts['cfr_source_example'].instance
            assert (native.menu.containerId,native.menu.body,native.seen,source.value)==(7,1,1,7)
            hook_module=core.HOSTS[side].runtime.load('neoforge.mixin_hooks')
            hooks=hook_module.MixinHooks
            assert hooks.count()==1
            hook_rows=hook_module._ROWS
            registrations=list(hook_rows)
            for unused in range(150):engine.emit('Minecraft','Engine','OnScriptTick'+side.title(),{})
            ticks=100 if side=='SERVER' else 0
            assert native.ticks==ticks,native.ticks
            assert native.menu.body==ticks+1,native.menu.body
            assert native.menu.containerId==(ticks if ticks else 7)
            core.close(side)
            for provider in providers:provider.Destroy()
            # SourceModuleLoader clears module globals on close. Inspect the
            # retained registrations, not a function of the destroyed module.
            assert not hook_rows
            assert all(not r['active'] and r['callback'] is None and r['owner'] is None for r in registrations)
            assert engine.listeners==[],repr(engine.listeners)
            assert all(r['state']=='unloaded' for r in loader.results.values())
            rows.append({'side':side,'core_first':core_first,'source_callback_value':source.value,
                'business_ticks':ticks,'menu_hook_calls':native.menu.body,'listeners_after_close':0,'hooks_after_close':len(hook_rows)})
        finally:
            if core is not None:core.close(side)
            for provider in providers:provider.Destroy()
            sys.path[:]=before
            for name in list(sys.modules):
                if name.split('.')[0] in scripts:sys.modules.pop(name,None)
print(json.dumps({'runs':rows,'sdk_scope':'explicit contract double','engine_verified':False}))
