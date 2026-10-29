# -*- coding: utf-8 -*-
# minecraft/block_entity.py
# θ 层：方块实体与容器
#
# 真实用法（逐字来自反编译源码）：
#
#   // 注册方块实体类型（DeferredRegister + Builder）
#   public static final DeferredHolder<BlockEntityType<?>,
#                                     BlockEntityType<ManaitaPlusFurnaceBlockEntity>>
#       FURNACE_BLOCK_ENTITY = ManaitaPlusLegacy.BLOCK_ENTITY_TYPES.register(
#           "furnace_block_entity",
#           () -> BlockEntityType.Builder.of(ManaitaPlusFurnaceBlockEntity::new,
#                                           new Block[]{ ...FurnaceBlock.get() })
#                                       .build(null));
#
#   // 方块实体的基类与接口
#   public class ManaitaPlusBrewingStandBlockEntity
#           extends BaseContainerBlockEntity
#           implements WorldlyContainer {
#       private NonNullList<ItemStack> items =
#           NonNullList.withSize(5, ItemStack.EMPTY);
#       protected Component getDefaultName() {...}
#       public int getContainerSize() { return 5; }
#       public boolean canPlaceItem(int index, ItemStack stack) {...}
#       public int[] getSlotsForFace(Direction side) {...}
#       protected AbstractContainerMenu createMenu(int id, Inventory player) {...}
#       protected void loadAdditional(CompoundTag tag, HolderLookup.Provider r) {
#           super.loadAdditional(tag, r);
#           ContainerHelper.loadAllItems(tag, this.items, r);
#       }
#       protected void saveAdditional(CompoundTag tag, HolderLookup.Provider r) {
#           super.saveAdditional(tag, r);
#           ContainerHelper.saveAllItems(tag, this.items, r);
#       }
#   }
#
#   // 方块侧：给方块实体提供 ticker
#   public <T extends BlockEntity> BlockEntityTicker<T> getTicker(
#           Level level, BlockState state, BlockEntityType<T> type) {
#       return level.isClientSide ? null
#           : ManaitaPlusBrewingStandBlock.createTickerHelper(type, BREWING_BLOCK_ENTITY,
#                                                             ManaitaPlusBrewingStandBlockEntity::serverTick);
#   }
#
# **一个必须照抄的语义**：`getTicker` 在客户端侧返回 null。
# 真实代码写的是 `level.isClientSide ? null : createTickerHelper(...)` ——
# 方块实体逻辑只在服务端跑，客户端靠同步。写反了会导致双端各跑一遍。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import
import copy
from java_stdlib.lang import NullPointerException, IndexOutOfBoundsException, ArrayIndexOutOfBoundsException, UnsupportedOperationException

try:
    from java_stdlib._base import (
        IllegalArgumentException,
        IllegalStateException,
        hash_code,
    )
    from java_stdlib.lang import java_to_string
    from minecraft.core import BlockPos, Component, Direction
    from minecraft.item import ItemStack
    from minecraft.registries import Holder
except ImportError:
    from _base import (  # type: ignore
        IllegalArgumentException,
        IllegalStateException,
        hash_code,
    )
    from lang import java_to_string  # type: ignore
    from core import BlockPos, Component, Direction  # type: ignore
    from item import ItemStack  # type: ignore
    from registries import Holder  # type: ignore


# ============================================================
# NonNullList
# ============================================================

