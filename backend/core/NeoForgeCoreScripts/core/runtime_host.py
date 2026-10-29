# -*- coding: utf-8 -*-
"""Thin SDK host for source-snapshot distribution protocol 2.

Copy together with source_modules.py into the one independent core Scripts folder.
"""
from __future__ import absolute_import, print_function
from .source_modules import SourceModuleLoader


def _diagnostic_loader(loader_type, side):
    """Observe actual lifecycle results without changing content entrypoints."""
    class DiagnosticLoader(loader_type):
        def __init__(self, namespace, name):
            self._diagnostic_tick_markers = set()
            self._diagnostic_close_reported = False
            loader_type.__init__(self, namespace, name)

        def _on_scripts_loaded(self, args=None):
            was_collecting = self.registry.state == "collecting"
            loader_type._on_scripts_loaded(self, args)
            if was_collecting:
                print("[NeoCore diagnostic] session", side, self.GetContentReport())

        def _on_tick(self, args=None):
            loader_type._on_tick(self, args)
            driver = self._tick_driver
            if driver is not None:
                ticks = driver.ticks
                if ticks in (1, 20, 100) and ticks not in self._diagnostic_tick_markers:
                    self._diagnostic_tick_markers.add(ticks)
                    print("[NeoCore diagnostic] ticks", side, ticks, self.GetContentReport())

        def Destroy(self):
            loader_type.Destroy(self)
            if not self._diagnostic_close_reported:
                self._diagnostic_close_reported = True
                print("[NeoCore diagnostic] closed", side, self.GetContentReport())

    return DiagnosticLoader


class SourceRuntimeHost(object):
    def __init__(self, core_bundle, api, side, exports, script_package, platform_versions=None, diagnostics=False):
        if core_bundle.get("schema_version") != 1 or core_bundle.get("kind") != "neocore_core_sources":
            raise ValueError("Unsupported core source bundle")
        if side not in ("SERVER", "CLIENT"):
            raise ValueError("Invalid runtime side")
        self.api, self.side = api, side
        self.sources = core_bundle["sources"]
        self.runtime = SourceModuleLoader(self.sources)
        self.systems = []
        self._closed = False
        self.errors = []
        try:
            contents = self.runtime.load("core.content_registry")
            contents.ContentRegistry.API_VERSION = 2
            sessions = self.runtime.load("core.bundled_mods")
            resource_content = self.runtime.load("core.resource_content")
            def factory(specs):
                if any("bundle" not in spec for spec in specs):
                    raise ValueError("Protocol 2 requires a generated content source bundle")
                session = sessions.BundledModSession(self.sources,
                    [spec["bundle"] for spec in specs], side, platform_versions, runtime=self.runtime)
                session.native_item_api = api
                return session
            if side == "SERVER":
                bridge = self.runtime.load("core.modsdk_entity")
                exports["SourceEntityBridge"] = bridge.install_server_system(api)
                self._register("NeoForgeCore", "EntityBridge",
                    script_package + ".modMain.SourceEntityBridge")
            class_name = "SourceServerLoader" if side == "SERVER" else "SourceClientLoader"
            loader_type = contents.install_content_system(api, factory, side)
            loader_type.RUNTIME_REQUIREMENTS_PROTOCOL = 1
            loader_type.RESOURCE_CONTENT_PROTOCOL = resource_content.PROTOCOL
            loader_type.ITEM_CONTENT_PROTOCOL = 1
            loader_type.BLOCK_CONTENT_PROTOCOL = 1
            def register_resources(system, pack_id, resource):
                try:
                    bundle = resource_content.unwrap(pack_id, resource)
                    return system.RegisterContent(pack_id, 2, [{"bundle": bundle}])
                except Exception as error:
                    message = resource_content._error_text(error)
                    system.registry.rejected[resource_content._error_text(pack_id)] = message
                    return {"accepted": False, "error": message}
            loader_type.RegisterResourceContent = register_resources
            exports[class_name] = _diagnostic_loader(loader_type, side) if diagnostics else loader_type
            self._register("NeoCore", "Loader",
                script_package + ".modMain." + class_name)
        except Exception:
            self.close()
            raise

    def _register(self, namespace, name, path):
        system = self.api.RegisterSystem(namespace, name, path)
        if system is None:
            raise RuntimeError("SDK failed to register " + namespace + "/" + name)
        self.systems.append(system)
        return system

    def close(self):
        if self._closed:
            return list(self.errors)
        self._closed = True
        # Remove owned entities while mod callbacks and their imports are still live.
        for system in self.systems:
            if system is None:
                self.errors.append("SDK RegisterSystem did not return a system")
                continue
            try:
                system.Destroy()
                registry = getattr(system, "registry", None)
                if registry is not None and registry.state == "close_failed":
                    self.errors.append(str(registry.error))
                bridge = getattr(system, "entityBridge", None)
                if bridge is not None and bridge._runtimes:
                    self.errors.append("Owned entity removal remains incomplete")
            except Exception as error:
                self.errors.append(str(error))
        self.runtime.close()
        return list(self.errors)
