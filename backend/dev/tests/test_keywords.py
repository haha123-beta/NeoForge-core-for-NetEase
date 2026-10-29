# -*- coding: utf-8 -*-
"""
θ/β 层自测：Python 关键字冲突与相关类型

这一批东西是被**扫描**发现的，不是凭空设计的：
    .is()   28 处  -> ItemStack.isItem      （minecraft/item.py）
    .pass()  7 处  -> EventResult.passResult（neoforge/common.py）
    .or()    4 处  -> Shapes.orShapes       （minecraft/shapes.py）

为什么必须处理：
    Java 里 `itemStack.is(x)` / `EventResult.pass()` / `Shapes.or(a, b)`
    翻译成 Python 全是**语法错误**（is / pass / or 都是关键字）。
    这不是运行时问题 —— 函数体里写任何兼容代码都绕不过解析器，
    只能在命名层改名。

验证点：
  1. 核心包没有任何以关键字命名的函数（会让整个模块无法解析）
  2. 改名映射表覆盖扫描发现的所有冲突
  3. rename_method 的精确/全局优先级
  4. VoxelShape（Shapes.orShapes / andShapes 的几何语义）
  5. EventResult / TriState
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary  # noqa: E402

pkg = Package()
mc = pkg.load("minecraft.core")
item_mod = pkg.load("minecraft.item")
shapes = pkg.load("minecraft.shapes")
common = pkg.load("neoforge.common")
renames = pkg.load("core.keyword_renames")

DEV_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from workspace_paths import SCRIPTS_ROOT as _SCRIPTS_ROOT
SCRIPTS_ROOT = str(_SCRIPTS_ROOT)


def raises(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
        return False
    except Exception:
        return True


try:
    # ------------------------------------------------------------
    section("核心包不能定义关键字函数名")
    # ------------------------------------------------------------
    # 这种定义会让整个文件 SyntaxError —— 连导入都做不到。
    # 用 keyword_lint 的扫描器直接查，而不是靠人工看。
    sys.path.insert(0, DEV_ROOT)
    import keyword_lint

    bad_defs = keyword_lint.scan_python_for_keyword_defs(SCRIPTS_ROOT)
    check(u"核心包没有关键字函数名", bad_defs == [], bad_defs)

    # 所有模块都能被真正导入（等价于「没有语法错误」）
    loaded = []
    for module_name in (u"minecraft.core", u"minecraft.item",
                        u"minecraft.shapes", u"neoforge.common",
                        u"core.keyword_renames"):
        try:
            pkg.load(module_name)
            loaded.append(module_name)
        except Exception:
            pass
    check(u"新增模块都能导入", len(loaded) == 5, loaded)

    # ------------------------------------------------------------
    section("改名映射表")
    # ------------------------------------------------------------
    check(u"类精确映射优先于全局映射",
          renames.rename_method("net.minecraft.world.item.ItemStack", "is")
          == u"isItem",
          renames.rename_method("net.minecraft.world.item.ItemStack", "is"))
    check(u"Shapes.or 改为 orShapes",
          renames.rename_method("net.minecraft.world.phys.shapes.Shapes", "or")
          == u"orShapes")
    check(u"EventResult.pass 改为 passResult",
          renames.rename_method("net.neoforged.neoforge.common.util.EventResult",
                                "pass") == u"passResult")
    check(u"未登记的类走全局映射",
          renames.rename_method("some.unknown.Class", "is") == u"isItem")
    check(u"不冲突的方法名原样返回",
          renames.rename_method("some.Class", "getItem") == u"getItem",
          renames.rename_method("some.Class", "getItem"))

    check(u"is_keyword 认得 is", renames.is_keyword(u"is") is True)
    check(u"is_keyword 认得 pass", renames.is_keyword(u"pass") is True)
    check(u"is_keyword 认得 or", renames.is_keyword(u"or") is True)
    check(u"is_keyword 认得 Py3 独有的 nonlocal",
          renames.is_keyword(u"nonlocal") is True)
    check(u"is_keyword 对普通名返回假",
          renames.is_keyword(u"getItem") is False)

    # 扫描发现的三类冲突都必须有处理方式
    for keyword_name in (u"is", u"pass", u"or"):
        check(u"改名表覆盖 .{}()".format(keyword_name),
              keyword_name in renames.GLOBAL_RENAMES,
              renames.GLOBAL_RENAMES.get(keyword_name))

    described = renames.describe()
    check(u"describe 给出可读清单", len(described) > 0, len(described))

    # 改名后的方法必须真的存在
    check(u"ItemStack.isItem 存在",
          hasattr(item_mod.ItemStack, u"isItem"))
    check(u"EventResult.passResult 存在",
          hasattr(common.EventResult, u"passResult"))
    check(u"VoxelShape.orShapes 存在",
          hasattr(shapes.VoxelShape, u"orShapes"))

    # ------------------------------------------------------------
    section("VoxelShape：Shapes.orShapes 并集")
    # ------------------------------------------------------------
    # 对应真实代码：Shapes.or(shapeSOUTH, shapeN)
    south = shapes.VoxelShape.box(0.0, 0.0, 14.0, 16.0, 16.0, 16.0)
    north = shapes.VoxelShape.box(0.0, 0.0, 0.0, 16.0, 16.0, 2.0)
    check(u"单个 box 形状有 1 个箱体", south.size() == 1, south.size())

    union = shapes.VoxelShape.orShapes(south, north)
    check(u"并集有 2 个箱体", union.size() == 2, union.size())
    check(u"并集不空", union.isEmpty() is False)

    single = shapes.VoxelShape.box(0.0, 0.0, 0.0, 1.0, 1.0, 1.0)
    check(u"orShapes 单个参数返回原对象（与 Java 一致）",
          shapes.VoxelShape.orShapes(single) is single)
    check(u"orShapes 忽略 None",
          shapes.VoxelShape.orShapes(single, None).size() == 1)
    check(u"orShapes 参数类型不对报错",
          raises(shapes.VoxelShape.orShapes, single, u"not_a_shape"))

    check(u"empty 形状为空", shapes.VoxelShape.empty().isEmpty() is True)
    check(u"block 形状占满整格",
          shapes.VoxelShape.block().bounds().getXSize() == 1.0)
    check(u"create 由一个 AABB 建形状",
          shapes.VoxelShape.create(
              mc.AABB.box(0, 0, 0, 1, 1, 1)).size() == 1)
    check(u"create 参数不对报错",
          raises(shapes.VoxelShape.create, u"not_an_aabb"))

    # bounds
    bounds = union.bounds()
    check(u"bounds 包住所有箱体",
          (bounds.minX, bounds.minZ, bounds.maxZ) == (0.0, 0.0, 16.0),
          (bounds.minX, bounds.minZ, bounds.maxZ))
    check(u"空形状的 bounds 是全 0 箱体（不是 None）",
          shapes.VoxelShape.empty().bounds().getXSize() == 0.0)

    # min / max
    check(u"min(X)", union.min(u"X") == 0.0, union.min(u"X"))
    check(u"max(X)", union.max(u"X") == 16.0, union.max(u"X"))
    check(u"min(Z)", union.min(u"Z") == 0.0, union.min(u"Z"))
    check(u"未知轴报错", raises(union.min, u"W"))
    check(u"空形状的 min 是 0", shapes.VoxelShape.empty().min(u"Y") == 0.0)

    # ------------------------------------------------------------
    section("VoxelShape：andShapes 交集")
    # ------------------------------------------------------------
    left = shapes.VoxelShape.box(0.0, 0.0, 0.0, 10.0, 10.0, 10.0)
    right = shapes.VoxelShape.box(5.0, 5.0, 5.0, 15.0, 15.0, 15.0)
    overlap = shapes.VoxelShape.andShapes(left, right)
    check(u"有交集时得到 1 个箱体", overlap.size() == 1, overlap.size())
    check(u"交集范围正确",
          (overlap.bounds().minX, overlap.bounds().maxX) == (5.0, 10.0),
          (overlap.bounds().minX, overlap.bounds().maxX))

    apart = shapes.VoxelShape.andShapes(
        shapes.VoxelShape.box(0.0, 0.0, 0.0, 1.0, 1.0, 1.0),
        shapes.VoxelShape.box(5.0, 5.0, 5.0, 6.0, 6.0, 6.0))
    check(u"不相交时交集为空", apart.isEmpty() is True, apart.size())

    # 面贴合不算相交（与 Minecraft 的 AABB.intersects 一致）
    touching = shapes.VoxelShape.andShapes(
        shapes.VoxelShape.box(0.0, 0.0, 0.0, 1.0, 1.0, 1.0),
        shapes.VoxelShape.box(1.0, 0.0, 0.0, 2.0, 1.0, 1.0))
    check(u"只贴合一个面不算相交", touching.isEmpty() is True, touching.size())

    check(u"andShapes 无参数返回空形状",
          shapes.VoxelShape.andShapes().isEmpty() is True)
    check(u"andShapes 参数不对报错",
          raises(shapes.VoxelShape.andShapes, left, u"nope"))

    # ------------------------------------------------------------
    section("VoxelShape：相交与包含")
    # ------------------------------------------------------------
    solid = shapes.VoxelShape.box(0.0, 0.0, 0.0, 16.0, 16.0, 16.0)
    check(u"intersects(AABB) 命中",
          solid.intersects(mc.AABB.box(1, 1, 1, 2, 2, 2)) is True)
    check(u"intersects(AABB) 未命中",
          solid.intersects(mc.AABB.box(20, 20, 20, 21, 21, 21)) is False)
    check(u"intersects 参数不对报错", raises(solid.intersects, u"nope"))

    check(u"intersectsShape 命中",
          solid.intersectsShape(
              shapes.VoxelShape.box(1, 1, 1, 2, 2, 2)) is True)
    check(u"intersectsShape 未命中",
          solid.intersectsShape(
              shapes.VoxelShape.box(50, 50, 50, 51, 51, 51)) is False)

    check(u"contains 内部点为真", solid.contains(8.0, 8.0, 8.0) is True)
    check(u"contains 外部点为假", solid.contains(99.0, 8.0, 8.0) is False)

    check(u"move 平移形状",
          solid.move(1.0, 0.0, 0.0).min(u"X") == 1.0,
          solid.move(1.0, 0.0, 0.0).min(u"X"))
    check(u"move 不改原形状", solid.min(u"X") == 0.0)

    # ------------------------------------------------------------
    section("EventResult / TriState")
    # ------------------------------------------------------------
    check(u"passResult 得到 PASS",
          common.EventResult.passResult() is common.EventResult.PASS,
          common.EventResult.passResult())
    check(u"allow 得到 ALLOW",
          common.EventResult.allow() is common.EventResult.ALLOW)
    check(u"deny 得到 DENY", common.EventResult.deny() is common.EventResult.DENY)
    check(u"四态互不相同",
          len(set([id(common.EventResult.DEFAULT), id(common.EventResult.ALLOW),
                   id(common.EventResult.DENY),
                   id(common.EventResult.PASS)])) == 4)
    check(u"valueOf 能取回",
          common.EventResult.valueOf(u"PASS") is common.EventResult.PASS)
    check(u"valueOf 未命中报错",
          raises(common.EventResult.valueOf, u"NOPE"))
    check(u"values 有 4 个", len(common.EventResult.values()) == 4)

    check(u"TriState.passResult 是 DEFAULT",
          common.TriState.passResult() is common.TriState.DEFAULT)
    check(u"fromBoolean(True) 是 TRUE",
          common.TriState.fromBoolean(True) is common.TriState.TRUE)
    check(u"fromBoolean(False) 是 FALSE",
          common.TriState.fromBoolean(False) is common.TriState.FALSE)
    check(u"toBoolean(TRUE) 为真",
          common.TriState.toBoolean(common.TriState.TRUE) is True)
    check(u"toBoolean(DEFAULT) 为假（不表态不等于同意）",
          common.TriState.toBoolean(common.TriState.DEFAULT) is False)

    # ------------------------------------------------------------
    section("名称映射表")
    # ------------------------------------------------------------
    for java_name in ("net.minecraft.world.phys.shapes.VoxelShape",
                      "net.minecraft.world.phys.shapes.Shapes"):
        check(u"shapes 映射 {}".format(java_name), java_name in shapes.JAVA_MAP)
    for java_name in ("net.neoforged.neoforge.common.util.EventResult",
                      "net.neoforged.neoforge.common.util.TriState"):
        check(u"common 映射 {}".format(java_name), java_name in common.JAVA_MAP)

finally:
    mc.Component.clearTranslations()

sys.exit(summary())
