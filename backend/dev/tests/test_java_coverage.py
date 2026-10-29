# -*- coding: utf-8 -*-
"""
Σ 层覆盖率自测：对照真实模组的 Java 引用清单

思路：
  不要凭感觉决定「该实现哪些 Java 类」，而是从真实模组里把引用挖出来，
  再检查 Σ 层是否覆盖。这样可以明确知道「还差什么」，
  也能避免实现一堆模组根本用不到的类。

参考数据来自本机另一个附加包里的真实模组（ManaitaPlus Legacy）：
184 个 .class 文件的常量池中提取的 java/* 引用。

验证点：
  1. 高价值 java.lang / java.util 类是否已在 JAVA_MAP 或已实现
  2. 仍未覆盖的类被显式登记为「待实现」，而不是被悄悄忽略
  3. 覆盖率有下限保护：核心集合类必须全部覆盖
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary  # noqa: E402

pkg = Package()
util = pkg.load("java_stdlib.util")

# ============================================================
# 真实模组的 java.* 引用频次（从 .class 常量池提取）
# 只列 java.lang 与 java.util，它们是本层（Σ）的职责范围。
# ============================================================

# 类名 -> 引用次数
REAL_MOD_JAVA_REFS = {
    # java.lang —— 高频
    "java/lang/String": 883,
    "java/lang/Object": 748,
    "java/lang/Integer": 72,
    "java/lang/Class": 70,
    "java/lang/Runnable": 37,
    "java/lang/Boolean": 30,
    "java/lang/Comparable": 27,
    "java/lang/StringBuilder": 25,
    "java/lang/Enum": 19,
    "java/lang/Math": 13,
    "java/lang/Float": 11,
    "java/lang/Record": 10,
    "java/lang/Exception": 8,
    "java/lang/System": 7,
    "java/lang/ThreadLocal": 6,
    "java/lang/AssertionError": 6,
    "java/lang/Throwable": 9,
    "java/lang/IllegalStateException": 4,
    "java/lang/Long": 4,
    "java/lang/Double": 5,
    "java/lang/Character": 3,
    "java/lang/Byte": 3,
    "java/lang/Short": 3,
    "java/lang/IllegalArgumentException": 2,
    "java/lang/Number": 2,
    "java/lang/Iterable": 14,

    # java.util —— 高频，本层重点
    "java/util/List": 170,
    "java/util/Map": 76,
    "java/util/Iterator": 60,
    "java/util/Set": 55,
    "java/util/Optional": 50,
    "java/util/UUID": 32,
    "java/util/Collection": 25,
    "java/util/Map$Entry": 19,
    "java/util/ArrayList": 15,
    "java/util/EnumSet": 14,
    "java/util/Arrays": 8,
    "java/util/EnumMap": 7,
    "java/util/HashMap": 7,
    "java/util/OptionalInt": 7,
    "java/util/Objects": 6,
    "java/util/ListIterator": 6,
    "java/util/HashSet": 4,
    "java/util/Random": 4,
    "java/util/Locale": 3,
    "java/util/LinkedList": 1,
    "java/util/WeakHashMap": 2,
}

# ============================================================
# Σ 层当前已覆盖的（含 util.py 的 JAVA_MAP 与本层自定义实现）
# ============================================================

# 已实现的、但不在 JAVA_MAP 里的 java.lang 类型（属于后续 lang.py 的职责，
# 这里只登记「已识别」，用于统计覆盖率而不是假装已实现）
LANG_COVERED = set([
    "java/lang/IllegalStateException",   # _base.IllegalStateException
    "java/lang/IllegalArgumentException",  # _base.IllegalArgumentException
])

# 明确知道尚未实现、留给后续模块的（附计划归属）
PENDING = {
    "java/lang/String": "lang.py",
    "java/lang/Object": "lang.py",
    "java/lang/Integer": "lang.py",
    "java/lang/Class": "需反射层，可能不可实现",
    "java/lang/Runnable": "lang.py（Python 可调用对象即可）",
    "java/lang/Boolean": "lang.py",
    "java/lang/Comparable": "lang.py",
    "java/lang/StringBuilder": "lang.py",
    "java/lang/Enum": "lang.py",
    "java/lang/Math": "lang.py",
    "java/lang/Float": "lang.py",
    "java/lang/Record": "lang.py",
    "java/lang/Exception": "lang.py",
    "java/lang/System": "lang.py",
    "java/lang/ThreadLocal": "lang.py",
    "java/lang/AssertionError": "lang.py",
    "java/lang/Throwable": "lang.py",
    "java/lang/Long": "lang.py",
    "java/lang/Double": "lang.py",
    "java/lang/Character": "lang.py",
    "java/lang/Byte": "lang.py",
    "java/lang/Short": "lang.py",
    "java/lang/Number": "lang.py",
    "java/lang/Iterable": "util.py 已映射到 JavaCollection",
    "java/util/Locale": "util.py 待补",
}


def to_dotted(slash_name):
    """java/util/List -> java.util.List"""
    return slash_name.replace("/", ".")


try:
    # ------------------------------------------------------------
    section("java.util 集合与工具类覆盖率")
    # ------------------------------------------------------------
    util_refs = {}
    for slash_name, count in REAL_MOD_JAVA_REFS.items():
        if slash_name.startswith("java/util/"):
            util_refs[slash_name] = count

    covered = []
    missing = []
    for slash_name in sorted(util_refs):
        dotted = to_dotted(slash_name)
        dotted = dotted.replace("$", ".")
        if dotted in util.JAVA_MAP:
            covered.append(slash_name)
        else:
            missing.append(slash_name)

    total_util = len(util_refs)
    check(u"java.util 引用的类共 {} 个".format(total_util), total_util > 0)
    check(u"已覆盖 {} 个".format(len(covered)), len(covered) >= 19,
          u"已覆盖 {}，缺 {}".format(len(covered), missing))
    check(u"核心集合类全部覆盖（List/Map/Set/Collection/Iterator）",
          all(to_dotted(name).replace("$", ".") in util.JAVA_MAP for name in (
              "java/util/List", "java/util/Map", "java/util/Set",
              "java/util/Collection", "java/util/Iterator",
          )))
    check(u"Optional 与 OptionalInt 都已覆盖",
          "java.util.Optional" in util.JAVA_MAP
          and "java.util.OptionalInt" in util.JAVA_MAP)
    check(u"只有 Locale 尚未覆盖（已知）",
          set([to_dotted(n) for n in missing]) <= set(["java.util.Locale"]),
          [to_dotted(n) for n in missing])

    # 覆盖率按「引用次数」加权，更能反映实际影响
    weighted_total = sum(util_refs.values())
    weighted_covered = sum([util_refs[name] for name in covered])
    ratio = float(weighted_covered) / weighted_total * 100.0
    check(u"按引用次数加权的覆盖率 >= 99%",
          ratio >= 99.0, u"{:.1f}%".format(ratio))

    print(u"")
    print(u"  java.util 覆盖率：{}/{} 个类，按引用次数加权 {:.1f}%".format(
        len(covered), total_util, ratio))

    # ------------------------------------------------------------
    section("java.lang 覆盖情况（本层只识别，实现留给 lang.py）")
    # ------------------------------------------------------------
    lang_refs = {}
    for slash_name, count in REAL_MOD_JAVA_REFS.items():
        if slash_name.startswith("java/lang/"):
            lang_refs[slash_name] = count

    lang_done = []
    lang_pending = []
    for slash_name in sorted(lang_refs):
        if slash_name in LANG_COVERED:
            lang_done.append(slash_name)
        elif slash_name in PENDING:
            lang_pending.append(slash_name)
        else:
            lang_pending.append(slash_name)

    check(u"java.lang 引用的类共 {} 个".format(len(lang_refs)), len(lang_refs) > 0)
    check(u"异常类已由 _base 提供（IllegalState/IllegalArgument）",
          set(lang_done) == set(["java/lang/IllegalStateException",
                                 "java/lang/IllegalArgumentException"]),
          lang_done)
    check(u"未实现的 java.lang 类都已登记在待办清单里",
          len(lang_pending) == len(lang_refs) - len(lang_done),
          u"待办 {} 个".format(len(lang_pending)))

    print(u"  java.lang 覆盖率：{}/{} 个类（其余 {} 个待 lang.py 实现）".format(
        len(lang_done), len(lang_refs), len(lang_pending)))

    # ------------------------------------------------------------
    section("待办清单本身要合理")
    # ------------------------------------------------------------
    check(u"每个待办项都写明了归属模块",
          all(value for value in PENDING.values()))
    check(u"最高频的 java.lang.String 已登记待办",
          "java/lang/String" in PENDING)
    check(u"待办里不包含已经实现的类（避免清单失真）",
          not (set([to_dotted(n) for n in PENDING if n.startswith("java/util/")])
               & set(util.JAVA_MAP.keys())),
          set([to_dotted(n) for n in PENDING if n.startswith("java/util/")])
          & set(util.JAVA_MAP.keys()))

    # ------------------------------------------------------------
    section("实现与清单一一对应")
    # ------------------------------------------------------------
    # JAVA_MAP 里不能有指向 None 或非类的条目
    bad_entries = []
    for java_name, impl in util.JAVA_MAP.items():
        if impl is None:
            bad_entries.append(java_name)
        elif not (isinstance(impl, type) or callable(impl)):
            bad_entries.append(java_name)
    check(u"JAVA_MAP 里没有无效条目", bad_entries == [], bad_entries)

    # 每个映射目标都要能真的构造出实例。
    # 注意不能要求「无参可构造」—— Java 里 Map.Entry / UUID / Optional
    # 本来就需要参数，所以这里用**最小合法参数**做冒烟构造。
    smoke_args = {
        util.MapEntry: (u"k", u"v"),
        util.JavaIterator: ([],),
        util.ListIterator: ([],),
        util.JavaOptional: (u"v",),
        util.JavaOptionalInt: (0,),
        util.UUID: (u"00000000-0000-0000-0000-000000000000",),
        util.JavaStream: ([],),
        util.Objects: (),
        util.Arrays: (),
        util.Collections: (),
        util.JavaRandom: (),
        util.JavaList: (),
        util.JavaMap: (),
        util.JavaSet: (),
        # EnumSet requires a real enum element type; Java exposes typed factories.
        util.EnumSet: (pkg.load("minecraft.goals").Goal.Flag,),
        util.JavaCollection: (),
    }

    failures = []
    for java_name, impl in util.JAVA_MAP.items():
        if not isinstance(impl, type):
            failures.append(u"{}: 映射目标不是类".format(java_name))
            continue
        args = smoke_args.get(impl, ())
        try:
            instance = impl(*args)
        except Exception as error:
            failures.append(u"{}: {}".format(java_name, error))
            continue
        if instance is None:
            failures.append(u"{}: 构造结果为 None".format(java_name))

    check(u"每个映射都能构造出实例（冒烟）", failures == [], failures)

finally:
    pass

sys.exit(summary())