class NonNullList(object):
    """Java List semantics; fixed withSize lists reset to their non-null default."""
    def __init__(self, items=None, size=None, default=None):
        self._fixed = size is not None
        self._default = default
        if size is not None:
            if int(size) < 0:
                raise IllegalArgumentException("Negative NonNullList size")
            if default is None:
                raise NullPointerException("NonNullList default is null")
            self._items = [default for index in range(int(size))]
        else:
            self._items = list(items) if items is not None else []
            if any(item is None for item in self._items):
                raise NullPointerException("NonNullList rejects null elements")

    @staticmethod
    def withSize(size, default):
        return NonNullList(size=size, default=default)

    @staticmethod
    def create():
        return NonNullList()

    def size(self):
        return len(self._items)

    def get(self, index):
        if int(index) < 0 or int(index) >= len(self._items):
            exception_type = ArrayIndexOutOfBoundsException if self._fixed else IndexOutOfBoundsException
            raise exception_type("NonNullList index out of range")
        return self._items[int(index)]

    def set(self, index, value):
        old = self.get(index)
        if value is None:
            raise NullPointerException("NonNullList rejects null elements")
        self._items[int(index)] = value
        return old

    def add(self, *args):
        if self._fixed:
            raise UnsupportedOperationException("Fixed NonNullList cannot resize")
        if len(args) not in (1, 2):
            raise IllegalArgumentException("NonNullList add requires value or index/value")
        index, value = (len(self._items), args[0]) if len(args) == 1 else args
        if value is None:
            raise NullPointerException("NonNullList rejects null elements")
        if int(index) < 0 or int(index) > len(self._items):
            raise IndexOutOfBoundsException("NonNullList insertion index invalid")
        self._items.insert(int(index), value)
        return True if len(args) == 1 else None

    def remove(self, index):
        if self._fixed:
            raise UnsupportedOperationException("Fixed NonNullList cannot resize")
        self.get(index)
        return self._items.pop(int(index))

    def isEmpty(self):
        return not self._items

    def clear(self):
        if self._fixed:
            self._items[:] = [self._default for index in range(len(self._items))]
        else:
            self._items[:] = []

    def toList(self):
        return list(self._items)

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def __getitem__(self, index):
        return self.get(index)

    def __repr__(self):
        return "<NonNullList " + str(len(self._items)) + ">"


# ============================================================
# Container
# ============================================================

from minecraft.container_contracts import Container as ContainerInterface, WorldlyContainer as WorldlyContainerInterface

class Container(ContainerInterface):
    """
    对应 net.minecraft.world.Container。

    真实代码里方块实体实现它（`implements WorldlyContainer` 是其子接口），
    从而「能被当容器用」—— 漏斗、比较器、菜单都靠这个接口。

    10 个方法里，真实模组实现了这几个：getContainerSize / getItem / setItem /
    removeItem / isEmpty / canPlaceItem / stillValid / createMenu。
    """

    def getContainerSize(self):
        raise NotImplementedError()

    def getItem(self, index):
        raise NotImplementedError()

    def setItem(self, index, stack):
        raise NotImplementedError()

    def removeItem(self, index, amount):
        """对应 removeItem(int, int)：取出并减少数量，返回取出的栈。"""
        if int(amount) <= 0:
            return ItemStack()
        stack = self.getItem(index)
        if stack is None or stack.isEmpty():
            return ItemStack()
        result = stack.split(int(amount))
        self.setChanged()
        return result

    def removeItemNoUpdate(self, index):
        """Remove the entire stack without the normal dirty notification."""
        stack = self.getItem(index)
        if stack is None or stack.isEmpty():
            return ItemStack()
        # Concrete containers must supply storage-specific removal semantics.
        raise NotImplementedError("Container.removeItemNoUpdate requires storage implementation")

    def getMaxStackSize(self, *args):
        return ContainerInterface.getMaxStackSize(self,*args)

    def isEmpty(self):
        raise NotImplementedError()

    def clearContent(self):
        """对应 clearContent()：清空所有槽位。"""
        for index in range(self.getContainerSize()):
            self.setItem(index, ItemStack())
        return None

    def setChanged(self):
        """对应 setChanged()：标记「内容变了」（用于存档与同步）。"""
        return None

    def canPlaceItem(self, index, stack):
        """对应 canPlaceItem(int, ItemStack)：这个槽位能不能放这个物品。"""
        return True

    def stillValid(self, player):
        """对应 stillValid(Player)：容器是否还有效（玩家没走远）。"""
        return True

    def startOpen(self, player):
        return None

    def stopOpen(self, player):
        return None

    def __repr__(self):
        return u"<{} {} 格>".format(type(self).__name__, self.getContainerSize())


