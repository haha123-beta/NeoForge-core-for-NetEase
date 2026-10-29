# -*- coding: utf-8 -*-
# minecraft/item_context.py
# θ 层：物品使用上下文
#
# 真实用法（逐字来自反编译源码）：
#
#   // UseOnContext —— 「拿物品对着方块用」的上下文
#   public InteractionResult useOn(UseOnContext p_40529_) {
#       ... ItemAbilities.AXE_STRIP ...
#
#   // BlockPlaceContext —— 「把方块放下去」的上下文（UseOnContext 的子类）
#   public BlockState getStateForPlacement(BlockPlaceContext p_48689_)
#   public InteractionResult place(BlockPlaceContext p_40577_)
#   protected boolean canPlace(BlockPlaceContext p_40611_, BlockState p_40612_)
#
#   实例方法引用次数（来自扫描）：
#       getLevel         21
#       getPlayer        21
#       getClickedPos    15
#       getClickedFace   13
#       getItemInHand    11
#       canPlace          4
#       getHand           2
#
# 真实调用示例（ManaitaPlusBrewingBlockItem）：
#       BlockPos blockpos = blockplacecontext.getClickedPos();
#       BlockPos relative = blockpos.relative(blockplacecontext.getClickedFace());
#       ItemStack itemstack = blockplacecontext.getItemInHand();
#       Player player = blockplacecontext.getPlayer();
#
# **继承关系要照抄**：`BlockPlaceContext extends UseOnContext`。
# 真实代码把 BlockPlaceContext 传给形参是 UseOnContext 的方法，
# 反过来则不行 —— 继承方向写反了类型检查就对不上。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from java_stdlib._base import (
        IllegalArgumentException,
        hash_code,
    )
    from java_stdlib.lang import java_to_string
    from minecraft.core import BlockPos, Direction, InteractionHand
    from minecraft.item import ItemStack
except ImportError:
    from _base import (  # type: ignore
        IllegalArgumentException,
        hash_code,
    )
    from lang import java_to_string  # type: ignore
    from core import BlockPos, Direction, InteractionHand  # type: ignore
    from item import ItemStack  # type: ignore


# ============================================================
# UseOnContext
# ============================================================

class UseOnContext(object):
    """
    对应 net.minecraft.world.item.context.UseOnContext。

    「玩家拿着某个物品，对着某个方块的某个面用了一下」——
    这些信息全在这个对象里。

    真实代码在 useOn(UseOnContext) 里读它做判断，
    所以 getter 的名字必须与 Java 一致（翻译层按名字找）。
    """

    def __init__(self, level=None, player=None, hand=None, item_in_hand=None,
                 hit_result=None, pos=None, face=None, click_x=0.0,
                 click_y=0.0, click_z=0.0, rotation=0.0):
        self._level = level
        self._player = player
        # hand 不传时默认主手 —— 与 Minecraft 的常见调用一致
        self._hand = hand if hand is not None else InteractionHand.MAIN_HAND
        self._item = item_in_hand if item_in_hand is not None \
            else ItemStack()
        self._hit_result = hit_result
        self._pos = pos if pos is not None else BlockPos(0, 0, 0)
        self._face = face if face is not None else Direction.UP
        self._click_x = float(click_x)
        self._click_y = float(click_y)
        self._click_z = float(click_z)
        self._rotation = float(rotation)

    # ---------------- 世界与玩家 ----------------

    def getLevel(self):
        """对应 getLevel()（引用 21 次）。"""
        return self._level

    def getPlayer(self):
        """对应 getPlayer()（引用 21 次）。可能为 None（发射器等无玩家场景）。"""
        return self._player

    # ---------------- 位置与面 ----------------

    def getClickedPos(self):
        """对应 getClickedPos()（引用 15 次）：被点击的方块坐标。"""
        return self._pos

    def getClickedFace(self):
        """对应 getClickedFace()（引用 13 次）：点击的是哪个面。"""
        return self._face

    def getClickLocation(self):
        """对应 getClickLocation()：点击点在方块上的精确坐标。"""
        return (self._click_x, self._click_y, self._click_z)

    def getHitResult(self):
        """对应 getHitResult()：完整的射线命中结果。"""
        return self._hit_result

    def getRotation(self):
        """对应 getRotation()：玩家朝向对应的方块旋转。"""
        return self._rotation

    # ---------------- 手持物 ----------------

    def getItemInHand(self):
        """对应 getItemInHand()（引用 11 次）：手里那个物品栈。"""
        return self._item

    def getHand(self):
        """对应 getHand()（引用 2 次）：用的哪只手。"""
        return self._hand

    def getHorizontalDirection(self):
        """
        对应 getHorizontalDirection()：玩家朝向的水平方向。

        玩家为 None 时回退成 NORTH —— 与 Minecraft 对空玩家的处理一致，
        免得发射器之类的场景要处处判空。
        """
        if self._player is None:
            return Direction.NORTH
        yaw = getattr(self._player, "_y_rot", 0.0)
        # 按 Minecraft 的 yaw 分段：0 度朝南，顺时针
        index = int((yaw / 90.0 + 0.5)) % 4
        table = (Direction.SOUTH, Direction.WEST, Direction.NORTH,
                 Direction.EAST)
        return table[index]

    def isSecondaryUseActive(self):
        """对应 isSecondaryUseActive()：是不是潜行触发的「副功能」。"""
        if self._player is None:
            return False
        if hasattr(self._player, "isShiftKeyDown"):
            return self._player.isShiftKeyDown()
        return False

    # ---------------- 展示 ----------------

    def toString(self):
        return u"UseOnContext[pos={}, face={}, hand={}]".format(
            self._pos.toString(), self._face, self._hand)

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<{}>".format(self.toString())


