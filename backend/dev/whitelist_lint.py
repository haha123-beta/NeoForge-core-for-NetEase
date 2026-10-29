# -*- coding: utf-8 -*-
"""
whitelist_lint —— 检查核心包是否用了官方白名单之外的标准库

为什么需要它
------------
官方《Python模块白名单》（2.9+）原文：
    「由于平台升级了违规模块的检测力度，从2.9 版本开始，
      除模块白名单以外的模块将不允许使用。
      注意：该限制不包括开发者自定义的模块和接口。」

也就是说：
  - 我们自建的包（core / container / java_stdlib / …）不受限制；
  - 但 **import 白名单之外的标准库会被判违规**。

已核实的白名单（480 条）里**没有** `os`、`sys`、`importlib`。
而核心包当前大量使用 `os.path` / `os.walk` / `sys.path`，
这是必须正视的合规风险。

本模块做两件事：
  1. 从官方白名单文件里读出可用模块名（可在 refs/ 下更新）
  2. 静态扫描核心包源码，列出所有 import 及其是否在白名单内

数据来源：refs/_whitelist.txt（抓自官方审核文档页）
"""

import io
import os
import re
import sys


# 官方白名单里与标准库相关的条目（已从 refs/_whitelist.txt 核实）
# 只列 Python 标准库那一部分，不含 mod.* / server.* / client.* 接口。
WHITELIST_STDLIB = set([
    "__future__", "_md5", "_random", "logging", "traceback", "random",
    "json", "math", "time", "copy", "base64", "bisect", "calendar",
    "datetime", "re", "Queue", "string", "struct", "types", "weakref",
    "itertools", "fnmatch", "posixpath", "keyword", "hashlib", "zlib",
    "heapq", "abc", "uuid", "functools", "collections", "warnings",
    "io", "gzip", "binascii", "cStringIO", "contextlib", "threading",
    "singleton", "ast", "mod_log",
])

# 已核实**不在**白名单、但核心包正在使用的模块。
# 列在这里是为了让报告说实话，而不是假装没问题。
KNOWN_VIOLATIONS = {
    "os": u"核心包用 os.path / os.walk 扫描模组目录；官方白名单未收录",
    "sys": u"核心包用 sys.path 挂载脚本根；官方白名单未收录",
    "importlib": u"官方白名单未收录（引擎提供 ImportModule 作为替代）",
}

# 可选功能的标记：文件里出现这行注释，说明该 import 只服务于
# 「需要显式调用才会执行」的可选功能，不属于加载主路径。
#
# 为什么需要这个区分：
#   核心的加载路径不该依赖白名单外的模块；但像「读写配置文件」
#   这种可选能力确实需要 os。把两者混在一起报，
#   真正的结构性风险会被淹没在噪音里。
OPTIONAL_MARKER = u"neocore:optional-io"

# 已知债务基线：核心路径上**已经存在**的白名单违规。
#
# 为什么要基线而不是「一律失败」：
#   α 层要递归扫描模组目录、读 TOML，这就必须用 os ——
#   而白名单里根本没有文件系统接口（已核实）。
#   在白名单口径确认之前（见 概览.md 待验证问题第 4 条），
#   这些违规**无法消除**，也不该让自测一直红着 ——
#   一直红着的检查等于没有检查。
#
# 所以策略是：**存量只报告，新增才失败**。
# 这样既能如实反映现状，又能挡住「新写代码又引入一个白名单外模块」。
KNOWN_DEBT = {
    ("core/alpha_neoforge.py", u"os"),
    ("core/injector.py", u"os"),
    (u"core/接口.py", u"os"),
    (u"core/接口.py", u"sys"),
    ("container/lifecycle.py", u"os"),
    ("container/lifecycle.py", u"sys"),
    ("container/mod_instance.py", u"os"),
    ("java_stdlib/_base.py", u"sys"),
    ("modMain.py", u"os"),
    ("modMain.py", u"sys"),
}


def split_by_debt(violations):
    """
    把违规分成「已知债务」与「新增」两组。

    返回 (已知债务列表, 新增列表)。路径分隔符统一成正斜杠再比对，
    否则 Windows 的反斜杠会让基线匹配不上。
    """
    known = []
    new = []
    for item in violations:
        rel = item[0].replace(u"\\", u"/")
        module = item[2]
        if (rel, module) in KNOWN_DEBT:
            known.append(item)
        else:
            new.append(item)
    return known, new

# 官方提供的替代接口（用于替代不白名单的能力）
OFFICIAL_ALTERNATIVES = {
    "importlib": u"serverApi.ImportModule(path) / clientApi.ImportModule(path)",
    "os (读配置)": u"serverApi.GetModConfigJson(path)",
}

_IMPORT_RE = re.compile(
    r'^[ \t]*(?:from[ \t]+([A-Za-z_][\w\.]*)[ \t]+import|import[ \t]+([A-Za-z_][\w\.]*))',
    re.MULTILINE,
)