class SimpleContainer(Container):
    """Shared mutable storage, with independent empty stacks and change listeners."""
    def __init__(self, *args):
        if len(args) != 1 or isinstance(args[0], ItemStack):
            if not all(isinstance(stack, ItemStack) for stack in args):
                raise IllegalArgumentException("SimpleContainer requires size or ItemStacks")
            self.items = list(args)
            self._listeners = []
            self.change_count = 0
            return
        size = args[0]
        if int(size) < 0:
            raise IllegalArgumentException("Negative container size")
        self.items = [ItemStack() for index in range(int(size))]
        self._listeners = []
        self.change_count = 0

    def _index(self, index):
        index = int(index)
        if index < 0 or index >= len(self.items):
            raise IllegalArgumentException("Container slot out of range")
        return index

    def getContainerSize(self):
        return len(self.items)

    def getItem(self, index):
        return self.items[self._index(index)]

    def setItem(self, index, stack):
        index = self._index(index)
        if not isinstance(stack, ItemStack):
            raise IllegalArgumentException("Container slot requires ItemStack")
        self.items[index] = stack
        if not stack.isEmpty():
            stack.setCount(min(stack.getCount(), self.getMaxStackSize(), stack.getMaxStackSize()))
        self.setChanged()

    def removeItemNoUpdate(self, index):
        index = self._index(index)
        stack = self.items[index]
        self.items[index] = ItemStack()
        return stack

    def isEmpty(self):
        return all(stack.isEmpty() for stack in self.items)

    def addListener(self, listener):
        if listener not in self._listeners:
            self._listeners.append(listener)

    def removeListener(self, listener):
        if listener in self._listeners:
            self._listeners.remove(listener)

    def setChanged(self):
        self.change_count += 1
        for listener in list(self._listeners):
            listener.containerChanged(self)

    def addItem(self, stack):
        remaining = stack.copy()
        for index in range(len(self.items)):
            existing = self.items[index]
            if remaining.isEmpty():
                break
            if not existing.isEmpty() and existing.isSameItemSameComponents(remaining):
                amount = min(remaining.getCount(), max(0, min(self.getMaxStackSize(), existing.getMaxStackSize()) - existing.getCount()))
                if amount:
                    existing.grow(amount)
                    remaining.shrink(amount)
                    self.setChanged()
        for index in range(len(self.items)):
            if remaining.isEmpty():
                break
            if self.items[index].isEmpty():
                amount = min(remaining.getCount(), self.getMaxStackSize(), remaining.getMaxStackSize())
                self.setItem(index, remaining.copyWithCount(amount))
                remaining.shrink(amount)
        return remaining


class WorldlyContainer(Container,WorldlyContainerInterface):
    """
    对应 net.minecraft.world.level.block.entity.WorldlyContainer。

    在 Container 之上加「按面（方向）限制槽位访问」——
    真实代码用它实现「漏斗只能从上面进、从下面出」这类规则：

        private static final int[] SLOTS_FOR_UP = new int[]{3};
        private static final int[] SLOTS_FOR_DOWN = new int[]{0, 1, 2, 3};
        private static final int[] SLOTS_FOR_SIDES = new int[]{0, 1, 2, 4};
        public int[] getSlotsForFace(Direction side) { ... }
    """

    def getSlotsForFace(self, side):
        raise NotImplementedError()

    def canPlaceItemThroughFace(self, index, stack, direction):
        """对应 canPlaceItemThroughFace：能否从这个面塞进去。"""
        return self.canPlaceItem(index, stack)

    def canTakeItemThroughFace(self, index, stack, direction):
        """对应 canTakeItemThroughFace：能否从这个面取出来。"""
        return True


# ============================================================
# BlockEntity
# ============================================================

