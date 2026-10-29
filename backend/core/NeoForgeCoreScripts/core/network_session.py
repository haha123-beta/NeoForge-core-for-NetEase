# -*- coding: utf-8 -*-
"""Owned ModSDK payload channels, original PacketDistributor routing and teardown.

Native ingress alone reads the SDK-injected __id__. Direct transport.receive still
requires an independent identity. This is tagged NeoCore data, not Netty framing.
Tick/disconnect listeners are private to this session and removed individually.
"""
from __future__ import absolute_import
from java_stdlib._base import IllegalArgumentException, IllegalStateException
from neoforge.network import PacketFlow, PACKET_DISTRIBUTOR, _error_text
from core.modsdk_network import ModSdkPayloadTransport


def native_player_recipients(mode, targets):
    if mode != 'player':
        raise IllegalStateException("Dimension/tracking selection requires an explicit adapter")
    players = []
    for target in targets:
        if isinstance(target, (str, type(u''))):
            player = target
        else:
            # Entity.getId is a local Java-compatible integer, not an SDK player ID.
            access = target.getLevelAccess()
            resolver = getattr(access, 'getEngineId', None)
            player = resolver(target) if callable(resolver) else None
        if not isinstance(player, (str, type(u''))) or not player:
            raise IllegalArgumentException("Player has no native engine binding")
        players.append(player)
    return players


class PayloadConnection(object):
    """NeoCore lifecycle handle, deliberately not a Java Connection substitute."""
    def __init__(self, channel, player_id):
        self.channel = channel
        self.player_id = player_id
        self.active = True

    def close(self):
        if self.active:
            self.active = False
            self.channel.transport.disconnect(self)
            self.channel = None


class _Channel(object):
    def __init__(self, session, owner, registry, channel, version, recipients, player_resolver):
        self.session, self.owner = session, owner
        self.channel, self.registry = channel, registry
        self.transport = ModSdkPayloadTransport(session.system, registry, session.side,
            channel, version, recipients)
        self.player_resolver = player_resolver
        self.connections = {}
        self.closed = False
        self.listener = None
        self.rejected = 0
        self.disconnected = set()

    def receive_native(self, args):
        if self.closed or self.session.closed:
            return False
        try:
            if not isinstance(args, dict):
                raise IllegalArgumentException("Payload event must be a dictionary")
            data = dict(args)
            # SDK ListenForEvent documentation guarantees the injected field only
            # for this server callback, never for arbitrary receive() callers.
            player_id = data.pop('__id__', None)
            if self.session.side == 'server':
                if not isinstance(player_id, (str, type(u''))) or not player_id:
                    raise IllegalArgumentException("Native payload has no SDK sender identity")
                if player_id in self.disconnected:
                    raise IllegalStateException("Payload sender has disconnected")
            else:
                player_id = None
            if 'payload_version' not in data:
                raise IllegalArgumentException("Native payload registration version required")
            connection = self.connections.get(player_id)
            if connection is None:
                if len(self.connections) >= self.session.max_connections:
                    raise IllegalStateException("Payload connection limit exceeded")
                connection = PayloadConnection(self, player_id)
                self.connections[player_id] = connection
            if not connection.active:
                raise IllegalStateException("Payload connection is closed")
            player = (self.player_resolver(player_id) if self.player_resolver is not None
                      else player_id)
            if self.session.side == 'server' and player is None:
                raise IllegalStateException("Payload sender could not be resolved")
            return self.transport.receive(data, player, connection)
        except Exception as error:
            self.rejected += 1
            self.session._error(self.owner, error)
            return False

    def disconnect(self, player_id):
        self.disconnected.add(player_id)
        connection = self.connections.pop(player_id, None)
        if connection is not None:
            connection.close()

    def close(self):
        if not self.closed:
            self.closed = True
            for connection in list(self.connections.values()):
                connection.close()
            self.connections.clear()
            self.disconnected.clear()
            self.transport.close()
        # Keep failed unlisten handles for a subsequent close() retry.
        if self.listener is not None:
            self.session._unlisten(self.listener)
            self.listener = None
        self.session._remove(self)


