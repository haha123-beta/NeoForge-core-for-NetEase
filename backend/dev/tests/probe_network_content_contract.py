# -*- coding: utf-8 -*-
from __future__ import print_function


def run(server_runtime, client_runtime, core_sources, bundle, extra_contents=()):
    class Api(object):
        def __init__(self):
            self.listeners = []
            self.remote = None
            self.fail_network = False
        def GetServerSystemCls(self):
            api = self
            class System(object):
                def __init__(self, namespace, name):
                    self.namespace, self.name = namespace, name
                def ListenForEvent(self, *row):
                    assert getattr(row[4], '__self__', row[3]) is row[3], 'SDK callback owner mismatch'
                    if api.fail_network and row[2].startswith('NeoCorePayload_'):
                        raise RuntimeError('native channel listener failed')
                    api.listeners.append(row)
                def UnListenForEvent(self, *row): api.listeners.remove(row)
                def BroadcastEvent(self, event, args): api.emit(self.namespace, self.name, event, args)
                def NotifyToServer(self, name, data):
                    data = dict(data); data['__id__'] = 'engine-player'
                    api.remote.emit(self.namespace, self.name, name, data)
                def NotifyToClient(self, player, name, data):
                    assert player == 'engine-player'
                    api.remote.emit(self.namespace, self.name, name, dict(data))
                def BroadcastToAllClient(self, name, data): self.NotifyToClient('engine-player', name, data)
            return System
        GetClientSystemCls = GetServerSystemCls
        def GetEngineNamespace(self): return 'Minecraft'
        def GetEngineSystemName(self): return 'Engine'
        def emit(self, ns, system, event, args=None):
            for row in list(self.listeners):
                if row[:3] == (ns, system, event): row[4](args)
    server_api, client_api = Api(), Api()
    server_api.remote, client_api.remote = client_api, server_api
    systems = []
    for runtime, api, side in ((server_runtime, server_api, 'SERVER'), (client_runtime, client_api, 'CLIENT')):
        load = runtime.load
        def factory(specs, load=load, side=side, runtime=runtime):
            return load('core.bundled_mods').BundledModSession(core_sources, [bundle] + list(extra_contents), side=side, runtime=runtime)
        cls = load('core.content_registry').install_content_system(api, factory, side)
        system = cls('NeoCore', 'Loader')
        system.RegisterContent('network_content', 1, [{'bundle': bundle}])
        for index, extra in enumerate(extra_contents):
            system.RegisterContent('extra_content_' + str(index), 1, [{'bundle': extra}])
        system._on_scripts_loaded()
        report = system.GetContentReport()
        assert report['state'] == 'initialized', repr(report)
        assert report['mods']['network_roundtrip'].get('ready'), repr(report)
        if extra_contents:
            assert report['mods']['runtime_entity_example'].get('ready'), repr(report)
        assert report['network']['channels']['network_roundtrip']['payload_types'] == ['network_roundtrip:counter']
        systems.append(system)
    server, client = systems
    # SDK has 30 frames/s; the content driver emits 20 Java ticks/s.
    for unused in range(150):
        client_api.emit('Minecraft', 'Engine', 'OnScriptTickClient')
        server_api.emit('Minecraft', 'Engine', 'OnScriptTickServer')
    # Flush final response enqueued during the last server frame.
    client.GetNetworkSession().tick()
    states = [s.registry._session.loader.contexts['network_roundtrip'].instance for s in systems]
    for state in states:
        assert state['ticks'] == 100 and state['received'] == 5 and state['total'] == 5, repr(state)
    assert states[0]['sent'] == 0 and states[1]['sent'] == 5
    if extra_contents:
        assert server.registry._session.loader.contexts['runtime_entity_example'].instance.ticks == 100
        assert client.registry._session.loader.contexts['runtime_entity_example'].instance.ticks == 0
    for system in systems:
        assert system.GetNetworkSession().report()['error_count'] == 0
        system.Destroy()
        assert system.GetContentReport()['state'] == 'closed', repr(system.GetContentReport())
        assert system.GetContentReport()['network']['listeners'] == 0
        if extra_contents:
            assert system.GetContentReport()['mods']['runtime_entity_example']['state'] == 'unloaded'
    assert not server_api.listeners and not client_api.listeners
    assert all(state['closed'] for state in states)
    # Native network startup failure must roll back the content that registered it.
    broken_api = Api(); broken_api.fail_network = True
    def factory(specs):
        return server_runtime.load('core.bundled_mods').BundledModSession(
            core_sources, [bundle], side='SERVER', runtime=server_runtime)
    cls = server_runtime.load('core.content_registry').install_content_system(broken_api, factory, 'SERVER')
    broken = cls('NeoCore', 'Loader')
    broken.RegisterContent('network_content', 1, [{'bundle': bundle}])
    broken._on_scripts_loaded()
    report = broken.GetContentReport()
    assert report['state'] == 'failed' and 'network:' in report['error'], repr(report)
    assert report['mods']['network_roundtrip']['state'] == 'unloaded', repr(report)
    assert report['network']['listeners'] == 0
    broken.Destroy()
    assert not broken_api.listeners
    return {'driver_ticks_each_side': 100, 'requests': 5, 'replies': 5,
            'native_identity': True, 'closed': True, 'startup_rollback': True, 'engine_verified': False}
