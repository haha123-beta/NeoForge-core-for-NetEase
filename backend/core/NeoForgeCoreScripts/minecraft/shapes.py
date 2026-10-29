# -*- coding: utf-8 -*-
# minecraft/shapes.py
# θ 层：形状（VoxelShape / Shapes）
#
# 真实用法（从反编译源码逐字提取）：
#
#   // 方块碰撞箱：由 AABB 组合而成
#   public static final VoxelShape shapeAndS =
#       Shapes.or(shapeSOUTH, shapeN);
#
#   // 单个箱体由 Block.box 产出，再交给 Shapes.box / Shapes.create
#   Block.box(7.0, 12.0, 0.0, 9.0, 16.0, 16.0)
#
# **关键字冲突**：Java 写 `Shapes.or(a, b)`，但 `or` 是 Python 关键字，
# `Shapes.or(a, b)` 在 Python 里是语法错误。所以核心包里方法名是
# `orShapes`，改名约定见 core/keyword_renames.py（实测 4 处）。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from java_stdlib._base import IllegalArgumentException
    from java_stdlib.lang import java_to_string
    from minecraft.core import AABB
except ImportError:
    from _base import IllegalArgumentException  # type: ignore
    from lang import java_to_string  # type: ignore
    from core import AABB  # type: ignore


