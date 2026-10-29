# -*- coding: utf-8 -*-
"""
harness —— 核心包本地自测脚手架

作用：在没有游戏、没有 ModSDK 的情况下，把核心包（behavior_pack_7k1k1i4l）
的 Python 2 源码加载进本机 Python 3，逐个函数验证。

用法（在 behavior_pack_7k1k1i4l 目录下执行）：

    python dev/run_selftest.py

编写自测脚本时：

    from harness import Package, check, section

    pkg = Package()                       # 自动定位 behavior_pack 根目录
    alpha = pkg.load("core.alpha_neoforge")   # 按 Py2 源码加载成模块
    check("解析出 modId", alpha.parse_toml(text)["modId"] == "demo_mod")
"""

import ast
import os
import shutil
import sys
import tempfile
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from py2to3lite import compile_module, adapt_source, Py2To3Error  # noqa: E402

# 目录约定（官方要求脚本必须放在 Scripts 子文件夹下，否则手机端失效）：
#
#   behavior_pack_7k1k1i4l/          <- PACK_ROOT，行为包根
#   ├── manifest.json
#   ├── dev/                         <- DEV_ROOT，开发期工具（不参与游戏加载）
#   └── NeoForgeCoreScripts/         <- SCRIPTS_ROOT，脚本文件夹，也是 import 的根
#       ├── __init__.py
#       ├── modMain.py
#       ├── core/ container/ java_stdlib/ …
#       └── 概览.md
#
# 注意：脚本的 import 根是 NeoForgeCoreScripts/，不是行为包根。
DEV_ROOT = os.path.dirname(os.path.abspath(__file__))
from workspace_paths import PACK_ROOT as _PACK_ROOT
PACK_ROOT = str(_PACK_ROOT)

SCRIPT_FOLDER_NAME = "NeoForgeCoreScripts"
SCRIPTS_ROOT = os.path.join(PACK_ROOT, SCRIPT_FOLDER_NAME)

# 兼容旧名：源码根
PACKAGE_ROOT = SCRIPTS_ROOT

FIXTURES_ROOT = os.path.join(DEV_ROOT, "fixtures")


