# -*- coding: utf-8 -*-
"""Versioned content-pack registration owned by the independent NeoCore pack."""
from __future__ import absolute_import
import copy
from neoforge.network import _error_text


class ContentRegistry(object):
    API_VERSION = 1

    def __init__(self, session_factory):
        self._factory = session_factory
        self._packs = {}
        self._session = None
        self.state = "collecting"
        self.error = None
        self.rejected = {}
        self.cleanup_errors = []
        self.startup_error = None

    def register(self, pack_id, api_version, specs):
        if api_version != self.API_VERSION:
            raise ValueError("Unsupported NeoCore registration API: " + str(api_version))
        if self.state != "collecting":
            raise ValueError("Content registration is closed; restart with all packs enabled")
        if not pack_id or not specs:
            raise ValueError("A pack ID and at least one folder are required")
        specs = copy.deepcopy(specs)
        if pack_id in self._packs:
            if self._packs[pack_id] == specs:
                return {"accepted": True, "duplicate": True}
            raise ValueError("Conflicting content pack registration: " + pack_id)
        self._packs[pack_id] = specs
        return {"accepted": True, "duplicate": False}

    def start(self):
        if self.state != "collecting":
            return self.report()
        self.state = "starting"
        specs = []
        for pack_id in sorted(self._packs):
            specs.extend(self._packs[pack_id])
        try:
            # One session owns all roots, shared package prefixes and dependency sorting.
            if specs:
                self._session = self._factory(specs)
                activate = getattr(self._session.loader, "activate", None)
                if activate is not None:
                    activate()
                activate_native = getattr(self._session, 'activate_native', None)
                if activate_native is not None:
                    activate_native()
            self.state = "initialized"
        except Exception as error:
            self.error = _error_text(error)
            self.startup_error = _error_text(error)
            self.state = "failed"
            if self._session is not None:
                try:
                    self._session.close()
                except Exception as cleanup_error:
                    self.cleanup_errors.append(_error_text(cleanup_error))
        return self.report()

    def report(self):
        mods = {}
        if self._session is not None:
            mods = copy.deepcopy(self._session.loader.results)
        item_bindings = copy.deepcopy(getattr(self._session, 'item_binding_report', None))
        return {"api_version": self.API_VERSION, "state": self.state, 'item_bindings':item_bindings,
                'block_bindings':copy.deepcopy(getattr(self._session,'block_binding_report',None)),
                "packs": sorted(self._packs), "mods": mods, "error": self.error,
                "rejected": dict(self.rejected), "cleanup_errors": list(self.cleanup_errors),
                "startup_error": self.startup_error}

    def close(self):
        if self.state in ("closed", "close_failed"):
            return self.report()
        try:
            if self._session is not None:
                self._session.close()
                failures = []
                for mod_id, result in sorted(self._session.loader.results.items()):
                    if result.get("state") == "cleanup_failed":
                        failures.append(mod_id + ": " + result.get("message", ""))
                if failures:
                    self.error = "; ".join(failures)
                    self.state = "close_failed"
                    return self.report()
        except Exception as error:
            self.error = _error_text(error)
            self.state = "close_failed"
            return self.report()
        self.state = "closed"
        return self.report()


