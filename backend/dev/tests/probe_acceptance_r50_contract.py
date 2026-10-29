# -*- coding: utf-8 -*-
from __future__ import print_function


def self_close_trace(load, setup, mode='context'):
    session, channel, sdk, event, contexts = setup(load)
    channel.receive_native(event)
    context = contexts[0]
    def work():
        if mode == 'context': context.close()
        elif mode == 'disconnect': channel.disconnect('trusted')
        else: channel.transport.close()
        raise ValueError(u'关闭后中文任务失败')
    context.enqueueWork(work)
    completed = session.tick(1)
    result = {'completed': completed, 'failures': channel.transport.work_failures,
              'errors': list(channel.transport.work_errors), 'pending': context.pending()}
    session.close()
    return result


def startup_trace(load):
    def fail(specs): raise ValueError(u'中文启动失败')
    registry = load('core.content_registry').ContentRegistry(fail)
    registry.register('probe', 1, [{'folder': 'probe'}])
    escaped = None
    try: registry.start()
    except Exception as error: escaped = type(error).__name__
    return {'escaped': escaped, 'state': registry.state, 'error': registry.error,
            'startup_error': registry.startup_error}


def destroy_trace(load):
    calls, listeners = [], []
    class Api(object):
        def GetEngineNamespace(self): return 'Minecraft'
        def GetEngineSystemName(self): return 'Engine'
        def GetServerSystemCls(self):
            class System(object):
                def __init__(self, *args): pass
                def ListenForEvent(self, *row): listeners.append(row)
                def UnListenForEvent(self, *row): listeners.remove(row)
            return System
    class Resource(object):
        def __init__(self, name): self.name = name
        def close(self):
            calls.append(self.name)
            raise ValueError(u'中文清理失败')
    class Session(Resource):
        def __init__(self):
            Resource.__init__(self, 'content')
            self.loader = self
            self.results = {}
    system = load('core.content_registry').install_content_system(Api(), lambda specs: None)('NeoCore', 'Loader')
    system._network_session = Resource('network')
    system._owned_runtimes[0] = Resource('entity')
    system._entity_mod_bus = Resource('bus')
    system.registry._session = Session()
    system.registry.state = 'initialized'
    escaped = None
    try: system.Destroy()
    except Exception as error: escaped = type(error).__name__
    return {'escaped': escaped, 'calls': calls, 'listeners': len(listeners),
            'state': system.registry.state, 'error': system.registry.error,
            'cleanup_errors': list(system.registry.cleanup_errors)}


def before_trace(load, setup):
    return {'self_close': self_close_trace(load, setup), 'startup': startup_trace(load),
            'destroy': destroy_trace(load)}


def run(load, setup):
    checks = []
    def check(name, condition):
        assert condition, name
        checks.append(name)
    for mode in ('context', 'disconnect', 'transport'):
        result = self_close_trace(load, setup, mode)
        check('failure retained after ' + mode + ' close', result == {
            'completed': 0, 'failures': 1, 'errors': [u'关闭后中文任务失败'], 'pending': 0})
    start = startup_trace(load)
    check('Unicode startup failure is reported', start == {'escaped': None, 'state': 'failed',
        'error': u'中文启动失败', 'startup_error': u'中文启动失败'})
    destroy = destroy_trace(load)
    check('Unicode Destroy failure does not escape', destroy['escaped'] is None)
    check('Destroy attempts every owned resource', destroy['calls'] == ['network', 'entity', 'content', 'bus'])
    check('Destroy still removes engine listeners', destroy['listeners'] == 0)
    check('Destroy preserves failure state and messages', destroy['state'] == 'close_failed'
          and u'中文清理失败' in destroy['error'] and len(destroy['cleanup_errors']) == 3)
    n = load('neoforge.network')
    class Packet(n.CustomPacketPayload):
        TYPE = n.CustomPacketPayload.make_type('acceptance', 'packet')
    distributor = n.PacketDistributor()
    for unused in range(150): distributor.sendToServer(Packet())
    check('sentCount preserves bounded history contract', distributor.sentCount() == 128)
    check('repr explains history without claiming delivery', 'retained_history=128/128' in repr(distributor)
          and 'not delivery acknowledgements' in repr(distributor))
    distributor.clear()
    check('clear still resets history', distributor.sentCount() == 0)
    return checks