_SKIP_DIRS = (".cache", "__pycache__", ".git", "dev", "resources", "entities")


def iter_sources(pack_root, layer_dirs):
    """
    列出核心包的所有源码文件（含包根下的散装 .py）。

    **每个文件只 yield 一次**。

    为什么强调这一点：pack_root 就是脚本根，而各层目录**在它下面**，
    所以「层的递归结果」不会包含包根的散装 .py（`__init__.py`、`modMain.py`），
    需要在层循环**之后**单独补一次 —— 起初这一补写在了循环**里面**，
    于是包根的两个文件被重复 yield 了 len(layer_dirs) 次。
    后果有两个：报出来的「检查了 N 个文件」虚高，
    以及白名单违规会被重复计入。
    """
    seen = set()

    for layer in layer_dirs:
        layer_path = os.path.join(pack_root, *layer.split("/"))
        if not os.path.isdir(layer_path):
            continue
        for root, dirs, files in os.walk(layer_path):
            dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)
            for filename in sorted(files):
                if not filename.endswith(".py"):
                    continue
                full = os.path.join(root, filename)
                if full not in seen:
                    seen.add(full)
                    yield full

    # 包根下直接躺着的 .py（`__init__.py`、`modMain.py`）——
    # 它们不属于任何层目录，所以要在层循环**之外**补一次。
    if os.path.isdir(pack_root):
        for filename in sorted(os.listdir(pack_root)):
            full = os.path.join(pack_root, filename)
            if filename.endswith(".py") and os.path.isfile(full):
                if full not in seen:
                    seen.add(full)
                    yield full


def local_module_names(pack_root, layer_dirs):
    """
    收集「本工程自建的模块名」——这些不受白名单限制。

    官方原文明确「该限制不包括开发者自定义的模块和接口」，
    所以 core / container / java_stdlib / alpha_neoforge 等都不算违规。

    **子包目录名也要收**（例如 `neoforge/event/` 让 `event` 成为合法模块名）。
    只收文件名与顶层层名是不够的 —— 事件层拆成包之后，
    `neoforge/network.py` 里的 `from event import ...` 立刻被误报成
    「使用了白名单外的模块 event」（实测踩到）。
    判定方式是「目录里有 __init__.py 就算包」。
    """
    names = set()

    for path in iter_sources(pack_root, layer_dirs):
        base = os.path.basename(path)
        if base.endswith(".py"):
            names.add(base[:-3])

    for layer in layer_dirs:
        layer_path = os.path.join(pack_root, *layer.split("/"))
        if os.path.isdir(layer_path):
            names.add(layer.split("/")[0])

    # 递归收集层目录下的子包名
    for layer in layer_dirs:
        layer_path = os.path.join(pack_root, *layer.split("/"))
        if not os.path.isdir(layer_path):
            continue
        for root, dirs, _files in os.walk(layer_path):
            dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)
            for dirname in dirs:
                if os.path.isfile(os.path.join(root, dirname, "__init__.py")):
                    names.add(dirname)

    # 引擎提供的模块（官方 API / 日志 / 内建）
    names.update([
        "mod", "mod_log", "server", "client",
        "builtin_modules", "singleton",
    ])
    return names


def optional_io_ranges(source):
    """
    找出被标记为「可选 I/O」的函数所占的行号区间。

    标记方式：函数体里出现注释 `neocore:optional-io`。
    这类函数**只在你显式调用时才执行**，不属于加载主路径，
    所以它内部的 os / sys 导入不算结构性风险。

    为什么按函数而不是整文件判断：
      一个文件里往往既有核心逻辑也有可选 I/O（例如 config.py），
      按整文件豁免会连核心部分的违规一起放过去。

    为什么要先转译再 parse：
      核心包源码是 **Python 2 语法**（`except Foo, e:`），
      本机的 ast.parse 会直接 SyntaxError —— 实测踩到：
      解析一失败整个标记检测就静默失效，可选功能的违规全被算进核心路径。
      py2to3lite 的改写是**逐行替换**，行号不变，所以区间可以放心用。
    """
    import ast

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from py2to3lite import adapt_source, Py2To3Error

    try:
        parseable = adapt_source(source, u"<whitelist_lint>")
    except Py2To3Error:
        return []

    try:
        tree = ast.parse(parseable)
    except SyntaxError:
        return []

    ranges = []
    for node in ast.walk(tree):
        # 只认普通函数定义。**不要**写成 (ast.FunctionDef, ast.AsyncFunctionDef)：
        # Python 2.7 的 ast 里没有 AsyncFunctionDef，
        # 取这个属性会直接 AttributeError。
        if not isinstance(node, ast.FunctionDef):
            continue
        start = node.lineno
        end = getattr(node, "end_lineno", None)
        if end is None:
            # Python 3.7 之前没有 end_lineno：退化成「到文件末尾」
            end = source.count("\n") + 1

        # 注意：标记要在**原文**里找。
        # 转译后的源码可能改变注释以外的东西，而标记本身是注释，原文里一定在。
        body_text = u"\n".join(source.split("\n")[start - 1:end])
        if OPTIONAL_MARKER in body_text:
            ranges.append((start, end))
    return ranges