class BlockEntity(object):
    """
    对应 net.minecraft.world.level.block.entity.BlockEntity。

    方块实体是「方块身上的数据与逻辑」：熔炉的燃烧进度、箱子的内容物。
    它绑定在某个 BlockPos 上。

    真实用法：`super((BlockEntityType) ...BREWING_BLOCK_ENTITY.get(), pos, state)`
    """

    def __init__(self, block_entity_type=None, pos=None, state=None):
        self._type = block_entity_type
        self._pos = BlockPos(pos.getX(),pos.getY(),pos.getZ()) if pos is not None else BlockPos(0, 0, 0)
        self._block_state = state
        self._level = None
        self._removed = False

    # ---------------- 绑定信息 ----------------

    def getBlockPos(self):
        """对应 getBlockPos()。"""
        return self._pos

    def setBlockPos(self, pos):
        self._pos = pos
        return None

    def getBlockState(self):
        """对应 getBlockState()：所在位置的方块状态。"""
        return self._block_state

    def hasLevel(self):return self._level is not None

    def isValidBlockState(self,state):
        from java_stdlib.lang import NullPointerException
        if self._type is None:raise NullPointerException()
        return self._type.isValid(state)

    def setBlockState(self,state):
        from minecraft.official_interfaces import _invoke
        from java_stdlib.lang import IllegalStateException
        if not _invoke(self,'isValidBlockState',(state,),('net.minecraft.world.level.block.state.BlockState',)):
            raise IllegalStateException('Invalid block entity state')
        self._block_state=state

    def triggerEvent(self,event_id,event_data):return False

    def onlyOpCanSetNbt(self):return False

    def getType(self):
        """对应 getType()：方块实体类型。"""
        return self._type

    def getLevel(self):
        """对应 getLevel()：所在世界（可能为 None）。"""
        return self._level

    def setLevel(self, level):
        self._level = level
        return None

    # ---------------- 存档 ----------------

    def loadAdditional(self, tag, registries=None):
        """
        对应 loadAdditional(CompoundTag, HolderLookup.Provider)。

        真实代码会先 `super.loadAdditional(tag, registries)` 再读自己的字段。
        `tag` 是 `CompoundTag`（见 minecraft/nbt.py）。
        """
        return None

    def saveAdditional(self, tag, registries=None):
        """对应 saveAdditional(CompoundTag, HolderLookup.Provider)。"""
        return None

    def getUpdateTag(self, registries=None):
        """对应 getUpdateTag(...)：发给客户端的同步数据。"""
        from minecraft.nbt import CompoundTag
        return CompoundTag()

    def getUpdatePacket(self):
        """对应 getUpdatePacket()：方块更新包（客户端为 None）。"""
        return None

    def setChanged(self):
        """对应 setChanged()：标记脏数据，触发存档。"""
        if self._level is not None and hasattr(self._level, "getAccess"):
            access = self._level.getAccess()
            if hasattr(access, "noteBlockEntityChanged"):
                access.noteBlockEntityChanged(self._pos)
        return None

    # ---------------- 生命周期 ----------------

    def setRemoved(self):
        """对应 setRemoved()：方块实体被移除。"""
        self._removed = True
        return None

    def isRemoved(self):
        return self._removed

    def clearRemoved(self):
        self._removed = False
        return None

    # ---------------- 展示与比较 ----------------

    def getDisplayName(self):
        """对应 getDisplayName()：界面标题。"""
        return Component.literal(type(self).__name__)

    def equals(self, other):
        if not isinstance(other, BlockEntity):
            return False
        return other is self

    def hashCode(self):
        return id(self)

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __repr__(self):
        return u"<{} at {}>".format(type(self).__name__,
                                    self._pos.toString())


