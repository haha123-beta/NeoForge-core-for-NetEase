# -*- coding: utf-8 -*-
# modMain.py
# NeoForge Core - 入口，只提供服务，不自己注册
#
# 位置与导入约定（依据官方文档，见 概览.md「官方依据」）：
#   1. modMain.py 是唯一入口，文件名不可自定义；
#   2. 官方要求它放在 Scripts（脚本）子文件夹下，否则手机端失效 —— 本包即
#      behavior_pack_7k1k1i4l/NeoForgeCoreScripts/modMain.py；
#   3. 脚本文件夹本身是 import 的根，例：RegisterSystem 的 clsPath
#      写作 "tutorialScripts.tutorialServerSystem.TutorialServerSystem"；
#   4. 每个含 modMain.py 的文件夹 = 一个 Mcp 代码模块。
#
# 关于 import 前缀的两种可能：
#   引擎究竟把「行为包根」还是「脚本文件夹」放进 sys.path，本机无法验证。
#   两种情况下前缀不同：
#       根 = 行为包根    -> from NeoForgeCoreScripts.core.alpha_neoforge import ...
#       根 = 脚本文件夹  -> from core.alpha_neoforge import ...
#   所以下面把**两种前缀都试一遍**，并明确打印出实际生效的是哪一种 ---
#   这条信息对后续所有层的 import 写法至关重要。

from __future__ import print_function
from __future__ import absolute_import

import os
import sys
from mod.common.mod import Mod

# 脚本文件夹（本文件所在目录）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 行为包根（脚本文件夹的上一级）
PACK_DIR = os.path.dirname(SCRIPT_DIR)
# 脚本文件夹名，用于拼「行为包根为 sys.path 根」时的前缀
SCRIPT_FOLDER = os.path.basename(SCRIPT_DIR)

# 两种根都挂上，保证无论引擎放哪个进去，import 都能通
for _candidate in (SCRIPT_DIR, PACK_DIR):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

print(u"[NeoForge] 核心包已加载")


# ============================================================
# 启动自检
# ============================================================
#
# 为什么必须有这个自检：
#   整个核心是分层设计的（core / container / java_stdlib / …），
#   层与层之间靠点分导入串联。这条链路能否成立，取决于引擎把哪个目录
#   放进 sys.path —— 这一点在本机无法验证（本机没有 ModSDK），只能进游戏验。
#   所以启动时把两种前缀都真的跑一遍，并把结果与 sys.path 打进日志：
#     哪种前缀成功 -> 后续层统一用那种写法
#     全部失败     -> 打印完整诊断，并退化为「核心不可用」
#
#   无论结果如何都不抛异常，避免一个 import 问题让整个包加载失败。

# 探测用的短模块名（两种前缀共用这部分）
_PROBE_MODULES = (
    u"core.alpha_neoforge",
    u"core.injector",
    u"container.mod_instance",
)

# 包导入前缀候选：空串表示「脚本文件夹就是根」，否则是「行为包根 + 文件夹名」
_PREFIX_CANDIDATES = (u"", SCRIPT_FOLDER)


def _try_import(module_name):
    """尝试导入，返回 (是否成功, 错误)。"""
    try:
        __import__(module_name)
        return True, None
    except Exception as error:
        return False, error


