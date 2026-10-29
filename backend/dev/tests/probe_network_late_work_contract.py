# -*- coding: utf-8 -*-
from __future__ import print_function
import gc
import weakref


def make(load, initial=True, connection=None, failing_handler=False):
    n = load('neoforge.network')
    m = load('core.modsdk_network')
    class Packet(n.CustomPacketPayload):
        TYPE = n.CustomPacketPayload.make_type('late_work', 'packet')
    class System(object): pass
    registry = n.PayloadRegistry()
    contexts, executed = [], []
    def handler(payload, context):
        contexts.append(context)
        if initial: context.enqueueWork(lambda: executed.append('initial'))
        if failing_handler: raise ValueError('expected handler failure')
    n.PayloadRegistrar('47', registry).playToServer(Packet.TYPE, n.StreamCodec.unit(Packet()), handler)
    transport = m.ModSdkPayloadTransport(System(), registry, 'server', 'late', '1')
    event = {'protocol': 1, 'channel': 'late', 'version': '1',
             'payload_version': '47', 'type': 'late_work:packet', 'data': []}
    return transport, event, contexts, executed


def before_trace(load):
    transport, event, contexts, executed = make(load)
    transport.receive(event, 'trusted')
    transport.tick()
    contexts[0].enqueueWork(lambda: executed.append('late'))
    done = transport.tick()
    result = {'executed': list(executed), 'late_tick_done': done,
              'context_pending': contexts[0].pending(), 'transport_pending': len(transport._pending)}
    transport.close()
    return result


def run(load):
    checks = []
    def check(name, condition):
        assert condition, name
        checks.append(name)
    def rejected(action):
        try: action()
        except Exception: return True
        return False
    result = before_trace(load)
    check('late work after drain is scheduled', result == {
        'executed': ['initial', 'late'], 'late_tick_done': 1,
        'context_pending': 0, 'transport_pending': 0})

    t, event, contexts, done = make(load, initial=False)
    t.receive(event, 'trusted')
    c = contexts[0]
    check('idle handler does not occupy pending slot', not t._pending)
    c.enqueueWork(lambda: done.append('one')); c.enqueueWork(lambda: done.append('two'))
    check('repeated enqueue creates one pending context', len(t._pending) == 1)
    check('late work obeys per-frame limit', t.tick(1) == 1 and done == ['one'] and c.pending() == 1)
    check('remaining late work survives next frame', t.tick(1) == 1 and done == ['one', 'two'])
    c.close()
    check('explicit close releases context and rejects work', not t._pending and rejected(lambda: c.enqueueWork(lambda: None)))
    t.close()

    t, event, contexts, done = make(load, initial=False)
    t.receive(event, 'trusted'); t.receive(event, 'trusted')
    a, b = contexts
    def work():
        done.append('a')
        a.enqueueWork(lambda: done.append('a-tail'))
        b.enqueueWork(lambda: done.append('b'))
    a.enqueueWork(work)
    check('enqueue during execution retains single owner', t.tick(1) == 1 and len(t._pending) == 2)
    check('woken context gets a turn before active tail', t.tick(2) == 2 and done == ['a', 'b', 'a-tail'])
    t.close()

    t, event, contexts, done = make(load)
    t.max_pending = 1
    t.receive(event, 'trusted'); t.tick()
    idle = contexts[0]
    t.receive(event, 'trusted')
    check('full queue rejects late work without retaining it',
        rejected(lambda: idle.enqueueWork(lambda: done.append('late'))) and idle.pending() == 0 and len(t._pending) == 1)
    t.tick()
    idle.enqueueWork(lambda: done.append('retry'))
    check('late work can retry after capacity frees', t.tick() == 1 and done == ['initial', 'initial', 'retry'])
    t.close()

    t, event, contexts, done = make(load, initial=False)
    t.receive(event, 'trusted'); t.receive(event, 'trusted')
    a, b = contexts
    t.max_pending = 1
    def occupy():
        done.append('active')
        a.enqueueWork(lambda: done.append('tail'))
        check('active context reserves queue capacity',
            rejected(lambda: b.enqueueWork(lambda: done.append('overflow'))) and not b.pending())
    a.enqueueWork(occupy)
    check('active tail does not overflow reserved capacity', t.tick(1) == 1 and len(t._pending) == 1)
    t.tick()
    b.enqueueWork(lambda: done.append('retry'))
    check('reserved capacity releases when active work finishes', t.tick() == 1 and done == ['active', 'tail', 'retry'])
    t.close()

    class Connection(object): active = True
    connection = Connection()
    t, event, contexts, done = make(load, initial=False)
    t.receive(event, 'trusted', connection)
    t.receive(event, 'trusted', connection)
    contexts[0].enqueueWork(lambda: done.append('cancelled'))
    t.disconnect(connection)
    check('disconnect closes idle and pending contexts', not t._pending and all(c._closed for c in contexts))
    check('disconnected context cannot wake transport', rejected(lambda: contexts[-1].enqueueWork(lambda: None)))
    t.close()

    t, event, contexts, done = make(load, initial=False)
    t.receive(event, 'trusted')
    t.close()
    check('unload invalidates even never-queued context', contexts[0]._closed and rejected(lambda: contexts[0].enqueueWork(lambda: None)))

    t, event, contexts, done = make(load, failing_handler=True)
    check('handler failure retracts registered work', rejected(lambda: t.receive(event, 'trusted'))
          and not t._pending and t.received == 0 and contexts[0]._closed)
    t.close()

    t, event, contexts, done = make(load, initial=False)
    t.receive(event, 'trusted'); c = contexts[0]
    c.enqueueWork(t.close)
    c.enqueueWork(lambda: done.append('must-not-run'))
    check('closing owner inside work cancels active tail', t.tick() == 1 and c._closed and not c.pending() and done == [])

    t, event, contexts, done = make(load, initial=False)
    t.receive(event, 'trusted')
    c = contexts[0]
    owner = weakref.ref(t)
    t = None
    gc.collect()
    check('retained idle context does not retain transport', owner() is None)
    check('collected transport rejects new work explicitly', rejected(lambda: c.enqueueWork(lambda: None)) and not c.pending())

    t, event, contexts, done = make(load, initial=False)
    t.receive(event, 'trusted')
    context_ref = weakref.ref(contexts[0])
    del contexts[:]
    gc.collect()
    check('transport does not retain idle contexts', context_ref() is None and len(t._contexts) == 0)
    t.close()

    t, event, contexts, done = make(load, initial=False)
    t.receive(event, 'trusted'); c = contexts[0]
    def fail(): raise ValueError('expected late task failure')
    c.enqueueWork(fail)
    check('late task failure consumes attempt budget', t.tick(1) == 0 and c.attempted == 1)
    c.enqueueWork(lambda: done.append('recovered'))
    check('failed task leaves context available for later work', t.tick(1) == 1 and done == ['recovered'])
    t.close()
    return checks
