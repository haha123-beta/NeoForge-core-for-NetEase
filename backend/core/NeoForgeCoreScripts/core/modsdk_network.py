# -*- coding: utf-8 -*-
"""ModSDK event transport for registered payloads; explicit per-content ownership.

Uses documented NotifyToServer, NotifyToClient, BroadcastToAllClient.
Envelope is NeoCore tagged data, NOT Java/Netty binary protocol compatibility.
Server receive requires an independently authenticated player; body fields never
identify the sender. Listener binding/authentication remain caller responsibilities.
"""
from __future__ import absolute_import
import json
import weakref
from java_stdlib._base import IllegalArgumentException, IllegalStateException
from neoforge.network import PacketFlow, FriendlyByteBuf, IPayloadContext, _error_text


class ModSdkPayloadTransport(object):
    def __init__(self, system, registry, side, channel, version, recipients=None, max_bytes=65536):
        if side not in ("client", "server") or not channel or not version:
            raise IllegalArgumentException("Explicit network side/channel/version required")
        if int(max_bytes) <= 0:
            raise IllegalArgumentException("Positive envelope limit required")
        self.system, self.registry = system, registry
        self.side, self.channel, self.version = side, channel, version
        self.recipients = recipients
        self.max_bytes = int(max_bytes)
        self._closed = False
        self._distributor = None
        self.submitted = 0
        self.received = 0
        self.work_failures = 0
        self.work_errors = []
        self._pending = []
        self._active_context = None
        self.max_pending = 128
        self._contexts = weakref.WeakSet()

    def attach(self, distributor):
        if self._closed or self._distributor is not None:
            raise IllegalStateException("Transport closed or already attached")
        distributor.setTransport(self)
        self._distributor = distributor
        return self

    def _check(self):
        if self._closed:
            raise IllegalStateException("Network transport is closed")

    def _copy(self, data):
        # Reject non-JSON objects instead of inventing encodings for NBT/BlockPos.
        try:
            text = json.dumps(data, ensure_ascii=True, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise IllegalArgumentException("Unsupported network value: " + str(error))
        if len(text.encode("utf-8")) > self.max_bytes:
            raise IllegalArgumentException("Network envelope exceeds configured limit")
        return json.loads(text)

    def send(self, targets, payload, description):
        self._check()
        flow = PacketFlow.SERVERBOUND if self.side == "client" else PacketFlow.CLIENTBOUND
        record = self.registry.get(payload.type(), flow)
        if record is None or record.flow is not flow or record.codec is None:
            raise IllegalStateException("Unregistered, wrong-direction or unencoded payload")
        if self.side == "server" and description == "server":
            raise IllegalStateException("Server transport cannot send a serverbound payload")
        if self.side == "client" and description != "server":
            raise IllegalStateException("Client transport can only send to server")
        data = self._copy({"protocol": 1, "channel": self.channel, "version": self.version,
                           "type": payload.type().id().toString(),
                           "payload_version": record.version,
                           "data": self.registry.encode(payload, flow).toList()})
        if self.side == "client":
            self.system.NotifyToServer(self.channel, data)
        elif description == "all":
            self.system.BroadcastToAllClient(self.channel, data)
        else:
            if self.recipients is None:
                raise IllegalStateException("Native player/dimension/tracking recipient resolver required")
            players = list(self.recipients(description, targets))
            if any(not isinstance(player, (str, type(u""))) or not player for player in players):
                raise IllegalArgumentException("Recipient resolver must return native player IDs")
            unique = []
            for player in players:
                if player not in unique:
                    unique.append(player)
            for player in unique:
                # Documented calls return no delivery acknowledgement.
                self.system.NotifyToClient(player, self.channel, self._copy(data))
        self.submitted += 1

    def receive(self, event_data, authenticated_player=None, connection=None):
        self._check()
        data = self._copy(event_data)
        if (not isinstance(data, dict) or data.get("protocol") != 1
                or data.get("channel") != self.channel or data.get("version") != self.version):
            raise IllegalArgumentException("Network envelope protocol/channel/version mismatch")
        if self.side == "server" and authenticated_player is None:
            raise IllegalStateException("Server payload requires an independently authenticated player")
        flow = PacketFlow.CLIENTBOUND if self.side == "client" else PacketFlow.SERVERBOUND
        record = self.registry.get(data.get("type"), flow)
        if record is None or record.flow is not flow or record.codec is None:
            raise IllegalStateException("Incoming payload is unregistered or wrong-direction")
        if data.get("payload_version", record.version) != record.version:
            raise IllegalArgumentException("Payload registration version mismatch")
        entries = data.get("data")
        if not isinstance(entries, list) or any(not isinstance(entry, list) or len(entry) != 2 for entry in entries):
            raise IllegalArgumentException("Malformed tagged payload buffer")
        buffer = FriendlyByteBuf(entries)
        payload = self.registry.decode(data["type"], buffer, flow)
        if buffer.readableBytes() or payload.type().id().toString() != data["type"]:
            raise IllegalArgumentException("Payload codec left trailing data or changed type")
        if len(self._pending) + (1 if self._active_context is not None else 0) >= self.max_pending:
            raise IllegalStateException("Network work queue is full")
        context = IPayloadContext(flow, authenticated_player, connection)
        context._work_owner = weakref.ref(self)
        self._contexts.add(context)
        try:
            record.handler(payload, context)
        except Exception:
            context.close()
            raise
        if self._closed:
            context.close()
        self.received += 1
        return True

    def _enqueue_context(self, context, work):
        self._check()
        waiting = context in self._pending
        active = context is self._active_context
        occupied = len(self._pending) + (1 if self._active_context is not None else 0)
        if not waiting and not active and occupied >= self.max_pending:
            raise IllegalStateException("Network work queue is full")
        # Check capacity before retaining the callable. A rejected enqueue can be
        # retried without leaving an unscheduled or duplicated task behind.
        context._queue.append(work)
        if not waiting and not active:
            self._pending.append(context)

    def _forget_context(self, context):
        if context in self._pending:
            self._pending.remove(context)
        self._contexts.discard(context)

    def _work_failed(self, error):
        self.work_failures += 1
        self.work_errors.append(_error_text(error))
        if len(self.work_errors) > 32:
            del self.work_errors[0]

    def tick(self, max_work=128):
        """Call from the SDK main-thread tick; receive never runs queued world work."""
        self._check()
        if int(max_work) <= 0:
            raise IllegalArgumentException("Positive network tick work limit required")
        remaining, done = int(max_work), 0
        while self._pending and remaining > 0 and not self._closed:
            context = self._pending.pop(0)
            if context.pending():
                self._active_context = context
                try:
                    done += context.drainWork(1)
                finally:
                    self._active_context = None
                remaining -= 1
            if context.pending() and not self._closed:
                self._pending.append(context)
        return done

    def disconnect(self, connection):
        contexts = list(self._contexts) + list(self._pending)
        if self._active_context is not None:
            contexts.append(self._active_context)
        for context in contexts:
            if context.connection() is connection:
                context.close()
                self._forget_context(context)

    def close(self):
        self._closed = True
        contexts = list(self._contexts) + list(self._pending)
        if self._active_context is not None:
            contexts.append(self._active_context)
        for context in contexts:
            context.close()
        self._pending = []
        self._contexts.clear()
        if self._distributor is not None and self._distributor._transport is self:
            self._distributor.setTransport(None)
        self._distributor = None
        self.system = None
        self.recipients = None