class VoxelShape(object):
    """
    对应 net.minecraft.world.phys.shapes.VoxelShape。

    它描述一个方块在空间里占据的体积，由若干 AABB 组成。
    Minecraft 用 DiscreteVoxelShape 做位图加速，本层只保留
    「一组箱体」这个语义 —— 够模组逻辑用（判断相交、取边界）。

    不可变：所有 orShapes/andShapes 都返回新对象（与 Java 一致）。
    """

    def __init__(self, boxes=None):
        self._boxes = list(boxes) if boxes else []

    # ---------------- 静态工厂 ----------------

    @staticmethod
    def create(box):
        """对应 Shapes.create(AABB)：由一个箱体建形状。"""
        if not isinstance(box, AABB):
            raise IllegalArgumentException(
                u"create 需要 AABB，收到 {}".format(type(box).__name__))
        return VoxelShape([box])

    @staticmethod
    def box(x1, y1, z1, x2, y2, z2):
        """对应 Shapes.box(...)：按两个角建单个箱体的形状。"""
        return VoxelShape([AABB.box(x1, y1, z1, x2, y2, z2)])

    @staticmethod
    def empty():
        """对应 Shapes.empty()：不含任何体积。"""
        return VoxelShape([])

    @staticmethod
    def block():
        """对应 Shapes.block()：占满整个方块的形状。"""
        return VoxelShape([AABB.box(0.0, 0.0, 0.0, 1.0, 1.0, 1.0)])

    @staticmethod
    def orShapes(*shapes):
        """
        对应 Shapes.or(...)：求并集。

        **方法名不是 or** —— `or` 是 Python 关键字，
        `Shapes.or(a, b)` 在 Python 里无法解析（实测真实模组用了 4 处）。
        改名约定见 core/keyword_renames.py。

        Java 里接受可变参数，这里同样接受；只有 1 个参数时原样返回，
        与 Java 的「or(shape) 返回自身」一致。
        """
        flattened = []
        for shape in shapes:
            if shape is None:
                continue
            if not isinstance(shape, VoxelShape):
                raise IllegalArgumentException(
                    u"orShapes 需要 VoxelShape，收到 {}".format(
                        type(shape).__name__))
            flattened.extend(shape._boxes)

        if len(shapes) == 1 and isinstance(shapes[0], VoxelShape):
            return shapes[0]
        return VoxelShape(flattened)

    @staticmethod
    def andShapes(*shapes):
        """
        对应 Shapes.and(...)：求交集（方法名同样要避开关键字）。

        交集用「逐对箱体求交」实现 —— 与 Minecraft 的做法一致：
        两个形状的交是所有箱体对的交集的集合（去掉空交集）。
        """
        if not shapes:
            return VoxelShape([])

        current = shapes[0]
        if not isinstance(current, VoxelShape):
            raise IllegalArgumentException(u"andShapes 需要 VoxelShape")

        for shape in shapes[1:]:
            if not isinstance(shape, VoxelShape):
                raise IllegalArgumentException(u"andShapes 需要 VoxelShape")
            intersections = []
            for left in current._boxes:
                for right in shape._boxes:
                    overlap = _intersect(left, right)
                    if overlap is not None:
                        intersections.append(overlap)
            current = VoxelShape(intersections)
        return current

    # ---------------- 查询 ----------------

    def getBoxes(self):
        """取组成这个形状的所有箱体。"""
        return list(self._boxes)

    def isEmpty(self):
        return len(self._boxes) == 0

    def size(self):
        """箱体个数（Java 里叫 toAabbs().size()）。"""
        return len(self._boxes)

    def bounds(self):
        """
        对应 bounds()：包住整个形状的边界箱。

        空形状在 Java 里返回一个全 0 的箱体，这里保持一致 ——
        返回 None 会让调用方处处判空。
        """
        if not self._boxes:
            return AABB(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        min_x = min(box.minX for box in self._boxes)
        min_y = min(box.minY for box in self._boxes)
        min_z = min(box.minZ for box in self._boxes)
        max_x = max(box.maxX for box in self._boxes)
        max_y = max(box.maxY for box in self._boxes)
        max_z = max(box.maxZ for box in self._boxes)
        return AABB(min_x, min_y, min_z, max_x, max_y, max_z)

    def min(self, axis):
        """对应 min(Direction.Axis)：某个轴上的最小值。"""
        return self._axis_value(axis, True)

    def max(self, axis):
        """对应 max(Direction.Axis)：某个轴上的最大值。"""
        return self._axis_value(axis, False)

    def _axis_value(self, axis, want_min):
        """
        取某个轴上的极值。

        注意：AABB **没有** `__getitem__`（只有 Vec3i / Vec3 有），
        所以这里必须显式取字段，不能用 box[index]。
        """
        name = java_to_string(axis).upper()
        if name in (u"X", u"DIRECTION.AXIS.X"):
            lower, upper = u"minX", u"maxX"
        elif name in (u"Y", u"DIRECTION.AXIS.Y"):
            lower, upper = u"minY", u"maxY"
        elif name in (u"Z", u"DIRECTION.AXIS.Z"):
            lower, upper = u"minZ", u"maxZ"
        else:
            raise IllegalArgumentException(
                u"未知的轴: {}（应为 X / Y / Z）".format(axis))

        if not self._boxes:
            return 0.0
        if want_min:
            return min(getattr(box, lower) for box in self._boxes)
        return max(getattr(box, upper) for box in self._boxes)

    # ---------------- 几何运算 ----------------

    def move(self, dx, dy, dz):
        """对应 move(...)：整体平移，返回新形状。"""
        return VoxelShape([box.move(dx, dy, dz) for box in self._boxes])

    def intersects(self, other):
        """对应 intersects(AABB)：与一个箱体是否相交。"""
        if not isinstance(other, AABB):
            raise IllegalArgumentException(u"intersects 需要 AABB")
        for box in self._boxes:
            if box.intersects(other):
                return True
        return False

    def intersectsShape(self, other):
        """与另一个形状是否相交（Java 里是同名重载，Python 用独立名字）。"""
        if not isinstance(other, VoxelShape):
            raise IllegalArgumentException(u"intersectsShape 需要 VoxelShape")
        for left in self._boxes:
            for right in other._boxes:
                if left.intersects(right):
                    return True
        return False

    def contains(self, x, y, z):
        """某个点是否在形状内部。"""
        for box in self._boxes:
            if box.contains(x, y, z):
                return True
        return False

    # ---------------- 展示 ----------------

    def toString(self):
        if not self._boxes:
            return u"VoxelShape[empty]"
        parts = [box.toString() for box in self._boxes]
        return u"VoxelShape[{}]".format(u", ".join(parts))

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<{}>".format(self.toString())


def _intersect(left, right):
    """
    两个 AABB 的交集；没有交集返回 None。

    注意用的是开区间式判断（> 与 <）：只有一个面贴合时不算相交 ——
    与 Minecraft 的 AABB.intersects 一致。
    """
    min_x = max(left.minX, right.minX)
    min_y = max(left.minY, right.minY)
    min_z = max(left.minZ, right.minZ)
    max_x = min(left.maxX, right.maxX)
    max_y = min(left.maxY, right.maxY)
    max_z = min(left.maxZ, right.maxZ)

    if max_x <= min_x or max_y <= min_y or max_z <= min_z:
        return None
    return AABB(min_x, min_y, min_z, max_x, max_y, max_z)


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.minecraft.world.phys.shapes.VoxelShape": VoxelShape,
    "net.minecraft.world.phys.shapes.Shapes": VoxelShape,
}


__all__ = ["VoxelShape", "JAVA_MAP"]

# Preserve Java names, including names that require getattr syntax in Python.
from core.java_names import install_java_aliases
install_java_aliases(JAVA_MAP)