class Package(object):
    """
    把核心包当成一个可加载的源码集合。

    加载一个模块前，会先把它的顶层 import 依赖也按同一套转译加载好。
    这一步不能省：Python 的 import 机制只认 .py 源码，
    不会走我们的转译器，一旦某个模块 import 了 Py2 语法的兄弟模块
    （例如 lifecycle 里 `import alpha_neoforge`），就会直接 SyntaxError。
    """

    # 核心包的分层目录；平坦模块名会在这些目录下依次查找
    LAYER_DIRS = (
        "core",
        "container",
        "neoforge",
        "neoforge/events",
        "minecraft",
        "minecraft/client",
        "java_stdlib",
        "launcher_skip",
        "shader",
        u"未映射api",
    )

    def __init__(self, pack_root=SCRIPTS_ROOT):
        self.pack_root = os.path.abspath(pack_root)
        self._loaded = {}
        # 正在加载中的模块：用于打断依赖环（见 load 的环保护）
        self._loading = set()
        # 真正执行过 `__init__.py` 的模块名。
        # 与 _loaded 的区别：_ensure_package 造的**空壳**也在 _loaded 里，
        # 但它没执行过。判断「能不能跳过」必须看这个集合。
        self._executed = set()
        # 只被造成空壳、还没执行 `__init__.py` 的包名
        self._placeholders = set()
        # 临时占位：{模块名: 占位模块对象}
        self._stubs = {}

        # 核心包自身要在 sys.path 上，模组代码里的绝对导入才找得到
        if self.pack_root not in sys.path:
            sys.path.insert(0, self.pack_root)

        # 各层目录也要挂上，否则核心包内部的 `import alpha_neoforge`
        # 会走真实 import 机制，绕开转译器并撞上 Py2 语法
        for directory in self.LAYER_DIRS:
            layer_path = os.path.join(self.pack_root, *directory.split("/"))
            if os.path.isdir(layer_path) and layer_path not in sys.path:
                sys.path.append(layer_path)

    def path_of(self, dotted_name):
        """core.alpha_neoforge -> <pack_root>/core/alpha_neoforge.py"""
        rel = os.path.join(*dotted_name.split(".")) + ".py"
        return os.path.join(self.pack_root, rel)

    def locate(self, module_name):
        """
        找一个核心包模块（或包）的源码文件。

        支持两种写法：
            "core.alpha_neoforge"  按目录层级定位
            "alpha_neoforge"       按层目录里的平坦名定位

        平坦名是必要的：核心包内部用绝对导入（`import alpha_neoforge`），
        被 import 的模块可能落在 core/、container/ 等任一目录下。

        **包也要能定位**（返回它的 `__init__.py`）。
        为什么：原先只找 `<name>.py`，遇到 `neoforge/event/` 这种包
        就返回 None，于是 `load("neoforge.event")` 只由 `_ensure_package`
        造了个**空壳**（有 `__path__` 但没有内容）——
        `__init__.py` 里的导出全部丢失，
        `from neoforge.event import IEventBus` 直接 ImportError。
        事件层拆成包之后这个坑立刻暴露出来了。

        实现上直接按点分路径拼目录，不走 path_of + dirname ——
        那样会丢掉一层（`neoforge.event` 会被解析成 `neoforge/__init__.py`，
        实测踩到）。
        """
        rel_parts = module_name.split(".")

        # 1. <pack_root>/a/b/c.py
        flat_path = os.path.join(self.pack_root, *rel_parts) + ".py"
        if os.path.isfile(flat_path):
            return flat_path

        # 2. <pack_root>/a/b/c/__init__.py（包）
        package_init = os.path.join(self.pack_root, *rel_parts, "__init__.py")
        if os.path.isfile(package_init):
            return package_init

        # 3. 层目录下的平坦名：<pack_root>/<layer>/c.py 或 .../c/__init__.py
        for directory in self.LAYER_DIRS:
            base = os.path.join(self.pack_root, *directory.split("/"))
            candidate = os.path.join(base, module_name + ".py")
            if os.path.isfile(candidate):
                return candidate
            candidate = os.path.join(base, *rel_parts, "__init__.py")
            if os.path.isfile(candidate):
                return candidate

        return None

    def is_package(self, module_name):
        """判断这个名字对应的是不是包（而非单文件模块）。"""
        path = self.locate(module_name)
        return bool(path) and os.path.basename(path) == "__init__.py"

    def _sibling_modules(self, package_name, package_init_path):
        """
        列出一个包的 `__init__.py` 同目录下、同包内的兄弟模块。

        `neoforge/event/__init__.py` → neoforge.event.base / .client / ...
        子包（有 __init__.py 的目录）也算，因为 `__init__.py` 常会
        `from shader.sub import ...`。

        顺序：先普通模块，再子包 —— 子包自己也会递归处理它的兄弟，
        这样依赖从叶子往上建立，符合直觉。
        """
        directory = os.path.dirname(package_init_path)
        plain = []
        packages = []

        for entry in sorted(os.listdir(directory)):
            full = os.path.join(directory, entry)
            if os.path.isdir(full):
                if os.path.isfile(os.path.join(full, "__init__.py")):
                    packages.append(u"{}.{}".format(package_name, entry))
            elif entry.endswith(".py") and entry != "__init__.py":
                plain.append(u"{}.{}".format(package_name, entry[:-3]))

        return plain + packages

    def _source_of(self, dotted_name):
        """读取模块源码（转译后），供预加载扫描 import 用。"""
        path = self.locate(dotted_name)
        if not path:
            return None
        with open(path, "rb") as fp:
            raw = fp.read()
        return adapt_source(raw, filename=os.path.basename(path))

    def _import_dependencies(self, dotted_name, source):
        """
        找出本模块会触发 import 的模块名（按需预加载）。

        遍历**整棵语法树**而不是只看 tree.body：
        核心代码到处用 `try: import x except ImportError:` 做优雅降级，
        那类 import 是嵌套在 Try 节点里的，只看顶层语句会漏掉，
        于是这个模块就不会被预加载，最终走真 import 撞上 Py2 语法。

        返回的是「候选模块名」而非只有顶层包名：
          `import core.alpha_neoforge`  -> core、core.alpha_neoforge
          `from core import alpha_neoforge` -> core、core.alpha_neoforge
        因为 `from core import xxx` 也会加载 core 包下的 xxx 子模块，
        只预加载 core 包本身是不够的（真 import 会去读 Py2 源码而报语法错）。
        """
        names = []
        if not source:
            return names
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return names

        def add(name):
            if name and name not in names:
                names.append(name)

        def add_dotted(dotted):
            """把 a.b.c 拆成 a、a.b、a.b.c 逐级加入。"""
            parts = dotted.split(".")
            for index in range(len(parts)):
                add(".".join(parts[:index + 1]))

        try:
            walker = list(ast.walk(tree))
        except AttributeError:
            walker = list(tree.body)

        for node in walker:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    add_dotted(alias.name)
            elif isinstance(node, ast.ImportFrom):
                # level > 0 是包内相对导入，核心包不用，跳过
                if getattr(node, "level", 0) == 0 and node.module:
                    add_dotted(node.module)
                    # from core import alpha_neoforge 也要带上子模块
                    for alias in node.names:
                        if alias.name != "*":
                            add_dotted(node.module + "." + alias.name)

        return names

    def _ensure_package(self, package_name):
        """
        为点分导入造一个真实的包对象，并挂到 sys.modules。

        为什么要真的建包对象（而不是只往 sys.modules 里塞个名字）：
          `from core.mod_instance import X` 这条语句执行时，
          Python 会先 import 'core'，再取它的 mod_instance 属性。
          如果 sys.modules['core'] 只是一个裸模块、没有 __path__，
          import 机制就无法在其下解析子模块，会直接 ImportError。
          给上 __path__ 之后，它才是一个「包」，子模块才能被解析。

        **注意这只是「壳」**：它的 `__init__.py` 还没执行。
        所以要在 `_placeholders` 里记一笔，`_execute_module` 据此知道
        「这个条目还是空的，得真跑一遍 `__init__.py`」。
        不区分的话 `_execute_module` 会看到 `_loaded` 里已有它就返回空壳，
        `__init__.py` 永远不会执行、导出全部丢失（实测踩到）。
        """
        if package_name in sys.modules:
            return sys.modules[package_name]

        package_dir = os.path.join(self.pack_root, *package_name.split("."))
        init_path = os.path.join(package_dir, "__init__.py")
        if not os.path.isfile(init_path):
            return None

        module = types.ModuleType(package_name)
        module.__path__ = [package_dir]
        module.__file__ = init_path
        module.__package__ = package_name
        sys.modules[package_name] = module
        self._loaded[package_name] = module
        self._placeholders.add(package_name)
        return module

    def load(self, dotted_name):
        """
        按核心包的源码加载模块（先递归预加载依赖，结果缓存）。

        **包的 `__init__.py` 要放在子模块之后执行。**
        为什么：`__init__.py` 里通常写
            from shader.material import ShaderInstance
        这是绝对导入，执行时走**真 import 机制**；
        如果那时 `shader.material` 还不在 sys.modules，
        Python 会从磁盘读 Py2 源码 —— 绕过转译器，撞上
        `except Foo, e:` 立刻 SyntaxError（实测踩到）。

        而自然的预加载顺序是「先 __init__.py 后子模块」，正好会踩中：
        外层 `load("shader.material")` 把它标进 _loading；
        `__init__.py` 里的兄弟预加载调 `load("shader.material")`
        被环保护挡回 None（模块还没建好），于是真 import 落到磁盘上 —— 崩。

        所以这里分两阶段：
            阶段一  预加载（含把包自己的 __init__.py 排到最后）
            阶段二  执行本模块自己的 __init__.py（此时子模块都已就位）

        支持两种写法：
            "core.alpha_neoforge"  按官方约定的点分路径（推荐，贴近真机）
            "alpha_neoforge"       平坦名，兼容旧脚本
        """
        if dotted_name in self._executed:
            return self._loaded.get(dotted_name)

        path = self.locate(dotted_name)
        if path:
            is_init = os.path.basename(path) == "__init__.py"
            if is_init:
                # 请求的就是这个包本身
                self._preload_package(dotted_name)
            else:
                # 请求的是一个模块：把它所在的**整条包链**都预加载好。
                #
                # 为什么连父包一起：`core/__init__.py` 里若有导出（或只是
                # 需要它作为包存在），不执行就会留下一个空壳，
                # `from core import xxx` / `hasattr(core, 'xxx')` 全都取不到
                # （实测踩到：core 包上挂不上 alpha_neoforge）。
                #
                # 顺序：由外向内 —— 先让顶层包就位，再进到它所在的直接包。
                package_name = dotted_name.rsplit(".", 1)[0] \
                    if "." in dotted_name else None
                if package_name:
                    chain = package_name.split(".")
                    for depth in range(len(chain)):
                        self._preload_package(".".join(chain[:depth + 1]))

        return self._execute_module(dotted_name)

    def _preload_package(self, package_name, skip=None):
        """
        预加载一个包：先按顺序加载它的子模块，最后才执行它的 `__init__.py`。

        这是 `load` 的阶段一。顺序的定义见 `_package_children`。

        `skip` 用于「正在加载的那个目标模块」—— 它由调用方在
        `__init__.py` 之后执行，这样 `__init__.py` 里对它的绝对导入
        能命中 sys.modules 里的转译版本，而不是落回磁盘上的 Py2 源码。
        """
        init_path = self.locate(package_name)
        if not init_path or os.path.basename(init_path) != "__init__.py":
            return None

        if package_name in self._executed:
            return None

        # 先把这个包的**父包**准备好（`import a.b.c` 要求 a.b 先存在）
        if "." in package_name:
            parent = package_name.rsplit(".", 1)[0]
            self._ensure_package(parent)

        children = self._package_children(package_name, init_path)
        for child in children:
            child_path = self.locate(child)
            if child_path and os.path.basename(child_path) == "__init__.py":
                # 子包：递归（它自己也会把 __init__ 排到最后）
                self._preload_package(child)
            else:
                self._execute_module(child)

        # 子模块都执行完了，现在执行 `__init__.py` 本身
        self._execute_module(package_name)

        return None

    def _package_children(self, package_name, init_path):
        """
        列出一个包的**预加载顺序**：先普通子模块，再子包。

        子包放在后面，因为 `__init__.py` 里常有
            from shader.sub import Something
        子包先就位更稳妥；而子包内部的 `__init__.py` 又由
        `_preload_package` 递归保证排在它自己的子模块之后。
        """
        directory = os.path.dirname(init_path)
        plain = []
        packages = []

        for entry in sorted(os.listdir(directory)):
            full = os.path.join(directory, entry)
            if os.path.isdir(full):
                if os.path.isfile(os.path.join(full, "__init__.py")):
                    packages.append(u"{}.{}".format(package_name, entry))
            elif entry.endswith(".py") and entry != "__init__.py":
                plain.append(u"{}.{}".format(package_name, entry[:-3]))

        return plain + packages

    def _execute_module(self, dotted_name):
        """
        真正编译并执行一个模块（阶段二）。

        前置条件：它的依赖与同包兄弟已经加载好（由 `load` 保证）。

        「已在 `_loaded` 里」不足以判定可以跳过 ——
        `_ensure_package` 造的空壳也在里面。所以要看 `_executed`。
        """
        if dotted_name in self._executed:
            return self._loaded.get(dotted_name)

        # 环保护：Python 自己的 import 有这层保护，这里原先没有。
        #
        # 为什么必须加：`_import_dependencies` 会走 ast.walk，
        # 因此**函数体内**的延迟 import 也算依赖。于是
        #     level.py  里 `from minecraft.entity import Player`（函数内）
        #     entity.py 里 `from minecraft.level import Level`（函数内）
        # 在依赖图上构成一个环，预加载就会无限递归
        # （实测：RecursionError，栈里全是 harness.load 自己）。
        # 正在加载中的模块直接返回 None，由稍后的真 import 去拿它。
        if dotted_name in self._loading:
            return None

        path = self.locate(dotted_name)
        if not path:
            raise Py2To3Error(u"模块文件不存在: {}".format(dotted_name))

        self._loading.add(dotted_name)
        try:
            source = self._source_of(dotted_name)

            for dependency in self._import_dependencies(dotted_name, source):
                # 「已经就位」的判定：在 sys.modules 里，而且不是空壳。
                #
                # 不能只看 self._executed —— 有些模块是被**真 import** 拉进来的
                # （例如 java_stdlib），它不在 _executed 里但其实已经好了；
                # 重复执行会出各种怪问题（实测：23 个测试文件一起挂）。
                # 也不能只看 sys.modules —— 空壳也在里面，得真跑一遍。
                if dependency in sys.modules \
                        and dependency not in self._placeholders:
                    continue
                if dependency == dotted_name:
                    continue
                # 只预加载确实存在于核心包里的模块；
                # mod、os、sys 这类外部模块交给正常 import 机制处理
                if self.locate(dependency):
                    self.load(dependency)

            # 这个包先前可能只被造成了空壳（`_ensure_package`）。
            # **复用那个壳对象**，只清空它的字典 —— 不要新建模块。
            #
            # 为什么必须复用：`sys.modules['core']` 是别人拿着的引用，
            # 子模块执行时会把 `setattr(core_pkg, 'alpha_neoforge', mod)`
            # 挂到那个壳上。如果这里换成新对象，
            # `sys.modules['core']` 仍指向旧壳、但 `_loaded` 指向新对象，
            # 两边分叉，`hasattr(core_pkg, 'alpha_neoforge')` 就没了
            # （实测踩到，test_import_chain 抓到）。
            reuse = None
            if dotted_name in self._placeholders:
                self._placeholders.discard(dotted_name)
                reuse = self._loaded.get(dotted_name) \
                    or sys.modules.get(dotted_name)

            # A dependency cycle can let native import finish a Py3-compatible
            # module while we preload siblings. Re-executing it would create a
            # second set of event classes and silently break isinstance/subscriptions.
            imported = sys.modules.get(dotted_name)
            spec = getattr(imported, "__spec__", None)
            imported_path = getattr(imported, "__file__", "")
            if (reuse is None and spec is not None
                    and not getattr(spec, "_initializing", False)
                    and os.path.normcase(os.path.abspath(imported_path))
                    == os.path.normcase(os.path.abspath(path))):
                module = imported
            else:
                module = compile_module(path, dotted_name, module=reuse)
            # 壳被复用后补齐包的属性
            if reuse is not None:
                module.__path__ = [os.path.dirname(path)]
                module.__package__ = dotted_name
        finally:
            self._loading.discard(dotted_name)

        self._executed.add(dotted_name)

        # 点分导入：补上包对象，并把它挂到父包上，
        # 这样后续的 `from core.mod_instance import X` 才能走通
        if "." in dotted_name:
            parent_name = dotted_name.rsplit(".", 1)[0]
            parent = self._ensure_package(parent_name)
            if parent is not None:
                setattr(parent, dotted_name.rsplit(".", 1)[1], module)

        # 一个模块执行完，顺手把**已加载的其他子模块**重新挂回各自的父包。
        #
        # 为什么需要：包的空壳是被**复用**的（见 compile_module 的说明），
        # 复用时只清 dunder、把模块自己的内容清掉 ——
        # 那会把之前 `setattr` 挂上去的子模块属性（例如
        # `core.alpha_neoforge`）一起抹掉。
        # 不用重跑任何模块，只是把 `_loaded` 里现成的对象重新挂一遍。
        self._relink_loaded_children()

        self._loaded[dotted_name] = module

        # 同时登记一个「平坦」别名：
        # 核心包内部若还有 `import alpha_neoforge` 这类平坦写法，
        # 两边会变成两个独立模块对象，全局注册表就对不上了。
        flat = dotted_name.split(".")[-1]
        if flat not in sys.modules and flat not in ("net", "java", "com", "it", "org"):
            sys.modules[flat] = module
        if flat not in self._loaded:
            self._loaded[flat] = module

        return module

    def _relink_loaded_children(self):
        """
        把所有已加载的点分模块重新挂回各自的父包。

        存在的理由：包的空壳会被**复用**（见 `compile_module`），
        复用时会清掉模块自己的内容 —— 包括之前 `setattr` 挂上去的
        子模块属性。于是 `core.alpha_neoforge` 会莫名消失
        （实测：`hasattr(core, 'alpha_neoforge')` 变成 False）。

        这里不重跑任何模块，只把 `_loaded` 里现成的对象重新挂一遍 ——
        幂等、便宜，而且能自愈。
        """
        for name in list(self._loaded.keys()):
            if "." not in name:
                continue
            module = self._loaded.get(name)
            if module is None:
                continue
            parent_name, child_name = name.rsplit(".", 1)
            parent = sys.modules.get(parent_name)
            if parent is None:
                continue
            if getattr(parent, child_name, None) is module:
                continue
            setattr(parent, child_name, module)
        return None

    def load_flat(self, module_name):
        """
        按核心包「平坦」的模块名加载，例如 "alpha_neoforge"。

        核心包里各层之间用的是绝对导入，模块实际以顶层名字存在于
        sys.modules 中；自测要直接调用它们时用这个方法更贴近真机。
        """
        for directory in ("core", "container"):
            candidate = os.path.join(self.pack_root, directory, module_name + ".py")
            if os.path.isfile(candidate):
                if module_name in self._loaded:
                    return self._loaded[module_name]
                module = compile_module(candidate, module_name)
                self._loaded[module_name] = module
                return module
        raise Py2To3Error(u"核心包里找不到模块: {}".format(module_name))

    def temp_dir(self, prefix="neocore_test_"):
        """建一个用完即弃的临时目录。"""
        return tempfile.mkdtemp(prefix=prefix)

    def fixture(self, name):
        """返回 dev/fixtures/<name> 的绝对路径。"""
        return os.path.join(FIXTURES_ROOT, name)