class BaseContainerBlockEntity(BlockEntity, Container):
    """
    对应 net.minecraft.world.level.block.entity.BaseContainerBlockEntity。

    它是「带物品栏的方块实体」的基类。真实代码继承它来实现熔炉/酿造台：

        public class ManaitaPlusBrewingStandBlockEntity
                extends BaseContainerBlockEntity
                implements WorldlyContainer {
            private NonNullList<ItemStack> items = NonNullList.withSize(5, ItemStack.EMPTY);
            protected NonNullList<ItemStack> getItems() { return this.items; }
            protected void setItems(NonNullList<ItemStack> items) { this.items = items; }
            public int getContainerSize() { return 5; }
        }

    所以 `getItems()` / `setItems(...)` 是子类必须提供的钩子，
    而 `getItem(i)` / `setItem(i, v)` / `isEmpty()` 由基类基于它们实现 ——
    照抄这个分工，子类就只需要管「物品列表是什么」。
    """

    # 子类覆盖：默认没有名字
    def getDefaultName(self):
        return Component.literal(type(self).__name__)

    # 子类覆盖：物品列表
    def getItems(self):
        raise NotImplementedError(
            u"{} 必须实现 getItems()".format(type(self).__name__))

    def setItems(self, items):
        raise NotImplementedError(
            u"{} 必须实现 setItems(NonNullList)".format(type(self).__name__))

    # ---------------- Container 实现 ----------------

    def getContainerSize(self):
        return self.getItems().size()

    def getItem(self, index):
        return self.getItems().get(index)

    def setItem(self, index, stack):
        self.getItems().set(index, stack)
        self.setChanged()
        return None

    def removeItemNoUpdate(self, index):
        stack = self.getItems().get(index)
        self.getItems().set(index, ItemStack())
        return stack

    def isEmpty(self):
        return all(stack is None or stack.isEmpty() for stack in self.getItems())

    def clearContent(self):
        items = self.getItems()
        for index in range(items.size()):
            items.set(index, ItemStack())
        self.setChanged()
        return None

    def getDisplayName(self):
        return self.getDefaultName()

    # ---------------- 存档 ----------------

    def loadAdditional(self, tag, registries=None):
        """
        对应 loadAdditional：**先把物品列表整成同样大小的空表**，再读内容。

        这一步不能省：读存档时槽位数必须与当前版本一致，
        否则旧存档里 3 个槽、新版本 5 个槽，后面按索引访问会错位。
        """
        BlockEntity.loadAdditional(self, tag, registries)
        container_helper_reset = NonNullList.withSize(self.getContainerSize(),
                                                      ItemStack())
        ContainerHelper.loadAllItems(tag, container_helper_reset, registries)
        self.setItems(container_helper_reset)
        return None

    def saveAdditional(self, tag, registries=None):
        BlockEntity.saveAdditional(self, tag, registries)
        ContainerHelper.saveAllItems(tag, self.getItems(), registries)
        return None

    def getUpdateTag(self, registries=None):
        """
        对应 getUpdateTag(...)：发给客户端的同步数据。

        返回 CompoundTag（真实类型就是它）。
        """
        from minecraft.nbt import CompoundTag
        tag = CompoundTag()
        ContainerHelper.saveAllItems(tag, self.getItems(), registries)
        return tag


# ============================================================
# ContainerHelper
# ============================================================

class ContainerHelper(object):
    """
    对应 net.minecraft.world.ContainerHelper。

    真实代码用它把物品栏写进/读出 NBT：
        ContainerHelper.loadAllItems(tag, this.items, registries);
        ContainerHelper.saveAllItems(tag, this.items, registries);

    参数 `tag` 是 `CompoundTag`（见 minecraft/nbt.py）。
    """

    ITEMS_KEY = u"Items"

    @staticmethod
    def saveAllItems(tag, items, registries=None):
        """
        对应 saveAllItems(CompoundTag, NonNullList, HolderLookup.Provider)。

        **只存非空槽位**（连同槽位号），与 Minecraft 一致 ——
        空槽位存进去只会让存档变大，而且反序列化时要多判一次。
        """
        if tag is None:
            raise IllegalArgumentException(u"saveAllItems 需要 tag")
        entries = []
        for index in range(items.size()):
            stack = items.get(index)
            if stack is None or stack.isEmpty():
                continue
            unresolved_id = getattr(stack, "getRestoredId", None)
            if callable(unresolved_id):
                identifier = unresolved_id()
            else:
                item = stack.getItem()
                identifier = (getattr(item, "_registry_name", None) or getattr(item, "_identifier", None)) if item is not None else u"minecraft:air"
                if not identifier:
                    raise IllegalArgumentException("Cannot save an unregistered item without its resource ID")
            row = {u"Slot": index, u"id": java_to_string(identifier), u"count": stack.getCount()}
            # NeoCore snapshot extension, not a claim of Java DataComponent codec equivalence.
            metadata = {"custom_data": copy.deepcopy(stack.getCustomData())}
            for name in ("_native_item_data", "_native_item_components"):
                if hasattr(stack, name):
                    metadata[name] = copy.deepcopy(getattr(stack, name))
            display_name = getattr(stack, "_display_name", None)
            if display_name is not None:
                metadata["display_name"] = copy.deepcopy(display_name)
            row["NeoCoreData"] = metadata
            entries.append(row)
        tag.putList(ContainerHelper.ITEMS_KEY, entries)
        return None

    @staticmethod
    def loadAllItems(tag, items, registries=None):
        """
        对应 loadAllItems(CompoundTag, NonNullList, HolderLookup.Provider)。

        按槽位号写回；槽位号越界的条目**跳过而不是抛异常** ——
        旧存档可能来自槽位数更多的版本，直接崩会让玩家进不去世界。
        """
        if tag is None:
            return None
        entries = tag.getList(ContainerHelper.ITEMS_KEY)
        if not entries:
            return None

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            slot = int(entry.get(u"Slot", -1))
            if slot < 0 or slot >= items.size():
                continue
            count = int(entry.get(u"count", 1))
            # 反序列化需要按 id 找回物品；本实现没有全局物品表，
            # 所以保留一个「未解析」的占位描述，交由上层补齐 ——
            # 关键是**不能让这一格变成 None**，否则后续判空会 NPE。
            identifier = entry.get(u"id")
            stack = None
            if registries is not None:
                from minecraft.registries import HolderLookup, RegistryAccess
                if isinstance(registries, RegistryAccess):
                    lookup = registries.lookupOrThrow("minecraft:item")
                elif isinstance(registries, HolderLookup):
                    lookup = registries.lookup("minecraft:item")
                else:
                    raise IllegalArgumentException("Unsupported container registry provider")
                holder = lookup.get(identifier)
                if holder is not None:
                    stack = ItemStack(holder.value(), count)
            if stack is None:
                stack = _RestoredItemStack(identifier, count)
            metadata = entry.get("NeoCoreData", {})
            stack.setCustomData(copy.deepcopy(metadata.get("custom_data", {})))
            for name in ("_native_item_data", "_native_item_components"):
                if name in metadata:
                    setattr(stack, name, copy.deepcopy(metadata[name]))
            if "display_name" in metadata:
                value = metadata["display_name"]
                stack._display_name = copy.deepcopy(value) if isinstance(value, Component) else Component.literal(value)
            items.set(slot, stack)
        return None


