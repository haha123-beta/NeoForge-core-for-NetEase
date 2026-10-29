from __future__ import print_function
import io,json,sys,types
with io.open(sys.argv[1],'r',encoding='utf-8') as stream:data=json.load(stream)
scope={};eval(compile(data['fake_engine_source'].encode('utf-8'),'sdk_double.py','exec'),scope)
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
sys.path[:0]=[data['root']+'/behavior_pack_neocore',data['root']+'/behavior_pack-gui_sample']
rows=[]
for side in ('SERVER','CLIENT'):
    for core_first in (True,False):
        engine=FakeEngine();engine.GetEngineCompFactory=lambda:object()
        engine.GetMinecraftEnum=lambda:type('Enums',(),{'AttrType':type('Attr',(),{'HEALTH':0})})()
        def register(namespace,name,path):
            module,unused,attribute=path.rpartition('.')
            cls=getattr(__import__(module,globals(),locals(),[attribute],0),attribute)
            instance=cls(namespace,name);engine.systems[(namespace,name)]=instance;return instance
        engine.RegisterSystem=register
        core=__import__('NeoCoreSourceScripts.modMain',globals(),locals(),['start'],0)
        if core_first:core.start(engine,side)
        entry=__import__('gui_sampleScripts.modMain',globals(),locals(),['register_provider'],0)
        provider=entry.register_provider(engine,side)
        if not core_first:core.start(engine,side)
        engine.emit('Minecraft','Engine','Load'+side.title()+'AddonScriptsAfter',{})
        system=engine.GetSystem('NeoCore','Loader')
        assert provider.last_registration['accepted']
        report=system.GetContentReport();assert report['mods']['gui_sample']['ready'],repr(report)
        loader=system.registry._session.loader;value=loader.contexts['gui_sample'].instance.value
        assert value==23,repr(value)
        core.close(side);provider.Destroy()
        assert engine.listeners==[],repr(engine.listeners)
        assert loader.results['gui_sample']['state']=='unloaded'
        rows.append({'side':side,'core_first':core_first,'value':value,'listeners_after_close':0})
        for name in list(sys.modules):
            if name.split('.')[0] in ('NeoCoreSourceScripts','gui_sampleScripts'):sys.modules.pop(name,None)
print(json.dumps({'runs':rows,'sdk_scope':'contract double','engine_verified':False}))
