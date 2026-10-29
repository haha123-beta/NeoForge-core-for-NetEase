# -*- coding: utf-8 -*-
from __future__ import absolute_import
from neoforge.event import IEventBus
from neoforge.event.base import Dist
from neoforge.config import ModContainer,FMLModContainer
from java_stdlib.lang import IllegalStateException,UnsupportedOperationException
_active_contexts=[]

class ModEntryScope(object):
    def __init__(self,context):self.context=context
    def __enter__(self):_active_contexts.append(self.context);return self.context
    def __exit__(self,*args):
        if not _active_contexts or _active_contexts[-1] is not self.context:raise RuntimeError("Mod entry scope stack mismatch")
        _active_contexts.pop()
        return False


class ModEntrypoints(object):
    ABI_VERSION = 2
    @staticmethod
    def _handlers(target):
        from neoforge.event.base import Event
        cls = target if isinstance(target,type) else type(target)
        for parent in cls.__mro__[1:]:
            if parent.__dict__.get('_nc_event_handlers'):
                raise ValueError("Annotated event handlers in superclasses are unsupported by bus registration")
        handlers=cls.__dict__.get('_nc_event_handlers',())
        for row in handlers:
            event_type=row['event_type']
            if not isinstance(event_type,type) or not issubclass(event_type,Event):
                raise ValueError("Event handler must accept a supported Event subtype")
        return handlers

    @staticmethod
    def _subscribe(bus,target,row,owner):
        from neoforge.event.base import EventPriority
        method=getattr(target,row['method_name'])
        signature=tuple(row['signature'])
        def callback(event):
            return method(event,**{'_nc_java_signature':signature})
        entry=bus.subscribe(callback,event_type=row['event_type'],
                            priority=EventPriority.valueOf(row['priority']),
                            receive_canceled=row['receive_canceled'])
        entry['owner']=owner if owner is not None else callback
        return entry

    @staticmethod
    def registerAnnotated(bus,target):
        handlers=ModEntrypoints._handlers(target)
        if any(entry['owner'] is target for entry in bus._listeners):return target
        if any(bool(row['static']) != isinstance(target,type) for row in handlers):
            raise ValueError("Class registration requires static handlers; object registration requires instance handlers")
        staged=[]
        try:
            for row in handlers:staged.append(ModEntrypoints._subscribe(bus,target,row,target))
        except BaseException:
            for entry in staged:
                if entry in bus._listeners:bus._listeners.remove(entry)
            raise
        return target

    @staticmethod
    def automatic(context,cls):
        handlers=ModEntrypoints._handlers(cls)
        if any(not row['static'] for row in handlers):raise ValueError("Automatic event handlers must be static")
        buses=set(row['bus'] for row in handlers)
        if buses-set(('MOD','GAME')):raise ValueError("Unknown event bus classification")
        if len(buses)==1:
            bus=context.mod_bus if 'MOD' in buses else context.game_bus
            return ModEntrypoints.registerAnnotated(bus,cls)
        staged=[]
        try:
            for row in handlers:
                bus=context.mod_bus if row['bus']=='MOD' else context.game_bus
                staged.append((bus,ModEntrypoints._subscribe(bus,cls,row,None)))
        except BaseException:
            for bus,entry in staged:
                if entry in bus._listeners:bus._listeners.remove(entry)
            raise
        return cls

    @staticmethod
    def create(cls,mod_id,signature,physical_sides,context):
        if context.mod_id!=mod_id:raise ValueError("@Mod id does not match content descriptor")
        if getattr(context,'_closed',False):raise ValueError("Mod context is closed")
        physical=getattr(context,'physical_side',None)
        if physical not in ('CLIENT','DEDICATED_SERVER'):raise ValueError("Physical side must be supplied by the host")
        if physical not in physical_sides:return None
        if cls.__dict__.get('_nc_JavaClassABI')!=2 or cls.__dict__.get('_nc_JavaMethodsABI')!=1:
            raise RuntimeError("Generated @Mod constructor requires Java class ABI2/method ABI1")
        values={'net.neoforged.bus.api.IEventBus':context.mod_bus,
                'net.neoforged.fml.ModContainer':context.mod_container,
                'net.neoforged.fml.javafmlmod.FMLModContainer':context.mod_container,
                'net.neoforged.api.distmarker.Dist':Dist.CLIENT if physical=='CLIENT' else Dist.DEDICATED_SERVER}
        if len(set(signature))!=len(signature) or any(name not in values for name in signature):
            raise ValueError("Unsupported or duplicated @Mod constructor parameter")
        if not isinstance(context.mod_bus,IEventBus) or not isinstance(context.mod_container,FMLModContainer):
            raise ValueError("@Mod injected objects do not have reviewed runtime types")
        with ModEntryScope(context):
            return cls(*[values[name] for name in signature],**{'_nc_java_constructor':tuple(signature)})

class ScopedGameBus(object):
    def _owner(self):
        if not _active_contexts:raise IllegalStateException("NeoForge.EVENT_BUS requires an active content context")
        context=_active_contexts[-1]
        if getattr(context,'_closed',False):raise IllegalStateException("Content context is closed")
        return context.game_bus
    def __getattr__(self,name):
        if name in ('post','_dispatch'):raise UnsupportedOperationException("Global event posting requires an explicit host dispatcher")
        return getattr(self._owner(),name)

class NeoForge(object):
    EVENT_BUS=ScopedGameBus()

JAVA_MAP={'neocore.runtime.ModEntrypoints':ModEntrypoints,'net.neoforged.neoforge.common.NeoForge':NeoForge}