# ============================================================
# BlockPlaceContext
# ============================================================

class BlockPlaceContext(UseOnContext):
    """
    对应 net.minecraft.world.item.context.BlockPlaceContext。

    **继承 UseOnContext**（不是独立类）—— 真实代码会把
    BlockPlaceContext 传给形参为 UseOnContext 的方法，继承方向不能反。

    在 UseOnContext 之上加「放置相关」的信息：
      - 替换点击方块时的实际放置位置（可能被推移一格）
      - 相邻方块是否可以替换
      - `canPlace()`：综合判断能不能放
    """

    def __init__(self, level=None, player=None, hand=None, item_in_hand=None,
                 hit_result=None, pos=None, face=None, click_x=0.0,
                 click_y=0.0, click_z=0.0, placement_pos=None):
        UseOnContext.__init__(self, level, player, hand, item_in_hand,
                              hit_result, pos, face, click_x, click_y, click_z)
        # 放置位置默认就是点击位置（可替换方块时）；不可替换则向外推一格
        self._placement_pos = placement_pos
        self._replace_clicked = False

    # ---------------- 放置位置 ----------------

    def getClickedPos(self):
        """
        重写：返回**实际放置位置**。

        与 UseOnContext.getClickedPos 的区别：如果点击的方块可被替换
        （例如草丛、水），放置位置就是它本身；否则是它的外侧面邻格。
        这就是 `blockplacecontext.getClickedPos()` 的真实语义 ——
        翻译层按名字找 getClickedPos，所以这里要保持同名。
        """
        if self._placement_pos is not None:
            return self._placement_pos
        return self.recomputePlacementPos()

    def recomputePlacementPos(self):
        """按「点击方块能否替换」算出实际放置位置。"""
        base = UseOnContext.getClickedPos(self)
        if self._replace_clicked:
            return base
        return base.relative(self.getClickedFace())

    def setReplaceClicked(self, value):
        """登记「点击的方块可以被替换」（真实代码由放置逻辑判定）。"""
        self._replace_clicked = bool(value)
        self._placement_pos = None      # 失效缓存，下次重算
        return self

    def canReplaceClicked(self):
        """对应 canReplaceClicked()：点击的方块能不能被直接替换。"""
        return self._replace_clicked

    def setPlacementPos(self, pos):
        """直接指定放置位置（跳过推算）。"""
        self._placement_pos = pos
        return self

    # ---------------- 相邻可否替换 ----------------

    def canPlace(self):
        """
        对应 canPlace()（引用 4 次）：这个位置能不能放东西。

        真实代码：`if (!p_40577_.canPlace()) { return InteractionResult.FAIL; }`
        本实现按「放置位置是否为空」判断 —— 没有世界句柄时保守返回 True，
        免得把能放的也挡掉。
        """
        level = self.getLevel()
        if level is None:
            return True
        state = level.getBlockState(self.getClickedPos())
        if state is None:
            return True
        return state.isAir()

    def replacingClickedOnBlock(self):
        """对应 replacingClickedOnBlock()：是否在替换点击的那个方块。"""
        return self._replace_clicked

    # ---------------- 展示 ----------------

    def toString(self):
        return u"BlockPlaceContext[placement={}, face={}]".format(
            self.getClickedPos().toString(), self.getClickedFace())

    def __repr__(self):
        return u"<{}>".format(self.toString())


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.minecraft.world.item.context.UseOnContext": UseOnContext,
    "net.minecraft.world.item.context.BlockPlaceContext": BlockPlaceContext,
}


__all__ = ["UseOnContext", "BlockPlaceContext", "JAVA_MAP"]

# Preserve Java names, including names that require getattr syntax in Python.
from core.java_names import install_java_aliases
install_java_aliases(JAVA_MAP)
