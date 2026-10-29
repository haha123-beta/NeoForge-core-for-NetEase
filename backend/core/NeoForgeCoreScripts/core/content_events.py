# -*- coding: utf-8 -*-
"""Shared content event adapters. Pre/Post delimit NeoCore dispatch, not engine ticks."""
from __future__ import absolute_import
from neoforge.event.tick import ServerTickEvent
from neoforge.event.client import ClientTickEvent


class ContentTickDriver(object):
    def __init__(self, loader, side):
        if side not in ("SERVER", "CLIENT"):
            raise ValueError("Unknown tick side")
        self.loader = loader
        self.event_type = ServerTickEvent if side == "SERVER" else ClientTickEvent
        self.units = 0
        self.ticks = 0

    def on_tick(self):
        if self.loader._closed:
            return
        self.units += 20
        if self.units < 30:
            return
        self.units -= 30
        self.loader.post_game_event(self.event_type.Pre())
        self.loader.post_game_event(self.event_type.Post())
        self.ticks += 1


class ContentGameBus(object):
    def __init__(self, loader):
        self.loader = loader

    def post(self, event):
        return self.loader.post_game_event(event)


class ContentModBus(object):
    """The loader owns the one-time registration and attribute barriers."""
    def __init__(self, loader):
        self.loader = loader

    def freeze_registries(self):
        self.loader.activate()

    def post(self, event):
        from neoforge.event.entity.registration import EntityAttributeCreationEvent
        if isinstance(event, EntityAttributeCreationEvent):
            if not self.loader._activated or self.loader._closed:
                raise ValueError("Entity attributes require an active loader")
            # Already run during activation. Do not register attributes per dimension.
            return 0
        return sum(self.loader.contexts[mod_id].mod_bus._dispatch(event, strict=True)
                   for mod_id in self.loader.order if self.loader.results[mod_id].get("ready"))

    def close(self):
        # Context cleanup owns the attributes and runs during loader.close().
        return None