class ModSdkNetworkSession(object):
    """One SDK system owns routes for several independent content mods.

    Uses NeoCore/Loader on both sides. A sender namespace is not a secret.
    SDK injects identity; per-packet authorization remains the mod's job.
    Recipient selection is explicit for dimensions/entity tracking; no guessing.
    """
    def __init__(self, system, api, side, peer=('NeoCore', 'Loader'),
                 distributor=None, max_work=128, max_connections=1024):
        if side not in ('server', 'client') or int(max_work) <= 0 or int(max_connections) <= 0:
            raise IllegalArgumentException("Valid side and positive network limits required")
        self.system, self.api, self.side = system, api, side
        self.peer = tuple(peer)
        if len(self.peer) != 2 or not all(self.peer):
            raise IllegalArgumentException("Peer namespace/system required")
        self.max_work, self.max_connections = int(max_work), int(max_connections)
        self.distributor = distributor if distributor is not None else PACKET_DISTRIBUTOR
        self.channels, self.routes = {}, {}
        self._listeners = []
        self.errors = []
        self.error_count = 0
        self.closed = False
        self._attached = False
        self._last_owner = None
        self._ticking = False

    def _error(self, owner, error):
        self.error_count += 1
        self.errors.append({'owner': owner, 'error': _error_text(error)})
        if len(self.errors) > 32:
            del self.errors[0]

    def _listen(self, namespace, system, event, callback, instance=None):
        row = (namespace, system, event, self if instance is None else instance, callback)
        self.system.ListenForEvent(*row)
        self._listeners.append(row)
        return row

    def _unlisten(self, row):
        if row not in self._listeners:
            return
        self.system.UnListenForEvent(*row)
        if row in self._listeners:
            self._listeners.remove(row)

    def _attach(self):
        if self._attached:
            return
        self.distributor.setTransport(self)
        self._attached = True
        namespace, system = self.api.GetEngineNamespace(), self.api.GetEngineSystemName()
        self._listen(namespace, system,
            'OnScriptTickServer' if self.side == 'server' else 'OnScriptTickClient', self._on_tick)
        if self.side == 'server':
            self._listen(namespace, system, 'DelServerPlayerEvent', self._on_leave)
            self._listen(namespace, system, 'AddServerPlayerEvent', self._on_join)

    def open_channel(self, owner, registry, version='1', channel=None,
                     recipients=None, player_resolver=None):
        if self.closed:
            raise IllegalStateException("Network session is closed")
        channel = channel if channel is not None else 'NeoCorePayload_' + owner
        if not owner or owner in self.channels or not channel:
            raise IllegalArgumentException("Unique network owner and channel required")
        if any(c.channel == channel for c in self.channels.values()):
            raise IllegalArgumentException("Network channel is already owned")
        types = registry.types()
        if not types or any(name in self.routes for name in types):
            raise IllegalArgumentException("Payload types must be nonempty and uniquely owned")
        value = _Channel(self, owner, registry, channel, version, recipients, player_resolver)
        before = list(self._listeners)
        was_attached = self._attached
        try:
            self._attach()
            value.listener = self._listen(self.peer[0], self.peer[1], channel, value.receive_native, value)
            self.channels[owner] = value
            for name in types:
                self.routes[name] = value
            registry.freeze()
            return value
        except Exception:
            value.transport.close()
            for row in reversed(list(self._listeners)):
                if row not in before:
                    try:
                        self._unlisten(row)
                    except Exception as error:
                        self._error(owner, error)
            if not was_attached and self.distributor._transport is self:
                self.distributor.setTransport(None)
                self._attached = False
            raise

    def _remove(self, channel):
        if self.channels.get(channel.owner) is channel:
            del self.channels[channel.owner]
        for name in list(self.routes):
            if self.routes[name] is channel:
                del self.routes[name]

    def send(self, targets, payload, description):
        if self.closed:
            raise IllegalStateException("Network session is closed")
        channel = self.routes.get(payload.type().id().toString())
        if channel is None or channel.closed:
            raise IllegalStateException("Payload has no live content owner")
        channel.transport.send(targets, payload, description)

    def tick(self, max_work=None):
        if self.closed:
            return 0
        if self._ticking:
            raise IllegalStateException("Network tick is not reentrant")
        budget = self.max_work if max_work is None else int(max_work)
        if budget <= 0:
            raise IllegalArgumentException("Positive network work budget required")
        self._ticking = True
        done = 0
        try:
            while budget > 0 and not self.closed:
                channels = [self.channels[name] for name in sorted(self.channels)
                            if not self.channels[name].closed and self.channels[name].transport._pending]
                if not channels:
                    break
                # The active subset changes as queues empty/refill. An index
                # into that subset can repeatedly jump back before a waiting
                # owner. Advance by stable owner identity, including across
                # frames and removal of the previously served channel.
                channel = channels[0]
                for candidate in channels:
                    if self._last_owner is None or candidate.owner > self._last_owner:
                        channel = candidate
                        break
                self._last_owner = channel.owner
                # Charge attempts, including failed tasks, against the frame budget.
                done += channel.transport.tick(1)
                budget -= 1
            return done
        finally:
            self._ticking = False

    def _on_tick(self, args=None):
        self.tick()

    def _on_leave(self, args):
        if self.closed or not isinstance(args, dict):
            return
        player_id = args.get('id')
        if isinstance(player_id, (str, type(u''))) and player_id:
            for channel in list(self.channels.values()):
                channel.disconnect(player_id)

    def _on_join(self, args):
        if not self.closed and isinstance(args, dict):
            for channel in list(self.channels.values()):
                channel.disconnected.discard(args.get('id'))

    def report(self):
        return {'state': 'closed' if self.closed else 'active',
            'error_count': self.error_count, 'errors': list(self.errors),
            'listeners': len(self._listeners),
            'channels': dict((owner, {'channel': value.channel,
                'payload_types': value.registry.types(), 'submitted': value.transport.submitted,
                'received': value.transport.received, 'rejected': value.rejected,
                'connections': len(value.connections),
                'work_failures': value.transport.work_failures,
                'work_errors': list(value.transport.work_errors),
                # Include the active context's queued tail, not the running task.
                'pending': sum(c.pending() for c in value.transport._pending) +
                    (value.transport._active_context.pending()
                     if value.transport._active_context is not None else 0)})
                for owner, value in self.channels.items())}

    def close(self):
        self.closed = True
        failures = []
        for channel in list(self.channels.values()):
            try:
                channel.close()
            except Exception as error:
                failures.append(_error_text(error))
        for row in reversed(list(self._listeners)):
            try:
                self._unlisten(row)
            except Exception as error:
                failures.append(_error_text(error))
        if self.distributor._transport is self:
            self.distributor.setTransport(None)
        self._attached = False
        if failures:
            raise IllegalStateException(u'; '.join(failures))
