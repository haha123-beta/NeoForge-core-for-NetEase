# -*- coding: utf-8 -*-
"""Host-owned import scope for unpacked Java package trees.

Filesystem and module-system objects are injected by the existing modMain host.
This still requires that host's os/sys capabilities; it does not bypass SDK limits.
"""
from __future__ import absolute_import
import re
import types
from core.alpha_neoforge import extracted_mod_index
from core.translated_loader import TranslatedModLoader
from core.java_api import collect_java_api, acquire_java_api, release_java_api


class FolderImports(object):
    def __init__(self, filesystem, module_system, roots):
        self.fs, self.system = filesystem, module_system
        self.roots = list(roots)
        self.before = set(module_system.modules)
        self.added_paths = []
        self.namespaces = {}
        self.closed = False

    def install(self):
        packages, modules = {}, {}
        for root in self.roots:
            for directory, children, files in self.fs.walk(root):
                children[:] = sorted(name for name in children
                                     if re.match(r"^[A-Za-z_]\w*$", name) and name != "__pycache__")
                relative = self.fs.path.relpath(directory, root)
                parts = [] if relative == "." else relative.split(self.fs.sep)
                for filename in files:
                    if not filename.endswith(".py") or filename == "__init__.py":
                        continue
                    stem = filename[:-3]
                    if not re.match(r"^[A-Za-z_]\w*$", stem):
                        continue
                    name = ".".join(parts + [stem])
                    path = self.fs.path.realpath(self.fs.path.join(directory, filename))
                    if name in modules and modules[name] != path:
                        raise ValueError("Duplicate Python module: " + name)
                    if name in self.system.modules:
                        raise ValueError("Python module already imported: " + name)
                    modules[name] = path
                    for count in range(1, len(parts) + 1):
                        package = ".".join(parts[:count])
                        location = self.fs.path.join(root, *parts[:count])
                        packages.setdefault(package, [])
                        if location not in packages[package]:
                            packages[package].append(location)
        for name in packages:
            if name in modules or name in self.system.modules:
                raise ValueError("Python package collision: " + name)
        # Validate everything before mutating the process import namespace.
        for root in reversed(self.roots):
            if root not in self.system.path:
                self.system.path.insert(0, root)
                self.added_paths.append(root)
        for name in sorted(packages, key=lambda value: (value.count("."), value)):
            locations = packages[name]
            if any(self.fs.path.isfile(self.fs.path.join(path, "__init__.py"))
                   for path in locations):
                # Real Python packages retain their normal __init__.py execution.
                continue
            module = types.ModuleType(name)
            module.__path__ = locations
            module.__package__ = name
            self.system.modules[name] = module
            self.namespaces[name] = module
            parent, unused, child = name.rpartition(".")
            if parent in self.system.modules:
                setattr(self.system.modules[parent], child, module)

    def close(self):
        if self.closed:
            return
        self.closed = True
        for name, module in list(self.system.modules.items()):
            if name in self.before:
                continue
            filename = getattr(module, "__file__", None)
            owned = name in self.namespaces
            if filename:
                filename = self.fs.path.realpath(filename)
                owned = owned or any(filename.startswith(root + self.fs.sep)
                                     for root in self.roots)
            if owned:
                self.system.modules.pop(name, None)
                parent, unused, child = name.rpartition(".")
                parent_module = self.system.modules.get(parent)
                if parent_module is not None and getattr(parent_module, child, None) is module:
                    delattr(parent_module, child)
        for root in self.added_paths:
            if root in self.system.path:
                self.system.path.remove(root)


_IMPORT_SCOPES = {}


class ExtractedModSession(object):
    def __init__(self, specs, filesystem, module_system, side="SERVER", platform_versions=None):
        self.loader = TranslatedModLoader(side=side, platform_versions=platform_versions)
        rows, roots = [], []
        for spec in specs:
            root = filesystem.path.realpath(spec["folder"])
            if root not in roots:
                roots.append(root)
            index = extracted_mod_index(root, spec["entrypoints"], spec.get("side", "BOTH"))
            rows.extend(index["mods"])
        self._closed = False
        self._scope_key = (id(module_system), tuple(sorted(roots)))
        shared = _IMPORT_SCOPES.get(self._scope_key)
        if shared is None:
            # Load trusted implementations before content roots enter sys.path.
            mapping = collect_java_api()
            imports = FolderImports(filesystem, module_system, roots)
            try:
                imports.install()
                api_key = acquire_java_api(module_system, mapping)
            except Exception:
                imports.close()
                raise
            shared = [imports, 0, api_key]
            _IMPORT_SCOPES[self._scope_key] = shared
        shared[1] += 1
        self.imports = shared[0]
        try:
            self.report = self.loader.load({"schema_version": 1, "mods": rows})
        except Exception:
            self.close()
            raise

    def close(self):
        if self._closed:
            return self.loader.close()
        self._closed = True
        try:
            return self.loader.close()
        finally:
            shared = _IMPORT_SCOPES[self._scope_key]
            shared[1] -= 1
            if shared[1] == 0:
                del _IMPORT_SCOPES[self._scope_key]
                try:
                    release_java_api(shared[2])
                finally:
                    self.imports.close()