def install_content_system(server_api, session_factory, side="SERVER"):
    if side not in ("SERVER", "CLIENT"):
        raise ValueError("Unknown content system side")
    base = (server_api.GetServerSystemCls() if side == "SERVER"
            else server_api.GetClientSystemCls())
    loaded_event = ("LoadServerAddonScriptsAfter" if side == "SERVER"
                    else "LoadClientAddonScriptsAfter")
    class_name = ("NeoCoreLoaderSystem" if side == "SERVER"
                  else "NeoCoreClientLoaderSystem")

    class NeoCoreLoaderSystem(base):
        def __init__(self, namespace, system_name):
            base.__init__(self, namespace, system_name)
            self.registry = ContentRegistry(session_factory)
            self._namespace = server_api.GetEngineNamespace()
            self._system = server_api.GetEngineSystemName()
            self._collect_requested = False
            self._destroyed = False
            self._tick_driver = None
            self._entity_mod_bus = None
            self._entity_game_bus = None
            self._owned_runtimes = {}
            self._network_session = None
            self.ListenForEvent(self._namespace, self._system,
                                loaded_event, self, self._on_scripts_loaded)
            self._tick_event = "OnScriptTickServer" if side == "SERVER" else "OnScriptTickClient"
            self.ListenForEvent(self._namespace, self._system,
                                self._tick_event, self, self._on_tick)

        def GetRegistrationApiVersion(self):
            return ContentRegistry.API_VERSION

        def RegisterContent(self, pack_id, api_version, specs):
            try:
                return self.registry.register(pack_id, api_version, specs)
            except Exception as error:
                self.registry.rejected[_error_text(pack_id)] = _error_text(error)
                return {"accepted": False, "error": _error_text(error)}

        def GetContentReport(self):
            report = self.registry.report()
            if self._network_session is not None:
                report['network'] = self._network_session.report()
            return report

        def GetNetworkSession(self):
            if self._destroyed or self._network_session is None:
                raise ValueError("No live payload channels in this content session")
            return self._network_session

        def _start_network(self, loader):
            from core.network_session import ModSdkNetworkSession
            contexts = getattr(loader, 'contexts', {})
            for mod_id in getattr(loader, 'order', []):
                context = contexts[mod_id]
                if loader.results[mod_id].get('ready') and context.payload_registry.size():
                    if self._network_session is None:
                        self._network_session = ModSdkNetworkSession(self, server_api, side.lower())
                    channel = self._network_session.open_channel(mod_id, context.payload_registry,
                        recipients=self._network_recipients)
                    context.on_close(channel.close)

        def _network_recipients(self, mode, targets):
            from core.network_session import native_player_recipients
            return native_player_recipients(mode, targets)

        def _on_tick(self, args=None):
            if self._tick_driver is not None and not self._destroyed:
                self._tick_driver.on_tick()

        def GetEntityRuntime(self, dimension_id=0):
            if (side != "SERVER" or self._destroyed or self.registry._session is None
                    or self.registry.state != "initialized"):
                raise ValueError("Entity runtime requires a live server content session")
            dimension_id = int(dimension_id)
            if dimension_id in self._owned_runtimes:
                return self._owned_runtimes[dimension_id]
            bridge = server_api.GetSystem("NeoForgeCore", "EntityBridge")
            if bridge is None:
                raise ValueError("Entity bridge is unavailable")
            from core.content_events import ContentModBus, ContentGameBus
            if self._entity_mod_bus is None:
                loader = self.registry._session.loader
                self._entity_mod_bus = ContentModBus(loader)
                self._entity_game_bus = ContentGameBus(loader)
            runtime = bridge.createEntityRuntime(dimension_id, self._entity_mod_bus, self._entity_game_bus)
            self._owned_runtimes[dimension_id] = runtime
            return runtime

        def GetRegisteredEntityTypes(self):
            if (side != 'SERVER' or self._destroyed or self.registry._session is None
                    or self.registry.state != 'initialized'):
                raise ValueError('Entity registry requires a live server content session')
            return sorted(self.registry._session.loader.registries.get('minecraft:entity_type', {}))

        def SpawnRegisteredEntity(self, identifier, position, dimension_id=0):
            # Resolve the published original factory; do not create a placeholder type.
            names = self.GetRegisteredEntityTypes()
            if identifier not in names:
                raise ValueError('Entity type was not published by an active content mod: ' + _error_text(identifier))
            entity_type = self.registry._session.loader.registries['minecraft:entity_type'][identifier]
            from minecraft.entity import _EntityType
            if not isinstance(entity_type, _EntityType) or entity_type._factory is None:
                raise ValueError('Registered entity has no reviewed original factory')
            return self.GetEntityRuntime(dimension_id).spawn(entity_type, position)

        def _on_scripts_loaded(self, args=None):
            if self._collect_requested or self.registry.state != "collecting":
                return
            self._collect_requested = True
            # Providers listen before this engine barrier, independent of InitServer order.
            self.BroadcastEvent("NeoCoreCollectContent", {"api_version": ContentRegistry.API_VERSION, "side": side})
            self.registry.start()
            if self.registry._session is not None and self.registry.state == "initialized":
                loader = self.registry._session.loader
                if hasattr(loader, "post_game_event"):
                    from core.content_events import ContentTickDriver
                    self._tick_driver = ContentTickDriver(loader, side)
                try:
                    self._start_network(loader)
                except Exception as error:
                    self.registry.state = 'failed'
                    self.registry.error = self.registry.startup_error = u'network: ' + _error_text(error)
                    self._tick_driver = None
                    for resource in (self._network_session, self.registry._session):
                        if resource is not None:
                            try:
                                resource.close()
                            except Exception as cleanup_error:
                                self.registry.cleanup_errors.append(_error_text(cleanup_error))

        def Destroy(self):
            if self._destroyed:
                return
            self._destroyed = True
            self._tick_driver = None
            errors = []
            if self._network_session is not None:
                try:
                    self._network_session.close()
                except Exception as error:
                    errors.append(u'network session: ' + _error_text(error))
            for dimension, runtime in list(self._owned_runtimes.items()):
                try:
                    runtime.close()
                except Exception as error:
                    errors.append(u"entity runtime " + str(dimension) + u": " + _error_text(error))
            self._owned_runtimes.clear()
            try:
                self.registry.close()
            except Exception as error:
                errors.append(u"content session: " + _error_text(error))
            if self._entity_mod_bus is not None:
                try:
                    self._entity_mod_bus.close()
                except Exception as error:
                    errors.append(u"entity mod bus: " + _error_text(error))
            self._entity_mod_bus = self._entity_game_bus = None
            for event, callback in ((loaded_event, self._on_scripts_loaded), (self._tick_event, self._on_tick)):
                try:
                    self.UnListenForEvent(self._namespace, self._system, event, self, callback)
                except Exception as error:
                    errors.append(u"engine listener " + event + u": " + _error_text(error))
            if errors:
                self.registry.cleanup_errors.extend(errors)
                self.registry.state = "close_failed"
                self.registry.error = u"; ".join(errors + ([self.registry.error] if self.registry.error else []))

    globals()[class_name] = NeoCoreLoaderSystem
    return NeoCoreLoaderSystem
