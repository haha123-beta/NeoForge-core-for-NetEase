# -*- coding: utf-8 -*-
"""Server lifecycle event data, without inventing a MinecraftServer backend."""
from __future__ import absolute_import
from neoforge.event.base import Event


class ServerLifecycleEvent(Event):
    def __init__(self, server):
        if type(self) is ServerLifecycleEvent:
            raise TypeError('ServerLifecycleEvent is abstract')
        Event.__init__(self)
        self.server = server

    def getServer(self):
        return self.server


class ServerStartingEvent(ServerLifecycleEvent):
    def __init__(self, server):
        ServerLifecycleEvent.__init__(self, server)


JAVA_MAP = {
    'net.neoforged.neoforge.event.server.ServerLifecycleEvent':ServerLifecycleEvent,
    'net.neoforged.neoforge.event.server.ServerStartingEvent':ServerStartingEvent}
