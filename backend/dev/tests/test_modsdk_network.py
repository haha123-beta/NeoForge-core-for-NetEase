# -*- coding: utf-8 -*-
import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
pkg = Package()
n = pkg.load("neoforge.network")
r = pkg.load("neoforge.registries")
m = pkg.load("core.modsdk_network")


class Payload(object):
    TYPE = n.CustomPacketPayload_Type(r.ResourceLocation("test:packet"))
    def __init__(self, value): self.value = value
    def type(self): return self.TYPE


class System(object):
    def __init__(self): self.calls = []
    def NotifyToServer(self, name, data): self.calls.append(("server", name, data))
    def NotifyToClient(self, player, name, data): self.calls.append((player, name, data))
    def BroadcastToAllClient(self, name, data): self.calls.append(("all", name, data))


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.registry = n.PayloadRegistry()
        self.handled = []
        self.registrar = n.PayloadRegistrar("1", self.registry)
        self.codec = n.StreamCodec.of(lambda b, p: b.writeInt(p.value), lambda b: Payload(b.readInt()))
        self.registrar.playToServer(Payload.TYPE, self.codec, lambda p, c: self.handled.append((p.value, c.player())))
        self.sdk = System()
        self.client = m.ModSdkPayloadTransport(self.sdk, self.registry, "client", "test-channel", "1")
        self.server = m.ModSdkPayloadTransport(self.sdk, self.registry, "server", "test-channel", "1")
        self.distributor = n.PacketDistributor()
        self.client.attach(self.distributor)
    def envelope(self):
        self.distributor.sendToServer(Payload(12))
        return self.sdk.calls[-1][2]
    def test_client_server_roundtrip(self):
        data = self.envelope()
        self.assertEqual(self.sdk.calls[0][:2], ("server", "test-channel"))
        self.assertTrue(self.server.receive(data, "authenticated-player"))
        self.assertEqual(self.handled, [(12, "authenticated-player")])
        self.assertEqual((self.client.submitted, self.server.received), (1, 1))
    def test_sender_body_is_not_authentication(self):
        data = self.envelope(); data["playerId"] = "forged"
        with self.assertRaises(Exception): self.server.receive(data)
        self.assertFalse(self.handled)
        self.server.receive(data, "trusted")
        self.assertEqual(self.handled[-1][1], "trusted")
    def test_version_type_direction_and_trailing(self):
        data = self.envelope()
        for key, value in (("version", "wrong"), ("type", "test:unknown"), ("channel", "other"), ("data", [["int", 1], ["int", 2]])):
            bad = dict(data); bad[key] = value
            with self.assertRaises(Exception): self.server.receive(bad, "trusted")
        with self.assertRaises(Exception): self.client.receive(data)
        self.assertFalse(self.handled)
    def test_size_and_unsupported_values(self):
        self.client.max_bytes = 10
        with self.assertRaises(Exception): self.distributor.sendToServer(Payload(12))
        self.assertFalse(self.sdk.calls)
        with self.assertRaises(Exception): self.server.receive({"bad": object()}, "trusted")
    def test_close_releases_own_distributor(self):
        self.client.close()
        self.assertIsNone(self.distributor._transport)
        with self.assertRaises(Exception): self.client.send([], Payload(1), "server")
        other = n.PacketDistributor(); replacement = m.ModSdkPayloadTransport(self.sdk, self.registry, "client", "test-channel", "1")
        replacement.attach(other)
        self.client.close()
        self.assertIs(other._transport, replacement)
    def test_ownership_conflict(self):
        other = m.ModSdkPayloadTransport(self.sdk, self.registry, "client", "other", "1")
        with self.assertRaises(Exception): other.attach(self.distributor)
        self.assertIs(self.distributor._transport, self.client)
    def test_server_broadcast_target_modes_and_dedup(self):
        registry = n.PayloadRegistry()
        n.PayloadRegistrar("1", registry).playToClient(Payload.TYPE, self.codec, lambda p, c: None)
        seen = []
        def resolve(mode, targets):
            seen.append((mode, targets))
            return ["p1", "p1", "p2"]
        server = m.ModSdkPayloadTransport(self.sdk, registry, "server", "channel", "1", resolve)
        distributor = n.PacketDistributor(); server.attach(distributor)
        distributor.sendToAllPlayers(Payload(2))
        self.assertEqual(self.sdk.calls[-1][0], "all")
        distributor.sendToPlayersTrackingEntityAndSelf("entity", Payload(3))
        self.assertEqual(seen[-1], ("tracking+self", ["entity"]))
        self.assertEqual([c[0] for c in self.sdk.calls[-2:]], ["p1", "p2"])
        distributor.sendToPlayersTrackingEntity("entity", Payload(4))
        self.assertEqual(seen[-1][0], "tracking")
        with self.assertRaises(Exception): distributor.sendToServer(Payload(1))
    def test_queued_work_tick_limit_and_close(self):
        queued = []
        def handler(payload, context):
            context.enqueueWork(lambda: queued.append(payload.value))
        self.registry.get(Payload.TYPE).handler = handler
        data = self.envelope()
        self.server.receive(data, "trusted")
        self.server.receive(data, "trusted")
        self.assertEqual(queued, [])
        self.assertEqual(self.server.tick(1), 1)
        self.assertEqual(queued, [12])
        self.server.close()
        self.assertEqual(self.server._pending, [])
        self.assertEqual(queued, [12])
    def test_queue_backpressure(self):
        self.registry.get(Payload.TYPE).handler = lambda p, c: c.enqueueWork(lambda: None)
        self.server.max_pending = 1
        data = self.envelope()
        self.server.receive(data, "trusted")
        with self.assertRaises(Exception): self.server.receive(data, "trusted")
        self.assertEqual(self.server.tick(), 1)
        self.assertTrue(self.server.receive(data, "trusted"))
    def test_native_failure_not_counted_as_submission(self):
        def fail(name, data): raise RuntimeError("SDK failure")
        self.sdk.NotifyToServer = fail
        with self.assertRaises(RuntimeError): self.distributor.sendToServer(Payload(1))
        self.assertEqual(self.client.submitted, 0)

if __name__ == "__main__": unittest.main()
