# -*- coding: utf-8 -*-
"""
θ 层自测：minecraft/core.py（基础类型）

真实依据（从反编译源码按引用次数统计）：
    Component.literal("...")                   40 次
    Component.translatable("itemGroup.…")      11 次
    Block.box(7.0, 12.0, 0.0, 9.0, 16.0, 16.0) 12 次
    InteractionResult.sidedSuccess(isClientSide) 9 次
    BlockPos.MutableBlockPos()                  6 次
    BlockPos.containing(vec3.x, vec3.y - 1e-6, vec3.z)
    BlockPos.randomInCube(random, 10, pos, 1)
    Vec3.atCenterOf(pos)

验证点：
  1. Component 的三种构造与翻译回退语义
  2. 翻译表装载与参数填充（%s / %N$s）
  3. InteractionResult.sidedSuccess 两端不同（不是布尔）
  4. BlockPos.containing 向下取整（负数易错）
  5. MutableBlockPos 的原地修改
  6. Vec3 的向量运算与 atCenterOf
  7. Direction 的步进与反向
  8. AABB 由两个角构造、相交与包含判断
  9. 名称映射表
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary  # noqa: E402

pkg = Package()
mc = pkg.load("minecraft.core")
util = pkg.load("java_stdlib.util")


def raises(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
        return False
    except Exception:
        return True


try:
    # ------------------------------------------------------------
    section("Component：三种构造")
    # ------------------------------------------------------------
    mc.Component.clearTranslations()

    literal = mc.Component.literal(u"ManaitaPlus")
    check(u"literal 直接给文本", literal.getString() == u"ManaitaPlus",
          literal.getString())
    check(u"literal 的 kind 正确", literal.kind == u"literal")

    empty = mc.Component.empty()
    check(u"empty 是空串", empty.getString() == u"")

    key = mc.Component.translatable(u"itemGroup.ManaitaPlusTab")
    check(u"translatable 记录翻译键",
          key.text == u"itemGroup.ManaitaPlusTab", key.text)
    check(u"翻译键查不到时回退为键本身",
          key.getString() == u"itemGroup.ManaitaPlusTab", key.getString())

    check(u"nullToEmpty(None) 得到空组件",
          mc.Component.nullToEmpty(None).getString() == u"")
    check(u"nullToEmpty(组件) 原样返回",
          mc.Component.nullToEmpty(literal) is literal)

    # ------------------------------------------------------------
    section("Component：翻译表与参数填充")
    # ------------------------------------------------------------
    loaded = mc.Component.loadFromLangFile({
        u"itemGroup.ManaitaPlusTab": u"砧板传承",
        u"block.manaita.crafting": u"%s 的合成砧板",
        u"multi.args": u"%1$s 与 %2$s",
        u"not.a.string": 12345,
    })
    check(u"只装载字符串值", loaded == 3, loaded)

    check(u"翻译键命中后返回译文",
          mc.Component.translatable(u"itemGroup.ManaitaPlusTab").getString()
          == u"砧板传承",
          mc.Component.translatable(u"itemGroup.ManaitaPlusTab").getString())

    with_arg = mc.Component.translatable(u"block.manaita.crafting", u"钻石")
    check(u"%s 参数被填充", with_arg.getString() == u"钻石 的合成砧板",
          with_arg.getString())

    positioned = mc.Component.translatable(u"multi.args", u"A", u"B")
    check(u"%N$s 位置参数被填充", positioned.getString() == u"A 与 B",
          positioned.getString())

    missing_arg = mc.Component.translatable(u"block.manaita.crafting")
    check(u"参数不足时保留占位符（不抛异常）",
          u"%s" in missing_arg.getString(), missing_arg.getString())

    check(u"非字典载入报错",
          raises(mc.Component.loadFromLangFile, [u"not", u"a", u"dict"]))

    mc.Component.clearTranslations()
    check(u"清空后回退为键",
          mc.Component.translatable(u"x").getString() == u"x")

    # 相等语义
    check(u"同内容组件相等",
          mc.Component.literal(u"a") == mc.Component.literal(u"a"))
    check(u"不同内容组件不等",
          mc.Component.literal(u"a") != mc.Component.literal(u"b"))
    check(u"组件可作字典键",
          {mc.Component.literal(u"a"): 1}[mc.Component.literal(u"a")] == 1)

    # ------------------------------------------------------------
    section("InteractionResult：sidedSuccess 两端不同")
    # ------------------------------------------------------------
    # 这是 Minecraft 的经典约定：客户端 SUCCESS、服务端 CONSUME。
    # 简化成一个布尔会导致双端重复处理 —— 所以必须分开。
    client_result = mc.InteractionResult.sidedSuccess(True)
    server_result = mc.InteractionResult.sidedSuccess(False)
    check(u"客户端得到 SUCCESS",
          client_result is mc.InteractionResult.SUCCESS, client_result)
    check(u"服务端得到 CONSUME",
          server_result is mc.InteractionResult.CONSUME, server_result)
    check(u"两端结果确实不同", client_result is not server_result)

    check(u"PASS 常量存在",
          mc.InteractionResult.PASS.name() == u"PASS")
    check(u"FAIL 常量存在", mc.InteractionResult.FAIL.name() == u"FAIL")
    check(u"SUCCESS 不等于 CONSUME",
          mc.InteractionResult.SUCCESS != mc.InteractionResult.CONSUME)
    check(u"按身份比较",
          (mc.InteractionResult.SUCCESS == mc.InteractionResult.SUCCESS) is True)
    check(u"valueOf 能取回", mc.InteractionResult.valueOf(u"PASS")
          is mc.InteractionResult.PASS)
    check(u"valueOf 未命中抛异常", raises(mc.InteractionResult.valueOf, u"NOPE"))
    check(u"values 有 4 个", len(mc.InteractionResult.values()) == 4,
          len(mc.InteractionResult.values()))

    check(u"InteractionHand.MAIN_HAND", mc.InteractionHand.MAIN_HAND.name()
          == u"MAIN_HAND")
    check(u"两只手不同", mc.InteractionHand.MAIN_HAND
          is not mc.InteractionHand.OFF_HAND)

    # ------------------------------------------------------------
    section("BlockPos.containing：向下取整（负数易错）")
    # ------------------------------------------------------------
    # 这条语义关键：-0.5 应落在 -1，而不是 0（截断）也不是 -1（四舍五入巧合）
    pos = mc.BlockPos.containing(1.7, 2.2, 3.9)
    check(u"正数向下取整",
          (pos.getX(), pos.getY(), pos.getZ()) == (1, 2, 3),
          (pos.getX(), pos.getY(), pos.getZ()))

    neg = mc.BlockPos.containing(-0.5, -1.2, -3.9)
    check(u"负数向下取整（-0.5 -> -1）",
          (neg.getX(), neg.getY(), neg.getZ()) == (-1, -2, -4),
          (neg.getX(), neg.getY(), neg.getZ()))

    check(u"整数坐标不变",
          mc.BlockPos.containing(5.0, 6.0, 7.0).getY() == 6)

    from_vec = mc.BlockPos.containing(mc.Vec3(1.9, -0.1, 2.5))
    check(u"接受 Vec3 参数",
          (from_vec.getX(), from_vec.getY(), from_vec.getZ()) == (1, -1, 2),
          (from_vec.getX(), from_vec.getY(), from_vec.getZ()))

    # ------------------------------------------------------------
    section("BlockPos：偏移与方向")
    # ------------------------------------------------------------
    origin = mc.BlockPos(1, 2, 3)
    check(u"offset 三参",
          tuple(origin.offset(1, 1, 1)) == (2, 3, 4), tuple(origin.offset(1, 1, 1)))
    check(u"offset 传 Vec3i",
          tuple(origin.offset(mc.BlockPos(1, 0, 0))) == (2, 2, 3))
    check(u"offset 传 Direction",
          tuple(origin.offset(mc.Direction.UP)) == (1, 3, 3))
    check(u"above/below", tuple(origin.above(2)) == (1, 4, 3)
          and tuple(origin.below()) == (1, 1, 3))
    check(u"east/west", tuple(origin.east()) == (2, 2, 3)
          and tuple(origin.west()) == (0, 2, 3))
    check(u"north/south", tuple(origin.north()) == (1, 2, 2)
          and tuple(origin.south()) == (1, 2, 4))
    check(u"relative 带距离",
          tuple(origin.relative(mc.Direction.EAST, 3)) == (4, 2, 3),
          tuple(origin.relative(mc.Direction.EAST, 3)))
    check(u"offset 不改动原对象",
          (origin.getX(), origin.getY(), origin.getZ()) == (1, 2, 3),
          tuple(origin))
    check(u"distSqr", mc.BlockPos(1, 2, 2).distSqr() == 9,
          mc.BlockPos(1, 2, 2).distSqr())

    # 类型必须保持 BlockPos，不能退化成 Vec3i。
    # 实测踩到：relative/offset 继承自 Vec3i 返回 Vec3i，
    # 于是 `blockpos.relative(dir)` 传进只收 BlockPos 的方法就被拒绝
    # （"位置参数应是 BlockPos 或三元组，收到 Vec3i"）。
    # 光断言坐标值抓不到这个 —— 所以这里专门断言类型。
    check(u"offset 返回 BlockPos（类型不退化）",
          isinstance(origin.offset(1, 1, 1), mc.BlockPos),
          type(origin.offset(1, 1, 1)).__name__)
    check(u"relative 返回 BlockPos",
          isinstance(origin.relative(mc.Direction.UP), mc.BlockPos),
          type(origin.relative(mc.Direction.UP)).__name__)
    check(u"above 返回 BlockPos",
          isinstance(origin.above(), mc.BlockPos))
    check(u"below 返回 BlockPos",
          isinstance(origin.below(), mc.BlockPos))
    check(u"east 返回 BlockPos", isinstance(origin.east(), mc.BlockPos))
    check(u"north 返回 BlockPos", isinstance(origin.north(), mc.BlockPos))
    # 反过来：Vec3i 的偏移仍然返回 Vec3i（不被 BlockPos 的实现带偏）
    check(u"Vec3i.relative 仍返回 Vec3i",
          type(mc.Vec3i(1, 2, 3).relative(mc.Direction.UP)) is mc.Vec3i,
          type(mc.Vec3i(1, 2, 3).relative(mc.Direction.UP)).__name__)

    check(u"相等比较",
          mc.BlockPos(1, 2, 3) == mc.BlockPos(1, 2, 3))
    check(u"不相等的坐标",
          mc.BlockPos(1, 2, 3) != mc.BlockPos(3, 2, 1))
    check(u"可作字典键",
          {mc.BlockPos(1, 2, 3): u"v"}[mc.BlockPos(1, 2, 3)] == u"v")
    check(u"toString 形态",
          mc.BlockPos(1, 2, 3).toString() == u"(1, 2, 3)",
          mc.BlockPos(1, 2, 3).toString())
    check(u"ZERO 常量", tuple(mc.BlockPos.ZERO) == (0, 0, 0))
    check(u"可解包成三元组", tuple(mc.BlockPos(4, 5, 6)) == (4, 5, 6))

    # ------------------------------------------------------------
    section("MutableBlockPos：原地修改")
    # ------------------------------------------------------------
    mutable = mc.BlockPos.mutable()
    check(u"mutable() 得到 MutableBlockPos",
          isinstance(mutable, mc.MutableBlockPos), type(mutable).__name__)

    returned = mutable.set(1, 2, 3)
    check(u"set 返回自身（可链式）", returned is mutable)
    check(u"set 生效", tuple(mutable) == (1, 2, 3), tuple(mutable))

    mutable.set(mc.BlockPos(4, 5, 6))
    check(u"set(Vec3i) 生效", tuple(mutable) == (4, 5, 6), tuple(mutable))

    mutable.move(mc.Direction.EAST, 2)
    check(u"move 原地偏移", tuple(mutable) == (6, 5, 6), tuple(mutable))

    mutable.setX(9)
    check(u"setX", mutable.getX() == 9)

    # 对比：不可变的 BlockPos 偏移后是新对象
    fixed = mc.BlockPos(0, 0, 0)
    shifted = fixed.east()
    check(u"BlockPos 偏移产生新对象", shifted is not fixed)
    check(u"原对象未被改动", tuple(fixed) == (0, 0, 0), tuple(fixed))

    # ------------------------------------------------------------
    section("BlockPos.randomInCube")
    # ------------------------------------------------------------
    random_source = util.JavaRandom(12345)
    center = mc.BlockPos(0, 0, 0)
    sample = mc.BlockPos.randomInCube(random_source, 10, center, 1)
    check(u"返回 BlockPos", isinstance(sample, mc.BlockPos))
    check(u"落在立方体范围内",
          -10 <= sample.getX() <= 10 and -10 <= sample.getY() <= 10
          and -10 <= sample.getZ() <= 10,
          tuple(sample))

    same_seed_a = mc.BlockPos.randomInCube(util.JavaRandom(7), 5, center, 1)
    same_seed_b = mc.BlockPos.randomInCube(util.JavaRandom(7), 5, center, 1)
    check(u"同种子结果可复现", tuple(same_seed_a) == tuple(same_seed_b),
          (tuple(same_seed_a), tuple(same_seed_b)))

    check(u"radius<=0 返回 None",
          mc.BlockPos.randomInCube(random_source, 0, center, 1) is None)
    check(u"缺随机源报错",
          raises(mc.BlockPos.randomInCube, None, 5, center, 1))

    # ------------------------------------------------------------
    section("BlockPos：getCenter / asLong")
    # ------------------------------------------------------------
    center_vec = mc.BlockPos(1, 2, 3).getCenter()
    check(u"getCenter 是方块中心",
          (center_vec.x, center_vec.y, center_vec.z) == (1.5, 2.5, 3.5),
          center_vec.toString())

    packed_a = mc.BlockPos(1, 2, 3).asLong()
    packed_b = mc.BlockPos(1, 2, 3).asLong()
    check(u"asLong 稳定", packed_a == packed_b and isinstance(packed_a, int),
          packed_a)
    check(u"不同坐标打包不同",
          mc.BlockPos(1, 2, 3).asLong() != mc.BlockPos(3, 2, 1).asLong())

    # ------------------------------------------------------------
    section("Vec3")
    # ------------------------------------------------------------
    check(u"atCenterOf 加 0.5",
          mc.Vec3.atCenterOf(mc.BlockPos(1, 2, 3)).toString() == u"(1.5, 2.5, 3.5)",
          mc.Vec3.atCenterOf(mc.BlockPos(1, 2, 3)).toString())
    check(u"atLowerCornerOf 不加",
          mc.Vec3.atLowerCornerOf(mc.BlockPos(1, 2, 3)).toString()
          == u"(1.0, 2.0, 3.0)",
          mc.Vec3.atLowerCornerOf(mc.BlockPos(1, 2, 3)).toString())

    a = mc.Vec3(1.0, 2.0, 3.0)
    b = mc.Vec3(4.0, 6.0, 8.0)
    check(u"x/y/z 是公开属性（真实代码直接读）",
          (a.x, a.y, a.z) == (1.0, 2.0, 3.0), (a.x, a.y, a.z))

    check(u"add", a.add(b).toString() == u"(5.0, 8.0, 11.0)", a.add(b).toString())
    check(u"subtract", b.subtract(a).toString() == u"(3.0, 4.0, 5.0)")
    check(u"scale", a.scale(2).toString() == u"(2.0, 4.0, 6.0)")
    check(u"dot", a.dot(b) == 4.0 + 12.0 + 24.0, a.dot(b))
    check(u"lengthSqr", a.lengthSqr() == 14.0, a.lengthSqr())
    check(u"distanceToSqr", mc.Vec3.ZERO.distanceToSqr(mc.Vec3(3, 4, 0)) == 25.0)
    check(u"normalize 得到单位长度",
          abs(a.normalize().length() - 1.0) < 1e-9, a.normalize().length())
    check(u"零向量 normalize 返回 ZERO",
          mc.Vec3.ZERO.normalize() is mc.Vec3.ZERO)
    check(u"cross 正交",
          a.cross(b).dot(a) == 0.0, a.cross(b).dot(a))
    check(u"horizontalDistanceSqr 忽略 y",
          mc.Vec3(3, 100, 4).horizontalDistanceSqr() == 25.0)
    check(u"ZERO 常量", mc.Vec3.ZERO.toString() == u"(0.0, 0.0, 0.0)")

    check(u"相等比较", mc.Vec3(1, 2, 3) == mc.Vec3(1.0, 2.0, 3.0))
    check(u"可解包", tuple(mc.Vec3(1, 2, 3)) == (1.0, 2.0, 3.0))
    check(u"运算符 + 可用", (mc.Vec3(1, 1, 1) + mc.Vec3(2, 2, 2)).x == 3.0)
    check(u"运算符 - 可用", (mc.Vec3(3, 3, 3) - mc.Vec3(1, 1, 1)).y == 2.0)

    # ------------------------------------------------------------
    section("Direction")
    # ------------------------------------------------------------
    check(u"UP 的步进是 (0,1,0)",
          (mc.Direction.UP.getStepX(), mc.Direction.UP.getStepY(),
           mc.Direction.UP.getStepZ()) == (0, 1, 0))
    check(u"EAST 的步进是 (1,0,0)", mc.Direction.EAST.getStepX() == 1)
    check(u"getNormal 与步进一致",
          mc.Direction.NORTH.getNormal() == (0, 0, -1),
          mc.Direction.NORTH.getNormal())
    check(u"getOpposite 正确",
          mc.Direction.UP.getOpposite() is mc.Direction.DOWN,
          mc.Direction.UP.getOpposite())
    check(u"反向的反向是自身",
          mc.Direction.EAST.getOpposite().getOpposite() is mc.Direction.EAST)
    check(u"values 有 6 个", len(mc.Direction.values()) == 6)
    check(u"valueOfJavaName", mc.Direction.valueOfJavaName(u"north")
          is mc.Direction.NORTH)
    check(u"valueOfJavaName 未命中报错",
          raises(mc.Direction.valueOfJavaName, u"MIDDLE"))
    check(u"按身份比较",
          (mc.Direction.UP == mc.Direction.UP) is True
          and (mc.Direction.UP == mc.Direction.DOWN) is False)

    # ------------------------------------------------------------
    section("AABB：由两个角构造")
    # ------------------------------------------------------------
    # 对应 Block.box(7.0, 12.0, 0.0, 9.0, 16.0, 16.0)
    box = mc.AABB.box(7.0, 12.0, 0.0, 9.0, 16.0, 16.0)
    check(u"尺寸由两角差决定",
          (box.getXSize(), box.getYSize(), box.getZSize()) == (2.0, 4.0, 16.0),
          (box.getXSize(), box.getYSize(), box.getZSize()))

    reversed_box = mc.AABB.box(9.0, 16.0, 16.0, 7.0, 12.0, 0.0)
    check(u"两个角顺序颠倒也能正确归一",
          (reversed_box.minX, reversed_box.maxY) == (7.0, 16.0),
          (reversed_box.minX, reversed_box.maxY))

    check(u"contains 判断", box.contains(8.0, 14.0, 8.0) is True)
    check(u"contains 边界外为假", box.contains(6.9, 14.0, 8.0) is False)
    check(u"contains 接受 Vec3",
          box.contains(mc.Vec3(8.0, 14.0, 8.0)) is True)

    check(u"相交判断",
          box.intersects(mc.AABB.box(8.0, 13.0, 1.0, 10.0, 15.0, 2.0)) is True)
    check(u"不相交判断",
          box.intersects(mc.AABB.box(0.0, 0.0, 0.0, 1.0, 1.0, 1.0)) is False)

    check(u"inflate 扩大",
          mc.AABB.box(0, 0, 0, 1, 1, 1).inflate(1.0).getXSize() == 3.0)
    check(u"move 平移不改尺寸",
          box.move(1.0, 0.0, 0.0).getXSize() == box.getXSize())

    # ------------------------------------------------------------
    section("名称映射表")
    # ------------------------------------------------------------
    expected = [
        "net.minecraft.network.chat.Component",
        "net.minecraft.world.InteractionResult",
        "net.minecraft.world.InteractionHand",
        "net.minecraft.core.Direction",
        "net.minecraft.core.Vec3i",
        "net.minecraft.core.BlockPos",
        "net.minecraft.core.BlockPos$MutableBlockPos",
        "net.minecraft.world.phys.Vec3",
        "net.minecraft.world.phys.AABB",
    ]
    missing = [name for name in expected if name not in mc.JAVA_MAP]
    check(u"已实现的 θ 层类型都在映射表里", missing == [], missing)

    # 每个映射目标都能构造（冒烟）
    smoke = {
        mc.Component: (u"literal", u"x"),
        mc.InteractionResult: (),
        mc.InteractionHand: (),
        mc.Direction: (),
        mc.Vec3i: (0, 0, 0),
        mc.BlockPos: (0, 0, 0),
        mc.MutableBlockPos: (0, 0, 0),
        mc.Vec3: (0.0, 0.0, 0.0),
        mc.AABB: (0, 0, 0, 1, 1, 1),
    }
    failures = []
    for java_name, impl in mc.JAVA_MAP.items():
        if not isinstance(impl, type):
            failures.append(u"{}: 映射目标不是类".format(java_name))
            continue
        try:
            impl(*smoke.get(impl, ()))
        except Exception as error:
            failures.append(u"{}: {}".format(java_name, error))
    check(u"映射的类都能构造实例（冒烟）", failures == [], failures)

finally:
    mc.Component.clearTranslations()

sys.exit(summary())
