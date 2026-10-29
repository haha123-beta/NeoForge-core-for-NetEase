# -*- coding: utf-8 -*-
"""Install implemented Java API class names as Python package attributes.

Receives the module system from its owner; does not add filesystem imports.
Only mapped classes exist. No JVM execution or automatic missing-class stubs.
"""
from __future__ import absolute_import
import types
from core.source_modules import _native_module_name
from core.java_api_catalog import API_MODULES


def collect_java_api():
    result = {}
    allowed = ("java.", "net.minecraft.", "net.neoforged.", "com.mojang.", "it.unimi.", "neocore.", "org.spongepowered.asm.mixin.injection.callback.")
    for name in API_MODULES:
        module = __import__(name, fromlist=["JAVA_MAP"])
        for java_name, value in getattr(module, "JAVA_MAP", {}).items():
            # Narrow reviewed ordinary Minecraft runtime dependencies, never a
            # blanket third-party mod-library namespace allowlist.
            if not java_name.startswith(allowed) and java_name not in ("org.slf4j.Logger", "io.netty.buffer.ByteBuf", "io.netty.buffer.Unpooled", "io.netty.handler.codec.DecoderException", "io.netty.handler.codec.EncoderException", "org.joml.Matrix4f", "org.joml.Vector3f", "com.google.common.collect.ImmutableMap", "com.google.common.collect.ImmutableMap$Builder"):
                continue
            if java_name in result and result[java_name] is not value:
                raise ValueError("Conflicting Java API implementation: " + java_name)
            result[java_name] = value
    return result


class JavaApiImports(object):
    def __init__(self, module_system):
        self.system = module_system
        self.modules = {}
        self.attributes = []
        self.closed = False
        self._exposed = {}
        self.cleanup_errors = []
        self.replaced_modules = {}

    def _attribute(self, owner, name, value):
        nested_owner = getattr(owner, "__neocore_java_owner__", None)
        if nested_owner is not None:
            self._attribute(nested_owner, name, value)
        if hasattr(owner, name):
            if getattr(owner, name) is not value:
                raise ValueError("Java API name collision: " + getattr(owner, "__name__", type(owner).__name__) + "." + name)
            return
        setattr(owner, name, value)
        self.attributes.append((owner, name, value))

    def _package(self, name):
        existing = self.system.modules.get(name)
        if existing is not None:
            if not hasattr(existing, "__path__"):
                if name != 'io' or getattr(existing, '__name__', None) != 'io' or not callable(getattr(existing, 'open', None)):
                    raise ValueError("Java API package collision: " + name)
                self.replaced_modules[name] = existing
            else:
                return existing
        if callable(getattr(self.system, "contains", None)) and self.system.contains(name):
            return self.system.load(name)
        parent, unused, child = name.rpartition(".")
        owner = self._package(parent) if parent else None
        module = types.ModuleType(_native_module_name(name))
        module.__path__ = []
        module.__package__ = name
        # Java's io.netty namespace must preserve Python io for trusted core modules.
        if name == 'io':
            external = getattr(self.system, '_external_import', None)
            native = existing or (external('io', {}, {}, ['open'], 0) if callable(external) else None)
            if native is not None:
                for attribute in dir(native):
                    if not attribute.startswith('__'):
                        setattr(module, attribute, getattr(native, attribute))
        self.system.modules[name] = module
        self.modules[name] = module
        if name in self._exposed:
            module.__neocore_java_owner__ = self._exposed[name]
        elif owner is not None:
            self._attribute(owner, child, module)
        return module

    def install(self, mapping=None):
        if self.closed or self.modules or self.attributes:
            raise ValueError("Java API import scope already used")
        mapping = collect_java_api() if mapping is None else mapping
        normalized = {}
        for java_name, value in mapping.items():
            key = java_name.replace("$", ".")
            if key in normalized and normalized[key] is not value:
                raise ValueError("Conflicting nested Java name: " + key)
            normalized[key] = value
        self._exposed = normalized
        try:
            for java_name in sorted(normalized):
                package, separator, name = java_name.rpartition(".")
                if not separator:
                    raise ValueError("Expected fully qualified Java class name")
                self._attribute(self._package(package), name, normalized[java_name])
        except Exception as error:
            try:
                self.close()
            except Exception as cleanup_error:
                raise RuntimeError("API installation failed: " + str(error) +
                                   "; cleanup failed: " + str(cleanup_error))
            raise
        return self

    def close(self):
        if self.closed:
            if self.cleanup_errors:
                raise RuntimeError("; ".join(self.cleanup_errors))
            return
        self.closed = True
        for owner, name, value in reversed(self.attributes):
            try:
                if getattr(owner, name, None) is value:
                    delattr(owner, name)
            except Exception as error:
                self.cleanup_errors.append("attribute " + name + ": " + str(error))
        for name in sorted(self.modules, key=lambda key: key.count("."), reverse=True):
            try:
                if self.system.modules.get(name) is self.modules[name]:
                    if name in self.replaced_modules:
                        self.system.modules[name] = self.replaced_modules[name]
                    else:
                        del self.system.modules[name]
            except Exception as error:
                self.cleanup_errors.append("module " + name + ": " + str(error))
        self.attributes = []
        self.modules = {}
        self.replaced_modules = {}
        self._exposed.clear()
        if self.cleanup_errors:
            raise RuntimeError("; ".join(self.cleanup_errors))


_SCOPES = {}


def acquire_java_api(module_system, mapping):
    key = id(module_system)
    if key not in _SCOPES:
        _SCOPES[key] = [JavaApiImports(module_system).install(mapping), 0]
    _SCOPES[key][1] += 1
    return key


def release_java_api(key):
    row = _SCOPES[key]
    row[1] -= 1
    if row[1] == 0:
        del _SCOPES[key]
        row[0].close()
