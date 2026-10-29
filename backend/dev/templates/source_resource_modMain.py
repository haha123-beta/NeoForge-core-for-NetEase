# -*- coding: utf-8 -*-
"""Generated resources-layout entry; content activation is owned by NeoCore."""
from __future__ import print_function
from __CONTENT_SCRIPT__.resources._nc_resources import RESOURCE
from mod.common.mod import Mod

# Give each content pack its own script folder and namespace.
SCRIPT_PACKAGE = "__CONTENT_SCRIPT__"
PACK_ID = "__PACK_ID__"
NAMESPACE = "__PACK_ID__"
print("[NeoCore content] entry imported", PACK_ID)


def register_provider(api, side):
    print("[NeoCore content] provider startup", PACK_ID, side)
    base = api.GetServerSystemCls() if side == "SERVER" else api.GetClientSystemCls()
    loaded_event = ("LoadServerAddonScriptsAfter" if side == "SERVER"
                    else "LoadClientAddonScriptsAfter")
    class_name = "ServerProvider" if side == "SERVER" else "ClientProvider"

    class Provider(base):
        def __init__(self, namespace, name):
            base.__init__(self, namespace, name)
            self.closed = False
            self.last_registration = None
            self.ListenForEvent("NeoCore", "Loader", "NeoCoreCollectContent",
                                self, self.register_content)
            self.ListenForEvent(api.GetEngineNamespace(), api.GetEngineSystemName(),
                                loaded_event, self, self.check_core)

        def register_content(self, args):
            core = api.GetSystem("NeoCore", "Loader")
            if core is None:
                self.last_registration = {"accepted": False, "phase": "missing_core"}
                print("[Content] NeoCore is missing")
                return
            if RESOURCE["bundle"].get("runtime_requirements") is not None and getattr(core, "RUNTIME_REQUIREMENTS_PROTOCOL", 0) < 1:
                self.last_registration = {"accepted": False, "phase": "runtime_requirements_protocol"}
                print("[Content] Runtime requirements protocol 1 required; update the independent NeoCore pack", PACK_ID)
                return
            if getattr(core, "RESOURCE_CONTENT_PROTOCOL", 0) != 1:
                self.last_registration = {"accepted": False, "phase": "resources_protocol"}
                print("[Content] Resources content protocol 1 required; update NeoCore", PACK_ID)
                return
            if RESOURCE['bundle'].get('item_content') is not None and getattr(core, 'ITEM_CONTENT_PROTOCOL', 0) != 1:
                self.last_registration = {'accepted':False, 'phase':'item_content_protocol'}
                print('[Content] Item content protocol 1 required; update NeoCore', PACK_ID)
                return
            if RESOURCE['bundle'].get('item_content',{}).get('blocks') and getattr(core,'BLOCK_CONTENT_PROTOCOL',0)!=1:
                self.last_registration={'accepted':False,'phase':'block_content_protocol'}
                print('[Content] Block content protocol 1 required; update NeoCore',PACK_ID)
                return
            result = core.RegisterResourceContent(PACK_ID, RESOURCE)
            self.last_registration = result
            print("[NeoCore content] registration", PACK_ID, side, result)
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


@Mod.Binding(name="__PACK_ID__", version="1.0.0")
class ContentEntry(object):
    @Mod.InitServer()
    def init_server(self):
        import mod.server.extraServerApi as api
        register_provider(api, "SERVER")

    @Mod.InitClient()
    def init_client(self):
        import mod.client.extraClientApi as api
        register_provider(api, "CLIENT")
