# -*- coding: utf-8 -*-
from __future__ import print_function
import gc
import weakref


def setup(load, handler=None, resolver=None):
    n = load('neoforge.network')
    m = load('core.network_session')
    class Api(object):
        def GetEngineNamespace(self): return 'Minecraft'
        def GetEngineSystemName(self): return 'Engine'
    class System(object):
        def __init__(self): self.listeners = []; self.fail = False
        def ListenForEvent(self, *row): self.listeners.append(row)
        def UnListenForEvent(self, *row):
            if self.fail:
                self.fail = False
                raise ValueError(u'中文卸载失败')
            self.listeners.remove(row)
    class Packet(n.CustomPacketPayload):
        TYPE = n.CustomPacketPayload.make_type('stability', 'packet')
    contexts = []
    def receive(packet, context):
        contexts.append(context)
        if handler: handler(context)
    sdk = System()
    session = m.ModSdkNetworkSession(sdk, Api(), 'server', distributor=n.PacketDistributor())
    registry = n.PayloadRegistry()
    n.PayloadRegistrar('49', registry).playToServer(Packet.TYPE, n.StreamCodec.unit(Packet()), receive)
    channel = session.open_channel('stability', registry, player_resolver=resolver)
    event = {'protocol': 1, 'channel': channel.channel, 'version': '1',
             'payload_version': '49', 'type': 'stability:packet', 'data': [], '__id__': 'trusted'}
    return session, channel, sdk, event, contexts


def before_trace(load):
    def fail(player): raise ValueError(u'中文入口失败')
    session, channel, sdk, event, contexts = setup(load, resolver=fail)
    escaped = None
    try: accepted = channel.receive_native(event)
    except Exception as error:
        escaped = type(error).__name__; accepted = None
    result = {'escaped': escaped, 'accepted': accepted, 'errors': session.error_count,
              'records': len(session.errors)}
    session.close()
    return result


def run(load):
    checks = []
    def check(name, value):
        assert value, name
        checks.append(name)
    result = before_trace(load)
    check('Unicode ingress failure returns false without secondary exception', result ==
          {'escaped': None, 'accepted': False, 'errors': 1, 'records': 1})
    session, channel, sdk, event, contexts = setup(load)
    check('valid ingress still accepted', channel.receive_native(event))
    def fail(): raise ValueError(u'中文任务失败')
    observed = []
    context = contexts[0]
    def inspect(): observed.append(session.report()['channels']['stability']['pending'])
    context.enqueueWork(inspect); context.enqueueWork(fail); context.enqueueWork(lambda: observed.append('tail'))
    check('running context tail included in pending', session.tick(1) == 1 and observed == [2])
    check('failed work consumes only one budget slot', session.tick(1) == 0 and context.pending() == 1)
    report = session.report()['channels']['stability']
    check('queued failures queryable separately from ingress', report['work_failures'] == 1
          and report['work_errors'] == [u'中文任务失败'] and session.error_count == 0)
    report['work_errors'].append('mutated')
    check('work error history is copied', len(channel.transport.work_errors) == 1)
    check('later work survives failure', session.tick(1) == 1 and observed == [2, 'tail'])
    for number in range(40): context.enqueueWork(fail)
    session.tick(40)
    check('failure count cumulative and diagnostic history bounded', channel.transport.work_failures == 41
          and len(channel.transport.work_errors) == 32)
    class BrokenError(Exception):
        def __str__(self): raise ValueError('broken str')
        def __unicode__(self): raise ValueError('broken unicode')
        def __repr__(self): raise ValueError('broken repr')
    session._error('stability', BrokenError())
    check('broken exception formatting has fallback', session.errors[-1]['error'] == u'<unprintable exception>')
    sdk.fail = True
    caught = False
    try: session.close()
    except load('java_stdlib._base').IllegalStateException as error:
        caught = u'中文卸载失败' in load('neoforge.network')._error_text(error)
    check('Unicode cleanup failure retains original diagnostic', caught)
    check('cleanup continues after failed unlisten', not sdk.listeners and session.closed and channel.closed)
    session.close()
    check('cleanup retry completes', not session._listeners and not session.channels)

    access = load('minecraft.level_access').InMemoryLevelAccess
    level_type = load('minecraft.level').ServerLevel
    entity_module = load('minecraft.entity')
    old_access, new_access = access(), access()
    old_level = level_type(old_access)
    entity = entity_module.Entity(entity_module.EntityType.of('stability:entity'), old_level)
    check('constructor level identity retained', entity.level() is old_level)
    entity.setLevelAccess(old_access)
    check('same access keeps original wrapper', entity.level() is old_level)
    reference = weakref.ref(old_level)
    entity.setLevelAccess(new_access)
    check('rebind uses current world and drops old wrapper', entity._level_wrapper is None
          and entity.level().getAccess() is new_access)
    del old_level
    gc.collect()
    check('old Level wrapper can be collected after rebind', reference() is None)
    entity.setLevelAccess(None)
    check('detach retains no level wrapper', entity._level_wrapper is None)
    return checks
