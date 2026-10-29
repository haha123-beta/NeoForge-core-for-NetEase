# -*- coding: utf-8 -*-
"""Shared high-level contracts, run with harness AND unmodified CPython 2.7."""
from __future__ import print_function


def run(load):
    n = load('neoforge.network')
    r = load('neoforge.registries')
    m = load('core.network_session')
    checks = []

    def check(name, condition):
        assert condition, name
        checks.append(name)

    def rejects(fn):
        try:
            fn()
        except Exception:
            return True
        return False

    class Packet(n.CustomPacketPayload):
        TYPE = n.CustomPacketPayload_Type(r.ResourceLocation('network:test'))
        def __init__(self, value): self.value = value
    codec = n.StreamCodec.of(lambda b, p: b.writeInt(p.value), lambda b: Packet(b.readInt()))
    check('empty registration version rejected', rejects(lambda: n.PayloadRegistrar('')))
    history = n.PacketDistributor()
    for number in range(150): history.sendToServer(Packet(number))
    check('packet diagnostic history is bounded', len(history.sent) == 128 and history.sent[-1][1].value == 149)
    class BoundPlayer(object):
        def getLevelAccess(self): return self
        def getEngineId(self, entity): return 'engine-player'
        def getId(self): return 17
    check('bound recipients use native identity instead of local entity ID',
        m.native_player_recipients('player', [BoundPlayer(), 'native']) == ['engine-player', 'native'])
    check('unreviewed tracking resolver fails explicitly', rejects(lambda:
        m.native_player_recipients('tracking', [BoundPlayer()])))

    class Api(object):
        def GetEngineNamespace(self): return 'Minecraft'
        def GetEngineSystemName(self): return 'Engine'
    class System(object):
        def __init__(self):
            self.listeners, self.sent = [], []
            self.fail_event = None
            self.fail_unlisten = False
            self.remote = None
        def ListenForEvent(self, *row):
            assert getattr(row[4], '__self__', row[3]) is row[3], 'SDK callback owner mismatch'
            if row[2] == self.fail_event: raise RuntimeError('listen failed')
            self.listeners.append(row)
        def UnListenForEvent(self, *row):
            if self.fail_unlisten:
                self.fail_unlisten = False
                raise RuntimeError('unlisten failed')
            self.listeners.remove(row)
        def NotifyToServer(self, name, data):
            self.sent.append(('server', name, data))
            if self.remote:
                data = dict(data); data['__id__'] = 'trusted-player'
                self.remote.emit('NeoCore', 'Loader', name, data)
        def NotifyToClient(self, player, name, data):
            self.sent.append((player, name, data))
            if self.remote: self.remote.emit('NeoCore', 'Loader', name, dict(data))
        def BroadcastToAllClient(self, name, data): self.NotifyToClient('*', name, data)
        def emit(self, ns, system, event, args=None):
            for row in list(self.listeners):
                if row[:3] == (ns, system, event): row[4](args)

    server_sdk, client_sdk = System(), System()
    server_sdk.remote, client_sdk.remote = client_sdk, server_sdk
    server_dist, client_dist = n.PacketDistributor(), n.PacketDistributor()
    server = m.ModSdkNetworkSession(server_sdk, Api(), 'server', distributor=server_dist)
    client = m.ModSdkNetworkSession(client_sdk, Api(), 'client', distributor=client_dist)
    server_reg, client_reg = n.PayloadRegistry(), n.PayloadRegistry()
    handled, replies, contexts = [], [], []
    def handle_server(packet, ctx):
        contexts.append(ctx)
        def execute():
            handled.append((packet.value, ctx.player()))
            server_dist.sendToPlayer(ctx.player(), Packet(packet.value + 1))
        ctx.enqueueWork(execute)
    def handle_client(packet, ctx):
        ctx.enqueueWork(lambda: replies.append(packet.value))
    for registry, handler in ((server_reg, handle_server), (client_reg, handle_client)):
        registrar = n.PayloadRegistrar('45', registry)
        check('fluent registration', registrar.playBidirectional(Packet.TYPE, codec, handler) is registrar)
        check('both directions retained', all(registry.get(Packet.TYPE, f) is not None
            for f in (n.PacketFlow.SERVERBOUND, n.PacketFlow.CLIENTBOUND)))
        check('ambiguous codec requires flow', rejects(lambda: registry.get(Packet.TYPE)))
    sc = server.open_channel('network_example', server_reg,
        recipients=lambda mode, targets: targets)
    cc = client.open_channel('network_example', client_reg)
    client_dist.sendToServer(Packet(45))
    check('native receive defers world work', handled == [] and sc.transport.received == 1)
    server_sdk.emit('Minecraft', 'Engine', 'OnScriptTickServer')
    check('trusted SDK identity reaches handler', handled == [(45, 'trusted-player')])
    check('reply deferred on client', replies == [] and cc.transport.received == 1)
    client_sdk.emit('Minecraft', 'Engine', 'OnScriptTickClient')
    check('original distributor bidirectional roundtrip', replies == [46])
    check('connection lifecycle available', contexts[0].connection().active)
    event = dict(client_sdk.sent[0][2]); event['playerId'] = 'forged'
    check('body cannot identify sender', sc.receive_native(event) is False)
    event['__id__'] = 'trusted-player'
    event['payload_version'] = 'wrong'
    check('registration version enforced', sc.receive_native(event) is False)
    event['payload_version'] = '45'
    event['data'] = [['int', 1], ['int', 2]]
    check('trailing data blocked', sc.receive_native(event) is False)
    event['data'] = [['int', 7]]
    check('forged body ignored with trusted identity', sc.receive_native(event))
    server_sdk.emit('Minecraft', 'Engine', 'DelServerPlayerEvent', {'id': 'trusted-player'})
    server.tick()
    check('disconnect cancels pending work', handled == [(45, 'trusted-player')])
    check('disconnect closes captured context', rejects(lambda: contexts[-1].enqueueWork(lambda: None)))
    check('late packet from disconnected player blocked', not sc.receive_native(event))
    server_sdk.emit('Minecraft', 'Engine', 'AddServerPlayerEvent', {'id': 'trusted-player'})
    check('rejoin gets fresh connection', sc.receive_native(event))
    server.tick(); client.tick()
    check('rejoin request works', handled[-1] == (7, 'trusted-player') and replies[-1] == 8)
    check('frozen registrations reject late mutation', rejects(lambda:
        n.PayloadRegistrar('45', server_reg).playToServer(Packet.TYPE, codec, handle_server)))
    optional = n.PayloadRegistrar('base', n.PayloadRegistry())
    copy = optional.optional().versioned('other')
    check('registrar copy settings isolated', optional.version == 'base' and not optional._optional
          and copy.version == 'other' and copy._optional)
    count = len(server_sdk.listeners)
    check('type ownership conflict rejected', rejects(lambda: server.open_channel('other', client_reg)))
    check('conflict leaves existing channel intact', len(server_sdk.listeners) == count and len(server.channels) == 1)
    # Reject duplicate registration across separate registrar instances atomically.
    reg = n.PayloadRegistry()
    n.PayloadRegistrar('1', reg).playToClient(Packet.TYPE, codec, handle_client)
    second = n.PayloadRegistrar('1', reg)
    check('bidirectional duplicate transaction rejected', rejects(lambda:
        second.playBidirectional(Packet.TYPE, codec, handle_server)))
    check('failed transaction publishes neither half', reg.get(Packet.TYPE, n.PacketFlow.SERVERBOUND) is None
          and second.getRegistrations() == [])
    # Callback failures are charged to the budget and cannot starve other packets.
    order = []
    def fail():
        order.append('failed')
        raise ValueError('expected work failure')
    pending = []
    for name in ('first', 'second'):
        ctx = n.IPayloadContext(n.PacketFlow.SERVERBOUND, name)
        ctx.enqueueWork(fail if name == 'first' else lambda: order.append('second'))
        ctx.enqueueWork(lambda: order.append('tail'))
        pending.append(ctx)
    sc.transport._pending.extend(pending)
    check('failed work respects frame budget', server.tick(1) == 0 and order == ['failed'])
    server.tick(1)
    check('work rotates between contexts', order == ['failed', 'second'])
    server_dist.sendToAllPlayers(Packet(4))
    check('broadcast reaches native API', server_sdk.sent[-1][0] == '*')
    server.tick(); client.tick()
    class OtherPacket(Packet):
        TYPE = n.CustomPacketPayload_Type(r.ResourceLocation('network:other'))
    other_codec = n.StreamCodec.of(lambda b, p: b.writeInt(p.value), lambda b: OtherPacket(b.readInt()))
    other_registry, other_client_registry = n.PayloadRegistry(), n.PayloadRegistry()
    n.PayloadRegistrar('45', other_registry).playToServer(OtherPacket.TYPE, other_codec,
        lambda p, ctx: ctx.enqueueWork(lambda: order.append('other')))
    n.PayloadRegistrar('45', other_client_registry).playToServer(OtherPacket.TYPE, other_codec, lambda p, ctx: None)
    other_server = server.open_channel('other_owner', other_registry)
    other_client = client.open_channel('other_owner', other_client_registry)
    client_dist.sendToServer(OtherPacket(1))
    client_dist.sendToServer(Packet(9))
    check('multiple owners have independent routes', other_server.transport.received == 1
          and other_client.transport.submitted == 1 and sc.transport.received >= 4)
    baseline = len(order) + len(handled)
    server.tick(1)
    check('one shared frame budget across owners', len(order) + len(handled) == baseline + 1)
    server.tick(1); client.tick()
    check('other content cannot be starved', order[-1] == 'other' and handled[-1] == (9, 'trusted-player'))
    other_server.close(); other_client.close()
    check('closing one owner preserves other listeners', 'network_example' in server.channels
          and 'other_owner' not in server.channels and len(server_sdk.listeners) == count)
    check('closed route cannot be reused', rejects(lambda: client_dist.sendToServer(OtherPacket(2))))
    connection = m.PayloadConnection(sc, 'closing-during-work')
    active = n.IPayloadContext(n.PacketFlow.SERVERBOUND, 'closing-during-work', connection)
    active.enqueueWork(connection.close)
    active.enqueueWork(lambda: order.append('must not run after disconnect'))
    sc.transport._pending.append(active)
    server.tick()
    check('disconnect during executing callback cancels remaining work',
          not active.pending() and 'must not run after disconnect' not in order)
    bad = System(); bad.fail_event = 'NeoCorePayload_test'
    dist = n.PacketDistributor()
    session = m.ModSdkNetworkSession(bad, Api(), 'server', distributor=dist)
    check('listener installation failure propagates', rejects(lambda:
        session.open_channel('test', client_reg)))
    check('listener rollback releases ownership', not bad.listeners and dist._transport is None and not session.channels)
    session.close()
    pending[-1].enqueueWork(lambda: order.append('must not run'))
    sc.transport._pending.append(pending[-1])
    server_sdk.fail_unlisten = True
    check('unlisten failure reported', rejects(server.close))
    server.close(); client.close()
    check('all native listeners removed', server_sdk.listeners == client_sdk.listeners == [])
    check('all router ownership released', server_dist._transport is client_dist._transport is None)
    check('closed contexts reject late enqueue', rejects(lambda: pending[-1].enqueueWork(lambda: None)))
    check('closed channels reject stale callbacks', not sc.receive_native(event))
    check('errors observable and bounded', server.report()['error_count'] >= 4 and len(server.report()['errors']) <= 32)
    server.close(); client.close()
    return checks
