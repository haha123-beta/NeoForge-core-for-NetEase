# -*- coding: utf-8 -*-
"""Load explicitly indexed translated mods, without moving their source JARs.

The index is prepared on the desktop. Runtime imports Python entry points only;
source_jar is provenance, never a module search path or executable bytecode.
"""
from __future__ import absolute_import
import re
import copy
from neoforge.event import IEventBus
from neoforge.network import _error_text
from neoforge.config import FMLModContainer, ConfigRegistry
from core.mod_versions import matches
from core.config_session import ConfigSession

try:
    _string_type = basestring
except NameError:
    _string_type = str


class ModContext(object):
    def __init__(self, descriptor, config_registry=None):
        self.mod_id = descriptor["mod_id"]
        self.descriptor = dict(descriptor)
        self.mod_bus = IEventBus("mod:" + self.mod_id)
        self.game_bus = IEventBus("game:" + self.mod_id)
        self.mod_bus._mod_context=self
        self.game_bus._mod_context=self
        self.instance = None
        self._cleanup = []
        self._closed = False
        self.cleanup_errors = []
        self.mod_container = FMLModContainer(self.mod_id, config_registry)
        self.mod_container._event_bus=self.mod_bus
        self.physical_side="CLIENT"
        self.on_close(self.mod_container.close)
        self.config_session = ConfigSession(self.mod_container, self.mod_bus)
        self.on_close(self.config_session.close)
        from neoforge.network import PayloadRegistry
        self.payload_registry = PayloadRegistry()
        self.on_close(self.payload_registry.clear)

    def on_close(self, callback):
        if self._closed or not callable(callback):
            raise ValueError("Cleanup must be callable and registered before close")
        self._cleanup.append(callback)

    def close(self):
        if not self._closed:
            self._closed = True
            for callback in reversed(self._cleanup):
                try:
                    callback()
                except Exception as error:
                    self.cleanup_errors.append(_error_text(error))
            self._cleanup = []
            for name, bus in (("game_bus", self.game_bus), ("mod_bus", self.mod_bus)):
                try:
                    bus.clear()
                except Exception as error:
                    self.cleanup_errors.append(name + ": " + _error_text(error))
        return list(self.cleanup_errors)



