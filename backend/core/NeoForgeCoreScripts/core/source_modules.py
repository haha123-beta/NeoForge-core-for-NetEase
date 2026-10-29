# -*- coding: utf-8 -*-
"""Private Python source modules supplied by a development-time bundle.

No os/sys, runtime directory scan, sys.path mutation or global module injection.
This executes trusted mod Python; it is not a security sandbox or JVM translator.
NetEase compile/packaging acceptance still requires in-game validation.
"""
from __future__ import absolute_import
import re
import types

_EXTERNAL_ROOTS = frozenset((
    "__future__", "_md5", "_random", "logging", "traceback", "random", "json",
    "math", "time", "copy", "base64", "bisect", "calendar", "datetime", "re",
    "Queue", "string", "struct", "types", "weakref", "itertools", "fnmatch",
    "posixpath", "keyword", "hashlib", "zlib", "heapq", "abc", "uuid", "functools",
    "collections", "warnings", "io", "gzip", "binascii", "cStringIO", "contextlib",
    "threading", "ast", "mod_log", "mod", "server", "client"))


def _native_module_name(name):
    # CPython 2.7 module.__init__ uses the S parser (byte string only).
    # Bundle JSON names are Unicode; preserve spelling using explicit UTF-8.
    return name if isinstance(name, str) else name.encode("utf-8")


class SourceModuleLoader(object):
    def __init__(self, sources, external_import=None):
        self.sources = dict(sources)
        self.modules = {}
        self.closed = False
        self._external_import = external_import or __import__
        self._packages = set()
        self._loading = set()
        self._blocked_sources = {}
        for name, row in self.sources.items():
            if not re.match(r"^[^\W\d]\w*(\.[^\W\d]\w*)*$", name, re.UNICODE):
                raise ValueError("Invalid bundled module name: " + str(name))
            if name.split(".")[0] in _EXTERNAL_ROOTS:
                raise ValueError("Bundled source shadows an external module: " + name)
            if not isinstance(row, dict) or "source" not in row:
                raise ValueError("Malformed source record: " + name)
            parts = name.split(".")
            for count in range(1, len(parts)):
                self._packages.add(".".join(parts[:count]))
            if row.get("is_package"):
                self._packages.add(name)
        for name in self._packages:
            if name in self.sources and not self.sources[name].get("is_package"):
                raise ValueError("Module/package collision: " + name)

    def contains(self, name):
        return name in self.sources or name in self._packages or name in self.modules

    def add_sources(self, sources):
        """Add content before its entrypoints run; never replace existing core/imported code."""
        if self.closed:
            raise ValueError("Source module loader is closed")
        duplicate = set(sources) & (set(self.sources) | set(self.modules))
        if duplicate:
            raise ValueError("Bundled module already present: " + ", ".join(sorted(duplicate)))
        combined = dict(self.sources)
        combined.update(sources)
        checked = SourceModuleLoader(combined, self._external_import)
        for name in checked._packages:
            if name in self.modules and not hasattr(self.modules[name], "__path__"):
                raise ValueError("Bundled package collides with loaded class/module: " + name)
        self.sources = checked.sources
        self._packages = checked._packages

    def load(self, name):
        if self.closed:
            raise ImportError("Source module loader is closed")
        if name in self._blocked_sources:
            raise ImportError("Bundled source blocked before import: " + name +
                              "; " + self._blocked_sources[name])
        if name in self.modules:
            return self.modules[name]
        if not self.contains(name):
            raise ImportError("No bundled module: " + name)
        parent_name, unused, child = name.rpartition(".")
        parent = self.load(parent_name) if parent_name else None
        # A package initializer may have imported the requested child itself.
        if name in self.modules:
            return self.modules[name]
        module = types.ModuleType(_native_module_name(name))
        module.__package__ = name if name in self._packages else parent_name
        if name in self._packages:
            module.__path__ = []
        row = self.sources.get(name)
        module.__file__ = row.get("origin", name + ".py") if row else "<namespace:" + name + ">"
        builtins = __builtins__ if isinstance(__builtins__, dict) else vars(__builtins__)
        module.__dict__["__builtins__"] = dict(builtins)
        module.__dict__["__builtins__"]["__import__"] = self.import_module
        self.modules[name] = module
        self._loading.add(name)
        if parent is not None:
            if hasattr(parent, child) and getattr(parent, child) is not module:
                del self.modules[name]
                self._loading.discard(name)
                raise ImportError("Bundled parent attribute collision: " + name)
            setattr(parent, child, module)
        try:
            if row is not None:
                source = row["source"]
                if not isinstance(source, bytes):
                    source = source.encode("utf-8")
                # eval accepts an exec-mode code object in Python 2.7 and 3.
                code = compile(source, module.__file__, "exec", 0, True)
                eval(code, module.__dict__)
        except Exception:
            self.modules.pop(name, None)
            if parent is not None and getattr(parent, child, None) is module:
                delattr(parent, child)
            raise
        finally:
            self._loading.discard(name)
        return module

    def import_module(self, name, globals=None, locals=None, fromlist=(), level=0):
        if self.closed:
            raise ImportError("Source module loader is closed")
        package = (globals or {}).get("__package__", "")
        if level > 0:
            parts = package.split(".") if package else []
            if level > len(parts):
                raise ImportError("Relative import escapes package")
            prefix = ".".join(parts[:len(parts) - level + 1])
            name = prefix + ("." + name if name else "")
        elif level < 0 and package and self.contains(package + "." + name):
            name = package + "." + name
        if not self.contains(name):
            root = name.split(".")[0]
            if root not in _EXTERNAL_ROOTS:
                raise ImportError("Unmapped or unavailable import: " + name)
            return self._external_import(name, globals, locals, fromlist, 0)
        module = self.load(name)
        if fromlist:
            for child in fromlist:
                if child == "*":
                    for exported in getattr(module, "__all__", ()):
                        if not hasattr(module, exported) and self.contains(name + "." + exported):
                            self.load(name + "." + exported)
                elif not hasattr(module, child) and self.contains(name + "." + child):
                    self.load(name + "." + child)
            return module
        return self.load(name.split(".")[0])

    def close(self):
        self.closed = True
        self.modules.clear()
        self.sources.clear()
        self._packages.clear()
        self._blocked_sources.clear()