# ============================================================
# 断言与输出
# ============================================================

class _Report(object):
    def __init__(self):
        self.passed = 0
        self.failed = []
        self.section_name = None

    def section(self, title):
        self.section_name = title

    def check(self, label, condition, detail=None):
        if condition:
            self.passed += 1
            print(u"  [OK]   {}".format(label))
        else:
            entry = label
            if detail is not None:
                entry = u"{}  ->  {}".format(label, detail)
            if self.section_name:
                entry = u"[{}] {}".format(self.section_name, entry)
            self.failed.append(entry)
            print(u"  [FAIL] {}".format(entry))

    def summary(self):
        print(u"")
        print(u"  " + u"-" * 52)
        if self.failed:
            print(u"  通过 {} 项，失败 {} 项".format(self.passed, len(self.failed)))
            for item in self.failed:
                print(u"    x {}".format(item))
            print(u"  " + u"-" * 52)
            return 1
        print(u"  全部通过（{} 项）".format(self.passed))
        print(u"  " + u"-" * 52)
        return 0


_report = _Report()


def section(title):
    """开始一个测试分组。"""
    print(u"")
    print(u"== {} ==".format(title))
    _report.section(title)


def check(label, condition, detail=None):
    """断言一条，失败不中断，最后统一汇总。"""
    _report.check(label, condition, detail)