def import_entrypoint(path):
    module_name, separator, attribute = path.partition(":")
    if not separator or not re.match(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$", module_name):
        raise ValueError("Expected package.module:entrypoint")
    if not re.match(r"^[A-Za-z_]\w*$", attribute):
        raise ValueError("Invalid entrypoint name")
    module = __import__(module_name, fromlist=[attribute])
    entrypoint = getattr(module, attribute)
    if not callable(entrypoint):
        raise ValueError("Entrypoint must be callable")
    return entrypoint


class TranslatedModLoader(object):
    """One-shot startup with deterministic dependency order and explicit failures."""
    def __init__(self, resolver=None, side="SERVER", platform_versions=None):
        if side not in ("SERVER", "CLIENT"):
            raise ValueError("Invalid loader side")
        self.side = side
        self.platform_versions = dict(platform_versions or {})
        self._platform_ids=frozenset(('minecraft','neoforge'))|frozenset(self.platform_versions)
        self.resolver = resolver or import_entrypoint
        self.config_registry = ConfigRegistry()
        self.contexts = {}
        self.results = {}
        self.order = []
        from neoforge.capabilities import EntityCapabilityRegistry
        self.capability_registry = EntityCapabilityRegistry()
        self.registries = {}
        self._activated = False
        self._started = False
        self._closed = False

    def load(self, index):
        if self._started or self._closed:
            raise ValueError("Loader already started; restart instead of importing twice")
        if index.get("schema_version") != 1:
            raise ValueError("Unsupported translated mod index version")
        descriptors = {}
        for raw in index.get("mods", []):
            row = dict(raw)
            mod_id = row.get("mod_id", "")
            if not re.match(r"^[a-z][a-z0-9_]{1,63}$", mod_id):
                raise ValueError("Invalid mod ID: " + str(mod_id))
            if mod_id in descriptors:
                raise ValueError("Duplicate mod ID: " + mod_id)
            if not isinstance(row.get("requires", []), list):
                raise ValueError("requires must be a list of mod IDs")
            if any(not isinstance(dep, _string_type) for dep in row.get("requires", [])):
                raise ValueError("Dependency IDs must be strings")
            row["requires"] = list(row.get("requires", []))
            if row.get("side", "BOTH") not in ("SERVER", "CLIENT", "BOTH"):
                raise ValueError("Invalid mod side: " + str(row.get("side")))
            descriptors[mod_id] = row
        self._started = True
        active = {}
        for mod_id, row in descriptors.items():
            side = row.get("side", "BOTH")
            if side not in ("SERVER", "CLIENT", "BOTH"):
                raise ValueError("Invalid mod side: " + str(side))
            if side not in ("BOTH", self.side):
                self.results[mod_id] = {"state": "skipped", "message": "Other logical side"}
            elif mod_id in self._platform_ids:
                self.results[mod_id]={'state':'blocked','phase':'identity',
                    'message':'Content cannot claim a reserved platform mod ID: '+mod_id}
            else:
                active[mod_id] = row
        waiting = dict((key, set(row["requires"])) for key, row in active.items())
        versions = dict(self.platform_versions)
        versions.update((key, row.get("version", "")) for key, row in active.items())
        for mod_id, row in active.items():
            warnings = []
            try:
                for dep in row.get("dependency_constraints", []):
                    dep_side = dep.get("side", "BOTH")
                    if dep_side not in ("SERVER", "CLIENT", "BOTH"):
                        raise ValueError("Invalid dependency side")
                    if dep_side not in ("BOTH", self.side):
                        continue
                    name = dep["modId"]
                    kind = dep.get("type", "required" if dep.get("mandatory", True) else "optional")
                    if kind not in ("required", "optional", "incompatible", "discouraged"):
                        raise ValueError("Unknown dependency type: " + kind)
                    present = name in versions
                    if not present and kind == "required":
                        raise ValueError("Missing dependency or declared platform version: " + name)
                    if not present:
                        continue
                    accepted = matches(versions[name], dep.get("versionRange", ""))
                    if kind in ("required", "optional") and not accepted:
                        raise ValueError("Incompatible dependency version: " + name)
                    if kind == "incompatible" and accepted:
                        raise ValueError("Prohibited dependency: " + name)
                    if kind == "discouraged" and accepted:
                        warnings.append("Discouraged dependency: " + name)
                    if kind == "required" and name in active:
                        row["requires"].append(name)
                    ordering = dep.get("ordering", "NONE")
                    if ordering not in ("NONE", "BEFORE", "AFTER"):
                        raise ValueError("Unknown dependency ordering")
                    if name in active:
                        if kind == "required" and ordering != "BEFORE":
                            waiting[mod_id].add(name)
                        if ordering == "AFTER":
                            waiting[mod_id].add(name)
                        elif ordering == "BEFORE":
                            waiting[name].add(mod_id)
                row["_warnings"] = warnings
            except Exception as error:
                self.results[mod_id] = {"state": "blocked", "message": _error_text(error), "phase": "dependencies"}
        for mod_id, row in active.items():
            issues = row.get("compatibility_issues", [])
            if issues:
                self.results[mod_id] = {
                    "state": "blocked", "phase": "compatibility",
                    "message": "Unported Mixin/bytecode requirements",
                    "issues": copy.deepcopy(issues)}
            requirement_report=row.get('_runtime_requirements_report')
            if requirement_report is not None and requirement_report.get('status')=='blocked':
                previous=self.results.get(mod_id)
                self.results[mod_id]={'state':'blocked','phase':'runtime_requirements',
                    'message':'Runtime requirements failed before content import',
                    'runtime_requirements':copy.deepcopy(requirement_report)}
                if previous:self.results[mod_id]['prior_failure']=copy.deepcopy(previous)
        pending = set(active) - set(self.results)
        while pending:
            progressed = False
            for mod_id in sorted(pending):
                row = active[mod_id]
                dependencies = row["requires"]
                missing = [dep for dep in dependencies if dep not in active]
                failed = [dep for dep in dependencies
                          if self.results.get(dep, {}).get("state") in ("failed", "blocked")]
                if missing or failed:
                    self.results[mod_id] = {
                        "state": "blocked", "message": "Unavailable dependencies: " +
                        ", ".join(sorted(set(missing + failed)))}
                elif any(dep in pending for dep in waiting[mod_id]):
                    continue
                else:
                    context = ModContext(row, self.config_registry)
                    context.side = self.side
                    try:
                        bindings=row.get('runtime_mixin_bindings',[])
                        if bindings:
                            from neoforge.mixin_hooks import MixinHooks
                            hook_scope=MixinHooks.openScope(context)
                            context.on_close(hook_scope.close)
                            for binding in bindings:
                                factory=self.resolver(binding['module']+':'+binding['class_name'])
                                method=getattr(factory,binding['handler'])
                                function=method
                                if not callable(function):raise TypeError('Runtime Mixin handler is not callable')
                                if binding.get('hook_abi',1)>MixinHooks.ABI_VERSION:
                                    raise RuntimeError('Runtime Mixin hook ABI requires newer core')
                                if binding.get('kind','callback')=='modify_arg':
                                    def invoke(receiver,argument,function=function):
                                        return function(receiver,argument)
                                elif binding.get('kind','callback')=='callback':
                                    def invoke(receiver,args,ci,function=function,capture=binding['capture_arguments']):
                                        return function(receiver,*(tuple(args)+(ci,) if capture else (ci,)))
                                else:raise ValueError('Unknown runtime Mixin binding kind')
                                hook_scope.register(binding['site'],invoke,binding['priority'])
                        entrypoint = self.resolver(row["entrypoint"])
                        context.instance = entrypoint(context)
                    except Exception as error:
                        cleanup_errors = context.close()
                        self.results[mod_id] = {
                            "state": "failed", "message": _error_text(error),
                            "phase": "entrypoint", "cleanup_errors": cleanup_errors}
                    else:
                        self.contexts[mod_id] = context
                        self.order.append(mod_id)
                        # Does not imply resource conversion, registry freeze or engine readiness.
                        self.results[mod_id] = {"state": "initialized", "message": "",
                                                "warnings": row.get("_warnings", [])}
                pending.remove(mod_id)
                progressed = True
            if not progressed:
                for mod_id in sorted(pending):
                    self.results[mod_id] = {
                        "state": "blocked",
                        "message": "Dependency cycle or dependency on a cycle"}
                break
        # A required dependency explicitly ordered AFTER its dependent can fail late.
        changed = True
        while changed:
            changed = False
            for mod_id in self.order:
                if self.results[mod_id]["state"] != "initialized":
                    continue
                failed = [dep for dep in active[mod_id]["requires"]
                          if self.results.get(dep, {}).get("state") != "initialized"]
                if failed:
                    errors = self.contexts[mod_id].close()
                    self.results[mod_id] = {
                        "state": "blocked", "phase": "dependencies",
                        "message": "Required dependency failed: " + ", ".join(failed),
                        "cleanup_errors": errors}
                    changed = True
        for mod_id,row in active.items():
            if '_runtime_requirements_report' in row:
                self.results[mod_id]['runtime_requirements']=copy.deepcopy(row['_runtime_requirements_report'])
        return dict((key, dict(value)) for key, value in self.results.items())

    def activate(self):
        """Run Python registration/setup barriers; does not create engine assets."""
        if not self._started or self._closed:
            raise ValueError("Activation requires a live loaded session")
        if self._activated:
            return copy.deepcopy(self.results)
        self._activated = True
        from neoforge.event.fml.lifecycle import FMLCommonSetupEvent
        from neoforge.event.fml.lifecycle import FMLClientSetupEvent, FMLLoadCompleteEvent
        from neoforge.capabilities import RegisterCapabilitiesEvent
        from neoforge.event.entity.registration import EntityAttributeCreationEvent
        from neoforge.network import RegisterPayloadHandlersEvent
        stages = [("registration", None), ("capabilities", RegisterCapabilitiesEvent),
                  ("entity_attributes", EntityAttributeCreationEvent),
                  ("payload_handlers", RegisterPayloadHandlersEvent),
                  ("common_setup", FMLCommonSetupEvent)]
        if self.side == "CLIENT":
            stages.append(("client_setup", FMLClientSetupEvent))
        stages.append(("load_complete", FMLLoadCompleteEvent))
        published = {}
        def release_attributes(event):
            for entity_type, supplier in event._attributes.items():
                if entity_type._attributes is supplier:
                    entity_type._attributes = None
        def fail(mod_id, phase, error):
            errors = self.contexts[mod_id].close()
            self.capability_registry.remove_owner(self.contexts[mod_id])
            for key, location in published.pop(mod_id, []):
                self.registries[key].pop(location, None)
            self.results[mod_id].update(state="failed", phase=phase,
                ready=False, message=_error_text(error), cleanup_errors=errors)
        def propagate():
            changed = True
            while changed:
                changed = False
                for mod_id in self.order:
                    if self.results[mod_id]["state"] != "initialized":
                        continue
                    required = self.contexts[mod_id].descriptor.get("requires", [])
                    if any(self.results.get(dep, {}).get("state") != "initialized"
                           for dep in required):
                        fail(mod_id, "dependencies", "Required dependency failed during activation")
                        changed = True
        for phase, event_type in stages:
            if event_type is None:
                # Block holders must be bound before item factories across all
                # loaded owners, even when ITEMS was attached to the bus first.
                # Other registry tasks retain their existing relative order.
                tasks = [(mod_id, deferred) for mod_id in self.order
                         if self.results[mod_id]['state'] == 'initialized'
                         for deferred in self.contexts[mod_id].mod_bus.getRegistries()]
                # GameData explicitly places these three registries before
                # vanilla registration. Do not move blocks ahead of components.
                priority = {'minecraft:attribute':0, 'minecraft:data_component_type':1,
                            'minecraft:armor_material':2, 'minecraft:block':3}
                tasks.sort(key=lambda task: priority.get(task[1].registry_key.registry(),4))
                for mod_id, deferred in tasks:
                    if self.results[mod_id]['state'] != 'initialized':continue
                    try:
                        key = deferred.registry_key.registry()
                        from neoforge.mod_entrypoints import ModEntryScope
                        with ModEntryScope(self.contexts[mod_id]):deferred.freeze_and_register()
                        staged = {}
                        for holder in deferred.getEntries():
                            location = holder.location.toString()
                            if location in staged or location in self.registries.get(key, {}):
                                raise ValueError('Duplicate registry entry: ' + location)
                            staged[location] = holder.get()
                        published.setdefault(mod_id, []).extend((key, location) for location in staged)
                        self.registries.setdefault(key, {}).update(staged)
                        self.results[mod_id]['phase'] = phase
                    except Exception as error:fail(mod_id, phase, error)
                    propagate()
                continue
            queued=[]
            for mod_id in self.order:
                if self.results[mod_id]["state"] != "initialized":
                    continue
                context = self.contexts[mod_id]
                try:
                    if event_type is RegisterPayloadHandlersEvent:
                        context.mod_bus.post(RegisterPayloadHandlersEvent(context.payload_registry), strict=True)
                        context.payload_registry.freeze()
                    elif event_type is EntityAttributeCreationEvent:
                        event = EntityAttributeCreationEvent()
                        try:
                            context.mod_bus.post(event, strict=True)
                        except Exception:
                            release_attributes(event)
                            raise
                        context.on_close(lambda event=event: release_attributes(event))
                    elif event_type is RegisterCapabilitiesEvent:
                        event = RegisterCapabilitiesEvent(self.capability_registry, context)
                        try:
                            context.mod_bus.post(event, strict=True)
                        finally:
                            event.close()
                    else:
                        event=event_type()
                        try:context.mod_bus.post(event,strict=True)
                        except Exception:
                            if hasattr(event,'cancelWork'):event.cancelWork()
                            raise
                        if hasattr(event,'drainWork'):queued.append((mod_id,event))
                    self.results[mod_id]["phase"] = phase
                except Exception as error:
                    fail(mod_id, phase, error)
                propagate()
            for mod_id,event in queued:
                if self.results[mod_id]['state']!='initialized':event.cancelWork();continue
                try:
                    from neoforge.mod_entrypoints import ModEntryScope
                    with ModEntryScope(self.contexts[mod_id]):event.drainWork()
                except Exception as error:fail(mod_id,phase,error)
                propagate()
        for mod_id in self.order:
            if self.results[mod_id]["state"] == "initialized":
                self.results[mod_id].update(phase="ready", ready=True)
        return copy.deepcopy(self.results)

    def post_game_event(self, event):
        if self._closed:
            return 0
        return sum(self.contexts[mod_id].game_bus._dispatch(event) for mod_id in self.order
                   if self.results[mod_id]["state"] == "initialized")

    def close(self):
        if not self._closed:
            self._closed = True
            self.registries.clear()
            self.capability_registry.close()
            for mod_id in reversed(self.order):
                startup_result = copy.deepcopy(self.results[mod_id])
                errors = self.contexts[mod_id].close()
                self.results[mod_id] = {
                    "state": "cleanup_failed" if errors else "unloaded",
                    "message": "; ".join(errors), "cleanup_errors": errors,
                    "startup_result": startup_result}
        return dict((key, dict(value)) for key, value in self.results.items())