class _RestoredItemStack(ItemStack):
    """
    从存档读回但尚未解析成真实物品的栈。

    真实引擎会按 id 去注册表找回 Item；本实现没有那个全局表，
    所以先留一个带 id 与数量的占位 —— 它依据存档 id/数量判空，不冒充已解析的 Item；
    上层拿到后可以用 id 去 HolderLookup 里补解析。
    """

    def __init__(self, identifier, count):
        ItemStack.__init__(self)
        self._restored_id = java_to_string(identifier) \
            if identifier is not None else u"minecraft:air"
        self._count = int(count)

    def isEmpty(self):
        # This is a storage record, not a resolved runtime item.
        return self._restored_id == u"minecraft:air" or self._count <= 0

    def copy(self):
        result = _RestoredItemStack(self._restored_id, self._count)
        result._custom_data = copy.deepcopy(self._custom_data)
        result._display_name = copy.deepcopy(self._display_name)
        for name in ("_native_item_data", "_native_item_components"):
            if hasattr(self, name):
                setattr(result, name, copy.deepcopy(getattr(self, name)))
        return result

    def isSameItemSameComponents(self, other):
        return (isinstance(other, _RestoredItemStack) and self._restored_id == other._restored_id
                and self.getCustomData() == other.getCustomData()
                and getattr(self, "_native_item_components", None) == getattr(other, "_native_item_components", None))

    def getRestoredId(self):
        """取出存档里的物品 id，供上层解析。"""
        return self._restored_id

    def getDescriptionId(self):
        return self._restored_id

    def toString(self):
        return u"{} x {}（待解析）".format(self._count, self._restored_id)


# ============================================================
# Ticker
# ============================================================

from minecraft.official_interfaces import BlockEntityTicker as BlockEntityTickerInterface

class BlockEntityTicker(BlockEntityTickerInterface):
    """
    对应 net.minecraft.world.level.block.entity.BlockEntityTicker。

    它是个函数式接口：`tick(Level, BlockPos, BlockState, T)`。
    真实代码用 `::serverTick` 方法引用来提供它。
    """

    def __init__(self, function):
        if function is None:
            raise IllegalArgumentException(u"BlockEntityTicker 需要函数")
        self._function = function
        self.tick_count = 0

    def tick(self, level, pos, state, block_entity):
        """对应 tick(Level, BlockPos, BlockState, T)。"""
        self.tick_count += 1
        return self._function(level, pos, state, block_entity)

    @staticmethod
    def of(function):
        return BlockEntityTicker(function)

    def __repr__(self):
        return u"<BlockEntityTicker 已 tick {} 次>".format(self.tick_count)


# ============================================================
# BlockEntityType
# ============================================================

