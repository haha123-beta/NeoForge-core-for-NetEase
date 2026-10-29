# -*- coding: utf-8 -*-
"""Dynamic network queues must get turns across frame and membership changes."""
from __future__ import print_function


def setup(load, max_work=128):
    n = load('neoforge.network')
    m = load('core.network_session')
    class Api(object):
        def GetEngineNamespace(self): return 'Minecraft'
        def GetEngineSystemName(self): return 'Engine'
    class System(object):
        def __init__(self): self.listeners = []
        def ListenForEvent(self, *row): self.listeners.append(row)
        def UnListenForEvent(self, *row): self.listeners.remove(row)
    system = System()
    session = m.ModSdkNetworkSession(system, Api(), 'server',
        distributor=n.PacketDistributor(), max_work=max_work)
    def channel(name):
        registry = n.PayloadRegistry()
        payload_type = n.CustomPacketPayload.make_type('fairness', name)
        n.PayloadRegistrar('46', registry).playToServer(payload_type, n.StreamCodec.unit(None), lambda p, c: None)
        value = session.open_channel(name, registry)
        context = n.IPayloadContext(n.PacketFlow.SERVERBOUND)
        value.transport._pending.append(context)
        return value, context
    return session, system, channel


def replenishing_trace(load, budget=90, split=False):
    session, system, channel = setup(load)
    unused, a = channel('a')
    unused, b = channel('b')
    unused, c = channel('c')
    trace = []
    def work_b(): trace.append('b')
    def work_a():
        trace.append('a')
        a.enqueueWork(work_a)
        if not b.pending():
            b.enqueueWork(work_b)
            # A completed standalone context needs explicit scheduling. This
            # models a new packet arrival on B, not a late-enqueue API guarantee.
            transport = session.channels['b'].transport
            if b not in transport._pending: transport._pending.append(b)
    def work_c():
        trace.append('c')
        c.enqueueWork(work_c)
    a.enqueueWork(work_a); b.enqueueWork(work_b); c.enqueueWork(work_c)
    if split:
        done = sum(session.tick(1) for unused in range(budget))
    else:
        done = session.tick(budget)
    counts = dict((name, trace.count(name)) for name in ('a', 'b', 'c'))
    session.close()
    assert not system.listeners
    return {'counts': counts, 'trace': trace, 'done': done}


def run(load):
    results = {}
    for split in (False, True):
        result = replenishing_trace(load, split=split)
        assert result['counts'] == {'a': 30, 'b': 30, 'c': 30}, repr(result)
        assert result['trace'] == ['a', 'b', 'c'] * 30 and result['done'] == 90, repr(result)
        results['replenishing_split' if split else 'replenishing_frame'] = result['counts']
    session, system, channel = setup(load, max_work=3)
    unused, a = channel('a')
    b_channel, b = channel('b')
    unused, c = channel('c')
    trace = []
    def repeat(name, context):
        def work():
            trace.append(name)
            context.enqueueWork(work)
        return work
    b_channel.transport._pending = []
    a.enqueueWork(repeat('a', a)); c.enqueueWork(repeat('c', c))
    # B exists but has no work. Skipping it must not reset the rotation.
    assert session.tick(6) == 6 and trace == ['a', 'c'] * 3, repr(trace)
    results['idle_channel_skipped'] = list(trace)
    # Repeated 1-task frames preserve the rotation and the default frame budget.
    b.enqueueWork(repeat('b', b))
    session.channels['b'].transport._pending.append(b)
    trace[:] = []
    assert session.tick() == 3 and trace == ['a', 'b', 'c'], repr(trace)
    results['default_budget_and_reactivation'] = list(trace)
    # Removing the last-served owner must not shift the next owner's turn.
    assert session.tick(2) == 2
    b_channel.close()
    trace[:] = []
    assert session.tick(1) == 1 and trace == ['c'], repr(trace)
    results['remove_last_owner_between_frames'] = list(trace)
    # An owner inserted before the last-served one waits for wrap-around.
    unused, aa = channel('aa')
    aa.enqueueWork(repeat('aa', aa))
    trace[:] = []
    assert session.tick(3) == 3 and trace == ['a', 'aa', 'c'], repr(trace)
    results['new_owner_joins_rotation'] = list(trace)
    session.close()
    assert not system.listeners

    session, system, channel = setup(load)
    a_channel, a = channel('a')
    b_channel, b = channel('b')
    unused, c = channel('c')
    trace = []
    def remove_during_work():
        trace.append('a')
        a_channel.close()
        b_channel.close()
    a.enqueueWork(remove_during_work)
    b.enqueueWork(lambda: trace.append('must not run'))
    c.enqueueWork(lambda: trace.append('c'))
    assert session.tick(2) == 2 and trace == ['a', 'c'], repr(trace)
    results['removal_inside_callback'] = list(trace)
    session.close()
    assert not system.listeners

    session, system, channel = setup(load)
    unused, a = channel('a')
    unused, b = channel('b')
    trace = []
    def fail():
        trace.append('failed')
        raise ValueError('expected fairness failure')
    a.enqueueWork(fail)
    b.enqueueWork(lambda: trace.append('b'))
    assert session.tick(1) == 0 and trace == ['failed'], repr(trace)
    assert session.tick(1) == 1 and trace == ['failed', 'b'], repr(trace)
    results['failures_charge_budget_and_advance_turn'] = list(trace)
    session.close()
    assert not system.listeners
    return results
