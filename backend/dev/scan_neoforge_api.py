# -*- coding: utf-8 -*-
"""
scan_neoforge_api —— 从反编译源码里抽出 NeoForge / Minecraft API 的真实用法清单

为什么要有这个工具
------------------
β 层（neoforge/）与 θ 层（minecraft/）该实现哪些类、哪些方法，
不该凭印象决定。反编译出来的 125 个 .java 是**真实用例**，
把它扫一遍就能得到准确的优先级表，也顺带得到一份「缺口检查表」：
每实现一批就回来看还有哪些没覆盖。

用法
----
    python dev/scan_neoforge_api.py             # 打印摘要
    python dev/scan_neoforge_api.py --detail    # 打印完整清单
"""

import io
import os
import re
import collections
import sys

DEV_ROOT = os.path.dirname(os.path.abspath(__file__))
from workspace_paths import PACK_ROOT as _PACK_ROOT
PACK_ROOT = str(_PACK_ROOT)
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(PACK_ROOT))

DECOMPILED_ROOT = os.path.join(WORKSPACE_ROOT, "refs", "decompiled")

# 按命名空间分组统计
NAMESPACES = (
    ("neoforge", u"net.neoforged"),
    ("minecraft", u"net.minecraft"),
    ("mojang", u"com.mojang"),
    ("fastutil", u"it.unimi"),
)

# 抓 Class.method( 形式
_CALL_RE = re.compile(r'\b([A-Z][A-Za-z0-9_]*)\s*\.\s*([a-zA-Z_]\w*)\s*\(')
# 抓 new Class<...>( 与 Class.field
_IMPORT_RE = re.compile(r'^\s*import\s+([\w\.\$]+)\s*;', re.MULTILINE)


def find_decompiled_root():
    if not os.path.isdir(DECOMPILED_ROOT):
        return None
    for name in sorted(os.listdir(DECOMPILED_ROOT)):
        candidate = os.path.join(DECOMPILED_ROOT, name)
        if os.path.isdir(candidate):
            return candidate
    return None


def collect(root):
    imports = collections.Counter()
    static_calls = collections.Counter()
    own_calls = collections.Counter()
    files = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(dirnames)
        for name in sorted(filenames):
            if not name.endswith(".java"):
                continue
            files += 1
            path = os.path.join(dirpath, name)
            text = io.open(path, "r", encoding="utf-8", errors="replace").read()

            for imported in _IMPORT_RE.findall(text):
                imports[imported] += 1

            for cls, method in _CALL_RE.findall(text):
                static_calls[(cls, method)] += 1

    return files, imports, static_calls


def group_imports(imports):
    grouped = collections.OrderedDict()
    for key, _prefix in NAMESPACES:
        grouped[key] = collections.Counter()
    grouped["other"] = collections.Counter()

    for imported, count in imports.items():
        for key, prefix in NAMESPACES:
            if imported.startswith(prefix):
                grouped[key][imported] = count
                break
        else:
            grouped["other"][imported] = count
    return grouped


def main():
    detail = "--detail" in sys.argv

    root = find_decompiled_root()
    if root is None:
        print(u"找不到反编译结果，请先运行：python dev/decompile_mod.py")
        return 1

    print(u"源码目录: {}".format(root))
    files, imports, static_calls = collect(root)
    print(u".java 文件数: {}".format(files))
    print(u"import 种类: {}".format(len(imports)))
    print(u"静态调用种类: {}".format(len(static_calls)))

    grouped = group_imports(imports)

    for key, _prefix in NAMESPACES:
        counter = grouped[key]
        print(u"")
        print(u"=== {} 命名空间的 import（共 {} 种，前 20）===".format(
            key, len(counter)))
        for name, count in counter.most_common(20):
            print(u"  {:<70} {}".format(name, count))

    print(u"")
    print(u"=== 其它 import（前 15）===")
    for name, count in grouped["other"].most_common(15):
        print(u"  {:<70} {}".format(name, count))

    if detail:
        print(u"")
        print(u"=== 全部静态/类方法调用（前 80）===")
        for (cls, method), count in static_calls.most_common(80):
            print(u"  {:<24}.{:<28} {}".format(cls, method, count))

    return 0


if __name__ == "__main__":
    sys.exit(main())