class BlockEntityType(object):
    """
    对应 net.minecraft.world.level.block.entity.BlockEntityType。

    真实注册写法：
        BlockEntityType.Builder.of(ManaitaPlusFurnaceBlockEntity::new,
                                   new Block[]{ ...FurnaceBlock.get() })
                           .build(null)
    """

    def __init__(self, factory, blocks=None, identifier=None):
        if factory is None:
            raise IllegalArgumentException(u"BlockEntityType 需要工厂函数")
        self._factory = factory
        self._blocks = list(blocks) if blocks else []
        self._identifier = identifier
        self.valid_blocks = list(self._blocks)

    # ---------------- 构造方块实体 ----------------

    def create(self, pos, state):
        """对应 create(BlockPos, BlockState)：按工厂造方块实体。"""
        return self._factory(pos, state)

    def instantiate(self, pos, state):
        """对应 instantiate(...)：同上（Java 里是不同重载）。"""
        return self.create(pos, state)

    def isValid(self, state):
        """
        对应 isValid(BlockState)：这个状态对应的方块能不能带本类型的方块实体。

        真实代码用它做类型检查（放错方块就别建方块实体）。
        """
        from java_stdlib.lang import NullPointerException
        if state is None:raise NullPointerException()
        block = state.getBlock()
        if block is None:
            return False
        for candidate in self._blocks:
            if candidate is block:
                return True
        return False

    def getValidBlocks(self):
        return frozenset(self._blocks)

    def getBlocks(self):
        return list(self._blocks)

    def setIdentifier(self, value):
        self._identifier = java_to_string(value)
        return self

    def getIdentifier(self):
        return self._identifier

    def equals(self, other):
        return other is self

    def hashCode(self):
        return id(self)

    def __eq__(self, other):
        return self.equals(other)

    def __ne__(self, other):
        return not self.equals(other)

    def __hash__(self):
        return self.hashCode()

    def __repr__(self):
        return u"<BlockEntityType {} {} 个方块>".format(
            self._identifier or u"未注册", len(self._blocks))


class BlockEntityTypeBuilder(object):
    """
    对应 BlockEntityType.Builder。

    链式约定与 Item.Properties 一样：每个方法返回自身，只有 build 产出结果。
    真实代码只用 `of(...)` + `build(null)` 两步。
    """

    def __init__(self, factory, blocks=None):
        self._factory = factory
        self._blocks = list(blocks) if blocks else []

    @staticmethod
    def of(factory, blocks=None):
        """对应 Builder.of(BlockEntitySupplier, Block...)。"""
        if blocks is None:
            blocks = []
        if not isinstance(blocks, (list, tuple)):
            blocks = [blocks]
        return BlockEntityTypeBuilder(factory, blocks)

    def build(self, type_id=None):
        """
        对应 build(Type<?>)：产出 BlockEntityType。

        真实代码传 `null`（类型由注册表分配）。
        """
        return BlockEntityType(self._factory, self._blocks, type_id)

    def __repr__(self):
        return u"<BlockEntityType.Builder {} 个方块>".format(len(self._blocks))


BlockEntityType.Builder = BlockEntityTypeBuilder


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.minecraft.core.NonNullList": NonNullList,
    "net.minecraft.world.Container": ContainerInterface,
    "net.minecraft.world.SimpleContainer": SimpleContainer,
    "net.minecraft.world.level.block.entity.BlockEntity": BlockEntity,
    "net.minecraft.world.level.block.entity.BaseContainerBlockEntity":
        BaseContainerBlockEntity,
    "net.minecraft.world.level.block.entity.BlockEntityType": BlockEntityType,
    "net.minecraft.world.level.block.entity.BlockEntityType$Builder":
        BlockEntityTypeBuilder,
    "net.minecraft.world.level.block.entity.BlockEntityTicker":
        BlockEntityTickerInterface,
    "net.minecraft.world.level.block.entity.ContainerHelper": ContainerHelper,
    "net.minecraft.world.WorldlyContainer": WorldlyContainerInterface,
}


__all__ = [
    "NonNullList", "Container", "WorldlyContainer",
    "BlockEntity", "BaseContainerBlockEntity",
    "ContainerHelper", "BlockEntityTicker",
    "BlockEntityType", "BlockEntityTypeBuilder",
    "JAVA_MAP",
]
