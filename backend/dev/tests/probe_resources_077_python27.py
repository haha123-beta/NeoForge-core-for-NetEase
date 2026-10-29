from __future__ import print_function
import io,json,sys,types
with io.open(sys.argv[1],'r',encoding='utf-8') as stream:data=json.load(stream)
scope={}
eval(compile(data['fake_engine_source'].encode('utf-8'),'sdk_contract_double.py','exec'),scope)
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
prefixes=['NeoCoreSourceScripts']+[row['script'] for row in data['contents']]


def cleanup():
    for name in list(sys.modules):
        if name.split('.')[0] in prefixes:sys.modules.pop(name,None)


rows=[]
for side in ('SERVER','CLIENT'):
    for core_first in (True,False):
        before=list(sys.path);core=None;providers=[]
        try:
            for root in [data['core_pack']]+[r['pack'] for r in data['contents']]:sys.path.insert(0,root)
            engine=FakeEngine()
            engine.GetEngineCompFactory=lambda:object()
            engine.GetMinecraftEnum=lambda:type('Enums',(),{'AttrType':type('Attr',(),{'HEALTH':0})})()
            def register(namespace,name,path):
                module,unused,attribute=path.rpartition('.')
                cls=getattr(__import__(module,globals(),locals(),[attribute],0),attribute)
                instance=cls(namespace,name);engine.systems[(namespace,name)]=instance
                return instance
            engine.RegisterSystem=register
            core=__import__('NeoCoreSourceScripts.modMain',globals(),locals(),['start'],0)
            if core_first:core.start(engine,side)
            for row in data['contents']:
                entry=__import__(row['script']+'.modMain',globals(),locals(),['register_provider'],0)
                providers.append(entry.register_provider(engine,side))
            if not core_first:core.start(engine,side)
            system=engine.GetSystem('NeoCore','Loader')
            event='Load'+side.title()+'AddonScriptsAfter'
            engine.emit('Minecraft','Engine',event,{})
            engine.emit('Minecraft','Engine',event,{})
            report=system.GetContentReport();assert all(r.get('ready') for r in report['mods'].values()),repr(report)
            assert all(p.last_registration['accepted'] for p in providers)
            loader=system.registry._session.loader
            assert loader.order==['resources_alpha','resources_beta'],repr(loader.order)
            states=[loader.contexts['resources_'+s].instance for s in ('alpha','beta')]
            assert [s.initial for s in states]==data['jdk_initials']
            for unused in range(150):engine.emit('Minecraft','Engine','OnScriptTick'+side.title(),{})
            expected=[2300,1400] if side=='SERVER' else [0,0]
            assert [s.total for s in states]==expected
            core.close(side)
            for provider in providers:provider.Destroy()
            assert engine.listeners==[],repr(engine.listeners)
            assert all(r['state']=='unloaded' for r in loader.results.values())
            assert all(c.game_bus.listenerCount()==0 for c in loader.contexts.values())
            rows.append({'side':side,'core_first':core_first,'initial':[s.initial for s in states],
                'total':[s.total for s in states],'unloaded':2,'listeners_after_close':0})
        finally:
            if core is not None:core.close(side)
            for provider in providers:provider.Destroy()
            sys.path[:]=before;cleanup()

# Frozen actual r75 native core must reject before any original content import.
before=list(sys.path);core=None;providers=[]
try:
    sys.path.insert(0,data['old_core_pack'])
    for row in data['contents']:sys.path.insert(0,row['pack'])
    engine=FakeEngine();engine.RegisterSystem=register
    core=__import__('NeoCoreSourceScripts.modMain',globals(),locals(),['start'],0)
    core.start(engine,'CLIENT')
    for row in data['contents']:
        entry=__import__(row['script']+'.modMain',globals(),locals(),['register_provider'],0)
        providers.append(entry.register_provider(engine,'CLIENT'))
    engine.emit('Minecraft','Engine','LoadClientAddonScriptsAfter',{})
    assert all(p.last_registration=={'accepted':False,'phase':'resources_protocol'} for p in providers)
    system=engine.GetSystem('NeoCore','Loader');assert system.GetContentReport()['packs']==[]
    assert not any(name.startswith('common.') for name in core.HOSTS['CLIENT'].runtime.modules)
finally:
    if core is not None:core.close('CLIENT')
    for provider in providers:provider.Destroy()
    sys.path[:]=before;cleanup()
print(json.dumps({'python':sys.version,'runs':rows,'r75_blocked_before_original_import':True,
    'sdk_scope':'explicit contract double, not NetEase engine','engine_verified':False}))