def _self_check():
    """
    探测导入前缀，返回 (生效前缀, 明细列表)。

    生效前缀为 None 表示两种都失败，核心不可用。
    """
    details = []
    working_prefix = None

    for prefix in _PREFIX_CANDIDATES:
        prefix_ok = True
        for short_name in _PROBE_MODULES:
            full_name = (prefix + u"." + short_name) if prefix else short_name
            ok, error = _try_import(full_name)
            details.append((prefix, full_name, ok, error))
            if not ok:
                prefix_ok = False
        if prefix_ok and working_prefix is None:
            working_prefix = prefix

    print(u"[NeoForge] ===== 启动自检 =====")
    print(u"[NeoForge] 脚本文件夹: {}".format(SCRIPT_DIR))
    print(u"[NeoForge] 行为包根:   {}".format(PACK_DIR))
    print(u"[NeoForge] sys.path 前 4 项:")
    for entry in sys.path[:4]:
        print(u"[NeoForge]     {}".format(entry))

    # 只打印第一轮（首选前缀）的逐条结果，避免刷屏
    for prefix, full_name, ok, error in details[:len(_PROBE_MODULES)]:
        mark = u"[OK]  " if ok else u"[FAIL]"
        if ok:
            print(u"[NeoForge] {} import {}".format(mark, full_name))
        else:
            print(u"[NeoForge] {} import {} -> {}".format(mark, full_name, error))

    if working_prefix is not None:
        if working_prefix:
            print(u"[NeoForge] 生效前缀: {}（引擎把行为包根放进了 sys.path）".format(
                working_prefix))
        else:
            print(u"[NeoForge] 生效前缀: （无）—— 引擎把脚本文件夹放进了 sys.path")
        print(u"[NeoForge] 分层导入链路可用")
    else:
        print(u"[NeoForge] 分层导入链路不可用！")
        print(u"[NeoForge] 已尝试的两种前缀：")
        for prefix, full_name, ok, error in details:
            print(u"[NeoForge]     {} -> {}".format(
                full_name, u"OK" if ok else error))
        print(u"[NeoForge] 请把上面 sys.path 的内容与报错一并反馈，据此调整。")
    print(u"[NeoForge] ======================")

    return working_prefix, details


_IMPORT_PREFIX, _SELF_CHECK_DETAILS = _self_check()


# ============================================================
# 导入核心模块
# ============================================================
# 用自检得出的前缀导入；自检失败时退化为「核心不可用」的函数桩，
# 保证 modMain.py 本身总能被引擎执行完，不至于整个包加载失败。

def _resolve_core():
    """按自检结果拿到 register_modpack 等函数。"""
    target = (u"{}.core.alpha_neoforge".format(_IMPORT_PREFIX)
              if _IMPORT_PREFIX else u"core.alpha_neoforge")
    try:
        module = __import__(target, fromlist=[u"register_modpack"])
        print(u"[NeoForge] 核心模块导入成功: {}".format(target))
        return module
    except Exception as error:
        print(u"[NeoForge] 核心模块导入失败: {} -> {}".format(target, error))
        return None


_core_module = _resolve_core()


def register_modpack(resources_path):
    """注册一个模组包（转发到 α 层）。"""
    if _core_module is None:
        return {"success": False, "message": u"核心模块未加载"}
    return _core_module.register_modpack(resources_path)


def get_registered_modpacks():
    """取已注册的模组包。"""
    if _core_module is None:
        return {}
    return _core_module.get_registered_modpacks()


def list_all_modpacks():
    """在控制台列出已注册的模组包。"""
    if _core_module is None:
        return
    _core_module.list_all_modpacks()


def get_self_check_result():
    """供其他包查询启动自检结果，返回 (生效前缀, 明细列表)。"""
    return _IMPORT_PREFIX, list(_SELF_CHECK_DETAILS)


def load_mod_folders(specs, side="SERVER", platform_versions=None):
    """Load extracted folders in place. Retain the session and close it on shutdown."""
    if _IMPORT_PREFIX is None:
        raise RuntimeError("Core imports are unavailable")
    prefix = (_IMPORT_PREFIX + u".") if _IMPORT_PREFIX else u""
    module = __import__(prefix + "core.extracted_mods", fromlist=["ExtractedModSession"])
    return module.ExtractedModSession(specs, os, sys, side, platform_versions)


