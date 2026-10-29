# -*- coding: utf-8 -*-
"""
分层导入链路自测

这个测试回答一个**本机无法直接验证、但决定整个架构成立与否**的问题：

    核心包的分层（core / container / …）靠 `from core.xxx import ...` 串联，
    这条链路能不能走通，取决于脚本根目录是否在 sys.path 上。

真机是否放行只能进游戏验，但**机制本身**可以在本机验：
只要脚本根目录在 sys.path 上，点分包导入就必须成立。
所以这里模拟「脚本根 = 包根目录」的环境，把官方那种点分导入真的跑一遍。

官方依据（见 概览.md）：
    RegisterSystem 的 clsPath 要求「路径从脚本的第一层算起」，
    官方示例为 "tutorialScripts.tutorialServerSystem.TutorialServerSystem"，
    说明引擎以「文件夹.模块.类」的点分路径解析脚本，脚本根在 sys.path 上。

验证点：
  1. 包根目录作为脚本根时，core.xxx / container.xxx 都能点分导入
  2. `from core.alpha_neoforge import 函数` 这种官方式导入可用
  3. `from core import xxx` 形式可用，且与 core.xxx 是同一个模块对象
  4. 所有层的包目录都有 __init__.py（Py2 下没有它就不是包）
  5. modMain.py 的启动自检逻辑本身是正确的
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary, SCRIPTS_ROOT, PACK_ROOT  # noqa: E402

pkg = Package()

# 脚本的 import 根 = 脚本文件夹（官方要求脚本放在 Scripts 子文件夹下）
SCRIPT_ROOT = SCRIPTS_ROOT


def import_targets():
    """核心包里所有需要能点分导入的模块。"""
    return [
        ("core.alpha_neoforge", "core/alpha_neoforge.py"),
        ("core.injector", "core/injector.py"),
        ("container.mod_instance", "container/mod_instance.py"),
        ("container.lifecycle", "container/lifecycle.py"),
    ]


try:
    # ------------------------------------------------------------
    section("包完整性（Py2 下没有 __init__.py 就不是包）")
    # ------------------------------------------------------------
    for layer in ("core", "container", "neoforge", "minecraft", "java_stdlib",
                  "launcher_skip", "shader", u"未映射api"):
        init_path = os.path.join(SCRIPT_ROOT, layer, "__init__.py")
        check(u"{} 有 __init__.py".format(layer), os.path.isfile(init_path), init_path)

    check(u"脚本根有 __init__.py（引擎把它当包）",
          os.path.isfile(os.path.join(SCRIPT_ROOT, "__init__.py")))

    # ------------------------------------------------------------
    section("点分导入链路")
    # ------------------------------------------------------------
    for dotted, source_rel in import_targets():
        source_path = os.path.join(SCRIPT_ROOT, *source_rel.split("/"))
        check(u"源码存在 {}".format(source_rel), os.path.isfile(source_path), source_path)

        loaded = None
        error = None
        try:
            loaded = pkg.load(dotted)
        except Exception as exc:
            error = exc

        check(u"可点分导入 {}".format(dotted), loaded is not None, error)
        if loaded is not None:
            check(u"{} 记录了自己的模块名".format(dotted),
                  getattr(loaded, "__name__", None) == dotted,
                  getattr(loaded, "__name__", None))

    # ------------------------------------------------------------
    section("官方式导入等价性")
    # ------------------------------------------------------------
    # `from core.alpha_neoforge import register_modpack` 要求
    # sys.modules['core'] 是个真包（有 __path__）且挂上了子模块
    core_pkg = sys.modules.get("core")
    check(u"sys.modules 里有 core 包", core_pkg is not None, list(sys.modules)[:5])
    if core_pkg is not None:
        check(u"core 是真包（有 __path__）", hasattr(core_pkg, "__path__"),
              getattr(core_pkg, "__path__", None))
        check(u"core 包上挂了 alpha_neoforge 子模块",
              hasattr(core_pkg, "alpha_neoforge"))
        check(u"包上的子模块与直接加载的是同一对象",
              getattr(core_pkg, "alpha_neoforge", None) is pkg.load("core.alpha_neoforge"))

    # 真的执行一次官方式导入语句
    import_statement = "from core.alpha_neoforge import register_modpack, parse_toml"
    namespace = {}
    exec_error = None
    try:
        exec(import_statement, namespace)
    except Exception as exc:
        exec_error = exc
    check(u"官方式导入语句可执行", exec_error is None, exec_error)
    check(u"导入到的函数可调用",
          callable(namespace.get("register_modpack")) and callable(namespace.get("parse_toml")))

    # ------------------------------------------------------------
    section("跨层导入（lifecycle 依赖 core）")
    # ------------------------------------------------------------
    lifecycle = pkg.load("container.lifecycle")
    check(u"lifecycle 加载成功", lifecycle is not None)
    check(u"lifecycle 拿到了 alpha_neoforge",
          getattr(lifecycle, "alpha_neoforge", None) is not None)
    check(u"lifecycle 里的 alpha_neoforge 与直接加载的是同一对象",
          getattr(lifecycle, "alpha_neoforge", None) is pkg.load("core.alpha_neoforge"),
          u"若是两个对象，全局注册表会不一致")
    check(u"lifecycle 拿到了 inject_layer",
          getattr(lifecycle, "inject_layer", None) is not None)
    check(u"lifecycle 拿到了 ModInstance",
          getattr(lifecycle, "ModInstance", None) is not None)

    # ------------------------------------------------------------
    section("modMain 的启动自检与双前缀策略")
    # ------------------------------------------------------------
    modmain_path = os.path.join(SCRIPT_ROOT, "modMain.py")
    check(u"modMain.py 在脚本文件夹内", os.path.isfile(modmain_path), modmain_path)

    with open(modmain_path, "rb") as fp:
        source = fp.read().decode("utf-8")

    # 引擎把哪个目录当 import 根是本机无法验证的，所以必须两种前缀都试
    check(u"modMain 支持「脚本文件夹为根」的前缀",
          u"core.alpha_neoforge" in source)
    check(u"modMain 支持「行为包根为根」的前缀（带文件夹名）",
          u"SCRIPT_FOLDER" in source and u"PACK_DIR" in source)
    check(u"modMain 把两种根都挂进 sys.path",
          source.count(u"sys.path.insert") >= 1 and u"PACK_DIR" in source)
    check(u"modMain 有启动自检",
          u"_self_check" in source and u"启动自检" in source)
    check(u"modMain 会打印生效前缀（供真机确认）",
          u"生效前缀" in source)
    check(u"modMain 不因导入失败而中断加载",
          u"try:" in source and u"except Exception as error" in source)

    # 自检探测链里的模块都必须真实存在，否则自检会误报失败
    for name in ("core.alpha_neoforge", "core.injector", "container.mod_instance"):
        check(u"自检链包含 {}".format(name), name in source)

    # 探测链里不能出现实际不存在的模块（曾错写成 core.mod_instance）
    for dotted, _rel in import_targets():
        check(u"自检链里的模块确实存在: {}".format(dotted), pkg.locate(dotted) is not None)

    # ------------------------------------------------------------
    section("行为验证：真的把 modMain.py 跑起来")
    # ------------------------------------------------------------
    # 用桩模块顶替引擎提供的 mod.common.mod，这样可以在本机执行 modMain.py，
    # 检验双前缀自检是否真的能选中「脚本文件夹为根」这条路径。
    import types as _types

    stub_mod = _types.ModuleType("mod")
    stub_common = _types.ModuleType("mod.common")
    stub_modmod = _types.ModuleType("mod.common.mod")

    class _StubMod(object):
        @staticmethod
        def Binding(name=None, version=None):
            def decorator(cls):
                return cls
            return decorator

        @staticmethod
        def InitServer():
            return lambda func: func

        @staticmethod
        def DestroyServer():
            return lambda func: func

        @staticmethod
        def InitClient():
            return lambda func: func

        @staticmethod
        def DestroyClient():
            return lambda func: func

    stub_modmod.Mod = _StubMod
    stub_common.mod = stub_modmod
    stub_mod.common = stub_common

    saved = {}
    for key, value in (("mod", stub_mod), ("mod.common", stub_common),
                       ("mod.common.mod", stub_modmod)):
        saved[key] = sys.modules.get(key)
        sys.modules[key] = value

    try:
        from py2to3lite import compile_module
        modmain_module = compile_module(
            modmain_path, "neoforge_modmain_for_test",
            register_in_sys_modules=False)

        check(u"modMain 可被执行完（不抛异常）", modmain_module is not None)

        prefix, details = modmain_module.get_self_check_result()
        check(u"自检选出了生效前缀", prefix is not None,
              [u"{} -> {}".format(d[1], u"OK" if d[2] else d[3]) for d in details])
        check(u"生效前缀是「脚本文件夹为根」（空前缀）", prefix == u"",
              u"实际: {!r}".format(prefix))

        check(u"modMain 暴露了 register_modpack",
              callable(getattr(modmain_module, "register_modpack", None)))
        check(u"register_modpack 转发到真实 α 层",
              modmain_module.register_modpack(
                  os.path.join(SCRIPT_ROOT, "no_such_dir"))["success"] is False)
        check(u"get_registered_modpacks 可用",
              isinstance(modmain_module.get_registered_modpacks(), dict))
    finally:
        for key, value in saved.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value

finally:
    pass

sys.exit(summary())
