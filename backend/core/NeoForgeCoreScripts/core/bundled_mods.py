# -*- coding: utf-8 -*-
"""One private core runtime plus independent content source snapshots.

The host supplies sources. Original directories remain build inputs; no runtime I/O.
"""
from __future__ import absolute_import
import copy
from core.source_modules import SourceModuleLoader
from core.runtime_requirements import inspect_requirements
from neoforge.network import _error_text
from core.item_content import bind as bind_item_content
from core.block_content import validate as validate_block_content


class BundledModSession(object):
    def __init__(self, core_sources, bundles, side="SERVER", platform_versions=None, runtime=None):
        sources = copy.deepcopy(core_sources)
        rows = []
        requirements=[]
        self.item_contracts = []
        self.physical_side=side
        self.block_binding_report={'status':'NOT_REQUESTED','engine_verified':False}
        self.native_item_api = None
        self.item_codec = None
        self.item_binding_report = {'status':'NOT_REQUESTED', 'engine_verified':False}
        for bundle in bundles:
            if bundle.get("schema_version") != 1 or bundle.get("kind") != "neocore_content_sources":
                raise ValueError("Unsupported content source bundle")
            for name, record in bundle.get("sources", {}).items():
                if name in sources:
                    raise ValueError("Duplicate bundled module: " + name)
                reserved=('java','net.minecraft','net.neoforged','com.mojang','it.unimi','neocore')
                if name in ('net','com','it') or any(name==root or name.startswith(root+'.') for root in reserved):
                    raise ValueError("Content shadows Java compatibility API: " + name)
                sources[name] = copy.deepcopy(record)
            owned=copy.deepcopy(bundle.get("mods", []))
            if bundle.get('item_content') is not None:
                contract = copy.deepcopy(bundle['item_content'])
                if sorted(contract.get('owners', [])) != sorted(row['mod_id'] for row in owned):
                    raise ValueError('Native item contract owner differs from content bundle')
                self.item_contracts.append(contract)
            rows.extend(owned)
            requirements.append((bundle.get('runtime_requirements'),bundle.get('sources',{}),owned))
        self._owns_runtime = runtime is None
        self.runtime = runtime if runtime is not None else SourceModuleLoader(sources)
        self._before_modules = set(self.runtime.modules)
        self._content_names = set(sources) - set(core_sources)
        if runtime is not None:
            self.runtime.add_sources(dict((name, sources[name]) for name in self._content_names))
        self.loader = None
        self.api_scope = None
        self._closed = False
        self._close_errors = []
        try:
            api = self.runtime.load("core.java_api")
            api_map=api.collect_java_api()
            for manifest,content_sources,owned in requirements:
                report=inspect_requirements(manifest,content_sources,api_map)
                for descriptor in owned:descriptor['_runtime_requirements_report']=copy.deepcopy(report)
                if report['status'] == 'blocked':
                    # Other content may import this pack without declaring a dependency.
                    # Reject that path too, before any package initializer can execute.
                    for name in content_sources:
                        self.runtime._blocked_sources[name] = 'Runtime requirements failed'
            self.api_scope = api.JavaApiImports(self.runtime).install(api_map)
            loader_type = self.runtime.load("core.translated_loader").TranslatedModLoader
            self.loader = loader_type(self._entrypoint, side, platform_versions)
            self.report = self.loader.load({"schema_version": 1, "mods": rows})
        except Exception as error:
            try:
                self.close()
            except Exception as cleanup_error:
                raise RuntimeError(u"Session startup failed: " + _error_text(error) +
                                   u"; cleanup failed: " + _error_text(cleanup_error))
            raise

    def activate_native(self):
        if not self.item_contracts:
            return
        try:
            expected_creative = set(row['identifier'] for contract in self.item_contracts
                                    for row in contract['items'] if row.get('creative_tab') == 'minecraft:ingredients')
            from core.item_content import creative_snapshot
            actual_creative = set(creative_snapshot(self.loader.contexts,self.loader.registries.get('minecraft:item',{})))
            owned_names = set(row['identifier'] for contract in self.item_contracts for row in contract['items'])
            if actual_creative & owned_names != expected_creative:
                raise ValueError('Runtime creative item identities differ from built menu definitions')
            expected_blocks=set(row['identifier'] for contract in self.item_contracts for row in contract['items'] if row.get('creative_tab')=='minecraft:building_blocks')
            if expected_blocks:
                actual_blocks=set(creative_snapshot(self.loader.contexts,self.loader.registries.get('minecraft:item',{}),'BUILDING_BLOCKS'))
                if actual_blocks & owned_names != expected_blocks:raise ValueError('Runtime building-block creative identities differ')
            self.block_binding_report=validate_block_content(self.item_contracts,self.loader.registries,self.native_item_api,self.physical_side=='SERVER')
            if any(row.get('fuel') for contract in self.item_contracts for row in contract['items']):
                from neoforge.event.base import Event
                for context in self.loader.contexts.values():
                    for listener in context.game_bus._listeners:
                        kind = listener['event_type']
                        if kind is None or kind in (object,Event) or kind.__name__ == 'FurnaceFuelBurnTimeEvent':
                            raise ValueError('Dynamic fuel listeners require an event-aware native bridge')
            self.item_codec, self.item_binding_report = bind_item_content(
                self.item_contracts, self.loader.registries, self.loader.results, self.native_item_api)
        except Exception as error:
            self.item_binding_report = {'status':'BLOCKED', 'error':_error_text(error),
                                        'engine_verified':False}
            raise

    def _entrypoint(self, path):
        name, separator, attribute = path.partition(":")
        if not separator or not attribute or any(not part for part in attribute.split(".")):
            raise ValueError("Expected bundled package.module:entrypoint or Class.method")
        value = self.runtime.load(name)
        for part in attribute.split("."):
            value = getattr(value, part)
        if not callable(value):
            raise ValueError("Bundled entrypoint must be callable")
        return value

    def close(self):
        if self._closed:
            if self._close_errors:
                raise RuntimeError(u"; ".join(self._close_errors))
            return self.loader.close() if self.loader is not None else {}
        self._closed = True
        if getattr(self, 'item_codec', None) is not None:
            self.item_codec._entries = []
            self.item_binding_report = dict(self.item_binding_report, status='CLOSED')
        try:
            return self.loader.close() if self.loader is not None else {}
        except Exception as error:
            self._close_errors.append(u"loader: " + _error_text(error))
        finally:
            if self.api_scope is not None:
                try:
                    self.api_scope.close()
                except Exception as error:
                    self._close_errors.append(u"api_scope: " + _error_text(error))
            try:
                if self._owns_runtime:
                    self.runtime.close()
                else:
                    for name in sorted(set(self.runtime.modules) - self._before_modules,
                                       key=lambda value: value.count("."), reverse=True):
                        if name in self._content_names or any(content.startswith(name + ".") for content in self._content_names):
                            module = self.runtime.modules.pop(name)
                            parent, unused, child = name.rpartition(".")
                            owner = self.runtime.modules.get(parent)
                            if owner is not None and getattr(owner, child, None) is module:
                                delattr(owner, child)
                    for name in self._content_names:
                        self.runtime.sources.pop(name, None)
                        self.runtime._blocked_sources.pop(name, None)
                    self.runtime._packages = SourceModuleLoader(self.runtime.sources)._packages
            except Exception as error:
                self._close_errors.append(u"runtime: " + _error_text(error))
            if self._close_errors:
                raise RuntimeError(u"; ".join(self._close_errors))