@Mod.Binding(name="NeoForgeCore", version="1.0.0")
class NeoForgeCore(object):

    def __init__(self):
        print(u"[NeoForge] 核心包初始化")
        self.translated_loaders = {}
        self.translated_errors = {}

    def _start_translated(self, side):
        if side in self.translated_loaders:
            return
        if _IMPORT_PREFIX is None:
            self.translated_errors[side] = u"核心导入失败，未启动翻译模组"
            return
        prefix = (_IMPORT_PREFIX + u".") if _IMPORT_PREFIX else u""
        try:
            prepared = __import__(prefix + "prepared_mods", fromlist=["MOD_INDEX"])
            module = __import__(prefix + "core.translated_loader",
                                fromlist=["TranslatedModLoader"])
            loader = module.TranslatedModLoader(
                side=side, platform_versions=prepared.MOD_INDEX.get("platform_versions", {}))
            self.translated_loaders[side] = loader
            report = loader.load(prepared.MOD_INDEX)
            for mod_id in sorted(report):
                result = report[mod_id]
                print(u"[NeoForge] {} {}: {} {}".format(
                    side, mod_id, result["state"], result["message"]))
        except Exception as error:
            self.translated_errors[side] = str(error)
            loader = self.translated_loaders.get(side)
            if loader is not None:
                loader.close()
            print(u"[NeoForge] 翻译模组启动失败: {}".format(error))

    def _stop_translated(self, side):
        loader = self.translated_loaders.get(side)
        if loader is not None:
            report = loader.close()
            for mod_id, result in report.items():
                if result["state"] == "cleanup_failed":
                    print(u"[NeoForge] 清理失败 {}: {}".format(mod_id, result["message"]))

    def get_translated_report(self, side="SERVER"):
        loader = self.translated_loaders.get(side)
        return {"error": self.translated_errors.get(side),
                "mods": dict((key, dict(value)) for key, value in loader.results.items())
                if loader is not None else {}}

    @Mod.InitServer()
    def init_server(self):
        print(u"[NeoForge] 服务端就绪，等待其他包注册模组")
        if _IMPORT_PREFIX is None:
            print(u"[NeoForge] 警告：分层导入未通过自检，部分功能可能不可用")
        # Register the server bridge only from InitServer, never on the client.
        # No entities or demo content are spawned automatically.
        if _IMPORT_PREFIX is not None:
            import mod.server.extraServerApi as serverApi
            module_path = ((u"{}.".format(_IMPORT_PREFIX) if _IMPORT_PREFIX else u"")
                           + u"core.modsdk_entity")
            bridge_module = __import__(module_path, fromlist=[u"install_server_system"])
            bridge_module.install_server_system(serverApi)
            serverApi.RegisterSystem(u"NeoForgeCore", u"EntityBridge",
                                     module_path + u".EntityBridgeSystem")
        if _IMPORT_PREFIX is not None:
            content_path = ((_IMPORT_PREFIX + u".") if _IMPORT_PREFIX else u"") + "core.content_registry"
            content_module = __import__(content_path, fromlist=["install_content_system"])
            config_path = ((_IMPORT_PREFIX + u".") if _IMPORT_PREFIX else u"") + "neocore_config"
            config = __import__(config_path, fromlist=["PLATFORM_VERSIONS"])
            def open_content_session(specs):
                return load_mod_folders(specs, "SERVER", config.PLATFORM_VERSIONS)
            content_module.install_content_system(serverApi, open_content_session)
            serverApi.RegisterSystem("NeoCore", "Loader", content_path + ".NeoCoreLoaderSystem")
        self._start_translated("SERVER")
        list_all_modpacks()

    @Mod.DestroyServer()
    def destroy_server(self):
        print(u"[NeoForge] 服务端销毁")
        self._stop_translated("SERVER")

    @Mod.InitClient()
    def init_client(self):
        print(u"[NeoForge] 客户端就绪")
        if _IMPORT_PREFIX is not None:
            import mod.client.extraClientApi as clientApi
            prefix = ((_IMPORT_PREFIX + u".") if _IMPORT_PREFIX else u"")
            content_path = prefix + "core.content_registry"
            content_module = __import__(content_path, fromlist=["install_content_system"])
            config = __import__(prefix + "neocore_config", fromlist=["PLATFORM_VERSIONS"])
            def open_client_session(specs):
                return load_mod_folders(specs, "CLIENT", config.PLATFORM_VERSIONS)
            content_module.install_content_system(clientApi, open_client_session, "CLIENT")
            clientApi.RegisterSystem("NeoCore", "Loader", content_path + ".NeoCoreClientLoaderSystem")
        self._start_translated("CLIENT")

    @Mod.DestroyClient()
    def destroy_client(self):
        print(u"[NeoForge] 客户端销毁")
        self._stop_translated("CLIENT")


if __name__ == "__main__":
    print(u"\n[NeoForge] 自测模式")
    print(u"[NeoForge] 生效前缀: {}".format(_IMPORT_PREFIX))
    print(u"[NeoForge] 核心包加载成功，等待外部调用")
