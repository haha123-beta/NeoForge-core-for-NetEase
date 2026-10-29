# -*- coding: utf-8 -*-
"""Copy this folder into a content behavior pack; it contains no NeoCore implementation."""
from __future__ import print_function
import os
from mod.common.mod import Mod

# Give each content pack its own script folder and namespace.
SCRIPT_PACKAGE = "ExampleContentScripts"
PACK_ID = "example_content_pack"
NAMESPACE = "ExampleContent"
MOD_FOLDER = "OriginalMod"
ENTRYPOINTS = {"examplemod": "com.example.mod.MyMod:start"}


def register_provider(api, side):
    base = api.GetServerSystemCls() if side == "SERVER" else api.GetClientSystemCls()
    loaded_event = ("LoadServerAddonScriptsAfter" if side == "SERVER"
                    else "LoadClientAddonScriptsAfter")
    class_name = "ServerProvider" if side == "SERVER" else "ClientProvider"

    class Provider(base):
        def __init__(self, namespace, name):
            base.__init__(self, namespace, name)
            self.closed = False
            self.ListenForEvent("NeoCore", "Loader", "NeoCoreCollectContent",
                                self, self.register_content)
            self.ListenForEvent(api.GetEngineNamespace(), api.GetEngineSystemName(),
                                loaded_event, self, self.check_core)

        def register_content(self, args):
            core = api.GetSystem("NeoCore", "Loader")
            if core is None:
                print("[Content] NeoCore is missing")
                return
            result = core.RegisterContent(PACK_ID, 1, [{
                "folder": os.path.join(os.path.dirname(__file__), "..", MOD_FOLDER),
                "entrypoints": ENTRYPOINTS,
                "side": "BOTH"
            }])
            if not result["accepted"]:
                print("[Content] Registration rejected:", result["error"])

        def check_core(self, args):
            if api.GetSystem("NeoCore", "Loader") is None:
                print("[Content] Enable the independent NeoCore behavior pack")

        def Destroy(self):
            if self.closed:
                return
            self.closed = True
            self.UnListenForEvent("NeoCore", "Loader", "NeoCoreCollectContent",
                                  self, self.register_content)
            self.UnListenForEvent(api.GetEngineNamespace(), api.GetEngineSystemName(),
                                  loaded_event, self, self.check_core)

    globals()[class_name] = Provider
    return api.RegisterSystem(NAMESPACE, class_name,
                              SCRIPT_PACKAGE + ".modMain." + class_name)


@Mod.Binding(name="ExampleContent", version="1.0.0")
class ContentEntry(object):
    @Mod.InitServer()
    def init_server(self):
        import mod.server.extraServerApi as api
        register_provider(api, "SERVER")

    @Mod.InitClient()
    def init_client(self):
        import mod.client.extraClientApi as api
        register_provider(api, "CLIENT")