def scan_file(path, local_names):
    """扫描单个文件，返回 (模块名, 行号, 是否白名单内, 是否可选功能) 列表。"""
    with io.open(path, "r", encoding="utf-8", errors="replace") as fp:
        source = fp.read()

    optional_ranges = optional_io_ranges(source)

    results = []
    for match in _IMPORT_RE.finditer(source):
        module = match.group(1) or match.group(2)
        if not module:
            continue
        top = module.split(".")[0]
        line_no = source.count("\n", 0, match.start()) + 1

        if top in local_names:
            allowed = True      # 自建模块，不受白名单限制
        elif top in WHITELIST_STDLIB:
            allowed = True
        else:
            allowed = False

        optional = False
        for start, end in optional_ranges:
            if start <= line_no <= end:
                optional = True
                break

        results.append((top, line_no, allowed, optional))
    return results


def check_tree(pack_root, layer_dirs):
    """
    扫描整棵树，返回 (检查文件数, 核心违规列表, 可选功能违规列表)。

    违规项形如 (相对路径, 行号, 模块名, 说明)。
    """
    local_names = local_module_names(pack_root, layer_dirs)
    checked = 0
    violations = []
    optional_violations = []

    for path in iter_sources(pack_root, layer_dirs):
        checked += 1
        for module, line_no, allowed, optional in scan_file(path, local_names):
            if not allowed:
                item = (os.path.relpath(path, pack_root), line_no, module,
                        KNOWN_VIOLATIONS.get(module, u"不在官方模块白名单内"))
                if optional:
                    optional_violations.append(item)
                else:
                    violations.append(item)

    return checked, violations, optional_violations


def main():
    # 源码根 = 脚本文件夹（官方要求脚本放在 Scripts 子文件夹下）
    dev_root = os.path.dirname(os.path.abspath(__file__))
    pack_root = os.path.dirname(dev_root)
    scripts_root = os.path.join(pack_root, "NeoForgeCoreScripts")
    if not os.path.isdir(scripts_root):
        scripts_root = pack_root

    # 分层目录的单一来源在 dev/layers.py，避免三处列表漂移导致漏检
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from layers import LAYER_DIRS as layers

    checked, violations, optional_violations = check_tree(scripts_root, layers)

    print(u"官方模块白名单扫描：检查了 {} 个文件".format(checked))
    print(u"（白名单来源：官方《Python模块白名单》，2.9+，共 480 条）")

    if not violations and not optional_violations:
        print(u"未发现白名单外的模块导入")
        return 0

    known_debt, new_violations = split_by_debt(violations)

    print(u"")
    print(u"=== 运行结果 ===")
    print(u"  核心路径: 已知债务 {} 处，新增违规 {} 处".format(
        len(known_debt), len(new_violations)))
    print(u"  可选功能: {} 处（需显式调用才执行）".format(len(optional_violations)))

    if known_debt:
        print(u"")
        print(u"--- 已知债务（存量，无法在白名单口径确认前消除）---")
        by_module = {}
        for rel, line_no, module, _note in known_debt:
            by_module.setdefault(module, []).append((rel, line_no))
        for module in sorted(by_module):
            entries = by_module[module]
            print(u"  [存量] {}  共 {} 处".format(module, len(entries)))
            print(u"        {}".format(KNOWN_VIOLATIONS.get(module,
                                                           u"不在白名单内")))
            for rel, line_no in entries:
                print(u"        {}:{}".format(rel, line_no))

    if new_violations:
        print(u"")
        print(u"--- 新增违规（必须处理）---")
        for rel, line_no, module, _note in new_violations:
            print(u"  [新增] {}:{} 使用 {}".format(rel, line_no, module))

    if optional_violations:
        print(u"")
        print(u"--- 可选功能（标记为 {}）---".format(OPTIONAL_MARKER))
        by_module = {}
        for rel, line_no, module, _note in optional_violations:
            by_module.setdefault(module, []).append((rel, line_no))
        for module in sorted(by_module):
            entries = by_module[module]
            print(u"  [可选] {}  共 {} 处".format(module, len(entries)))
            for rel, line_no in entries:
                print(u"        {}:{}".format(rel, line_no))

    print(u"")
    print(u"官方提供的替代方案：")
    for key in sorted(OFFICIAL_ALTERNATIVES):
        print(u"  {} -> {}".format(key, OFFICIAL_ALTERNATIVES[key]))

    print(u"")
    if new_violations:
        print(u"发现 {} 处**新增**白名单违规，需要处理".format(len(new_violations)))
        return 1

    print(u"没有新增违规（已知债务 {} 处，可选功能 {} 处）".format(
        len(known_debt), len(optional_violations)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
