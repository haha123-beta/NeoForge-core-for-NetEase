# -*- coding: utf-8 -*-
from __future__ import print_function
from mod.common.mod import Mod
from NeoCoreSourceScripts.runtime_host import SourceRuntimeHost
from NeoCoreSourceScripts.source_snapshot import BUNDLE

HOSTS = {}
PLATFORM_VERSIONS = {}
print("[NeoCore][r35-pc-fix] entry imported")


def start(api, side):
    if side in HOSTS:
        raise ValueError("NeoCore side already started")
    print("[NeoCore] startup begin", side)
    HOSTS[side] = SourceRuntimeHost(BUNDLE, api, side, globals(),
                                    "NeoCoreSourceScripts", PLATFORM_VERSIONS, diagnostics=True)
    print("[NeoCore] startup ready", side, "systems", len(HOSTS[side].systems))


def close(side):
    host = HOSTS.pop(side, None)
    if host is not None:
        for error in host.close():
            print("[NeoCore] Cleanup failed:", error)


@Mod.Binding(name="NeoCore", version="0.2.0")
class NeoCoreEntry(object):
    @Mod.InitServer()
    def init_server(self):
        import mod.server.extraServerApi as api
        start(api, "SERVER")

    @Mod.InitClient()
    def init_client(self):
        import mod.client.extraClientApi as api
        start(api, "CLIENT")

    @Mod.DestroyServer()
    def destroy_server(self):
        close("SERVER")

    @Mod.DestroyClient()
    def destroy_client(self):
        close("CLIENT")