def summary():
    """打印汇总，返回进程退出码。"""
    return _report.summary()


def cleanup(path):
    """删除临时目录，忽略失败。"""
    if path and os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)


# ============================================================
# 测试用最小模组包
# ============================================================

SAMPLE_TOML = u'''modLoader="javafml"
loaderVersion="[1,)"
license="MIT License"

[[mods]]
modId="demo_manaita"
version="0.1.0"
displayName="DemoManaita"
description="A tiny fixture mod used by the local self-test."
authors="tester"
'''


def make_sample_modpack(root_dir, mod_id=u"demo_manaita", nested=True):
    """
    在 root_dir 下造一个最小可识别的模组包。

    nested=True 时把 META-INF 放进一层子目录，
    用来验证 alpha 层的「递归扫描」而不是只看第一层。
    """
    import io

    base = os.path.join(root_dir, u"resources")
    if nested:
        base = os.path.join(base, u"demo_mod-0.1.0")

    meta_dir = os.path.join(base, u"META-INF")
    if not os.path.isdir(meta_dir):
        os.makedirs(meta_dir)

    text = SAMPLE_TOML
    if mod_id != u"demo_manaita":
        text = text.replace(u'demo_manaita', mod_id)

    toml_path = os.path.join(meta_dir, u"neoforge.mods.toml")
    with io.open(toml_path, "w", encoding="utf-8") as fp:
        fp.write(text)

    # 附带几个资源文件，验证 γ 层不依赖具体内容
    for rel in (u"assets/demo/lang/zh_cn.json", u"data/demo/recipe/x.json"):
        target = os.path.join(base, *rel.split(u"/"))
        target_dir = os.path.dirname(target)
        if not os.path.isdir(target_dir):
            os.makedirs(target_dir)
        with io.open(target, "w", encoding="utf-8") as fp:
            fp.write(u"{}")

    return base
