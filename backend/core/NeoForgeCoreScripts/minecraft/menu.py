# -*- coding: utf-8 -*-
# minecraft/menu.py
# θ 层：容器界面（菜单）与物品栏槽位
#
# 真实用法（逐字来自反编译源码）：
#
#   // 注册菜单类型
#   public static final DeferredRegister<MenuType<?>> MENU_TYPES =
#       DeferredRegister.create(BuiltInRegistries.MENU, "manaita_plus_legacy");
#   event.register(ManaitaPlusLegacyMenuCore.CraftingManaita.get(), CraftingManaitaScreen::new);
#
#   // 方块实体提供菜单
#   public MenuProvider getMenuProvider(BlockState state, Level level, BlockPos pos)
#   player.openMenu(state.getMenuProvider(level, pos));
#   sender.openMenu((MenuProvider) new ...);          // 匿名实现
#
#   // 菜单与槽位
#   protected AbstractContainerMenu createMenu(int id, Inventory player)
#   super(menu, inventory, title)
#   BrewingStandScreen(...) { super((AbstractContainerMenu) p_98332_, ...) }
#   protected final ContainerData dataAccess = new ...;   // 进度条数据
#   class ... extends RecipeBookMenu
#
#   // 掉落内容物
#   Containers.dropContents(level, pos, container);
#
# **一个必须照抄的分工**：`AbstractContainerMenu` 只管「槽位与同步」，
# 界面的绘制在客户端 Screen 里（δ 层会跳过），两者通过 menuType 关联。
# 所以本层只做数据侧，不碰渲染 —— 与 δ 层「客户端界面跳过」的判定一致。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from java_stdlib._base import (
        IllegalArgumentException,
        hash_code,
        IllegalStateException,
    )
    from java_stdlib.lang import java_to_string, UnsupportedOperationException
    from minecraft.item import ItemStack
    from minecraft.block_entity import NonNullList
except ImportError:
    from _base import (  # type: ignore
        IllegalArgumentException,
        hash_code,
        IllegalStateException,
    )
    from lang import java_to_string, UnsupportedOperationException  # type: ignore
    from item import ItemStack  # type: ignore
    from block_entity import NonNullList  # type: ignore


# ============================================================
# ContainerData
# ============================================================

from minecraft.official_interfaces import ContainerData as ContainerDataInterface, MenuProvider as MenuProviderInterface

class ContainerData(ContainerDataInterface):
    """
    对应 net.minecraft.world.inventory.ContainerData。

    它是「一小块要在菜单里同步的整数」—— 典型用途是熔炉的
    燃烧进度条（真实代码：`protected final ContainerData dataAccess = new ...`）。

    真实代码里它是匿名内部类，实现 get / set / getCount 三个方法。
    这里给一个直接用列表存值的实现，够用且可测。
    """

    def __init__(self, size=4, values=None):
        if values is not None:
            self._values = [int(v) for v in values]
        else:
            self._values = [0] * int(size)

    def get(self, index):
        """对应 get(int)：取第 index 个值。"""
        index = int(index)
        if index < 0 or index >= len(self._values):
            raise IllegalArgumentException(
                u"ContainerData 越界: {}（共 {} 项）".format(index,
                                                            len(self._values)))
        return self._values[index]

    def set(self, index, value):
        """对应 set(int, int)：写第 index 个值。"""
        index = int(index)
        if index < 0 or index >= len(self._values):
            raise IllegalArgumentException(
                u"ContainerData 越界: {}（共 {} 项）".format(index,
                                                            len(self._values)))
        self._values[index] = int(value)
        return None

    def getCount(self):
        """对应 getCount()：值的个数。"""
        return len(self._values)

    def toList(self):
        return list(self._values)

    def __len__(self):
        return len(self._values)

    def __repr__(self):
        return u"<ContainerData {}>".format(self._values)


# ============================================================
# Slot
# ============================================================

class Slot(object):
    """
    对应 net.minecraft.world.inventory.Slot。

    一个槽位 = 「在界面里显示容器中的某一格」+「那个格子的坐标」。
    真实代码用它造菜单的槽位布局，并用坐标画那个格子。

    三个真正常用的行为：
      - `mayPlace(stack)`：这个槽位收不收这个物品
      - `hasItem()`：格子非空
      - `getItem()` / `set(...)`
    """

    def __init__(self, container=None, slot_index=0, x=0, y=0):
        self.index = -1
        self.container = container
        self.slot_index = int(slot_index)
        # Java 1.21.1 declares public x/y fields, not x()/y() methods.
        self.x = int(x)
        self.y = int(y)

    # ---------------- 位置 ----------------

    def getContainerSlot(self):
        """对应 getContainerSlot()：在容器里的第几格。"""
        return self.slot_index

    def getSlotIndex(self):
        return self.slot_index

    # ---------------- 内容 ----------------

    def getItem(self):
        """对应 getItem()：这一格的物品（容器不存在时返回空栈）。"""
        if self.container is None:
            return ItemStack()
        return self.container.getItem(self.slot_index)

    def set(self, stack):
        """对应 set(ItemStack)。"""
        if self.container is None:
            return None
        self.container.setItem(self.slot_index, stack)
        return None

    def setChanged(self):
        if self.container is not None:
            self.container.setChanged()
        return None

    def hasItem(self):
        """对应 hasItem()：格子非空。"""
        stack = self.getItem()
        return stack is not None and not stack.isEmpty()

    def remove(self, amount):
        """对应 remove(int)：取出若干。"""
        if self.container is None:
            return ItemStack()
        return self.container.removeItem(self.slot_index, amount)

    def mayPlace(self, stack):
        """
        对应 mayPlace(ItemStack)：这个槽位收不收这个物品。

        默认真；子类（例如「只能放燃料」的槽位）覆盖它。
        """
        if self.container is None:
            return True
        if hasattr(self.container, "canPlaceItem"):
            return self.container.canPlaceItem(self.slot_index, stack)
        return True

    def getMaxStackSize(self, stack=None):
        limit = self.container.getMaxStackSize() if self.container is not None and hasattr(self.container, "getMaxStackSize") else 99
        return min(limit, stack.getMaxStackSize()) if stack is not None else limit

    def mayPickup(self, player):
        return True

    def setByPlayer(self, stack, old_stack=None):
        return self.set(stack)

    def onTake(self, player, stack):
        self.setChanged()

    def isActive(self):
        """对应 isActive()：槽位是否可用（有些界面会禁用某些格）。"""
        return True

    def __repr__(self):
        return u"<Slot #{} at ({}, {})>".format(self.slot_index, self.x, self.y)


# ============================================================
# AbstractContainerMenu
# ============================================================

class DataSlot(object):
    def __init__(self, getter=None, setter=None):
        self._value = 0
        self._previous_value = 0
        self._getter = getter
        self._setter = setter

    @staticmethod
    def standalone():
        return DataSlot()

    @staticmethod
    def forContainer(data, index):
        return DataSlot(lambda: data.get(index), lambda value: data.set(index, value))

    @staticmethod
    def shared(storage, index):
        from java_stdlib.lang import ArrayIndexOutOfBoundsException
        def check():
            if index < 0 or index >= len(storage):
                raise ArrayIndexOutOfBoundsException("Shared data slot index out of range")
        def get():
            check()
            return storage[index]
        def set(value):
            check()
            storage[index] = int(value)
        return DataSlot(get,set)

    def checkAndClearUpdateFlag(self):
        value = self.get()
        changed = value != self._previous_value
        self._previous_value = value
        return changed

    def get(self):
        return self._getter() if self._getter is not None else self._value

    def set(self, value):
        if self._setter is not None:
            self._setter(int(value))
        else:
            self._value = int(value)


class AbstractContainerMenu(object):
    """
    对应 net.minecraft.world.inventory.AbstractContainerMenu。

    它是「服务端与客户端共享的界面数据模型」：
      服务端管真实容器，客户端管影子副本，靠 menuType + id 对应。

    真实代码只用到几件事：
      - 构造（收容器、玩家背包、标题）
      - 加槽位
      - 让容器知道「玩家还开着这个界面」（`stillValid`）
      - 关界面时清理

    本实现提供槽位/整数/手持栈同步回调；SDK 网络与界面接入须显式配置。
    """

    # 全局自增 id（Java 里由服务端分配，同一玩家不会重复）
    _next_id = [0]

    def __init__(self, container=None, inventory=None, title=None):
        AbstractContainerMenu._next_id[0] += 1
        self._container_id = AbstractContainerMenu._next_id[0]
        menu_type = None
        java_constructor = isinstance(inventory, int)
        if java_constructor:
            menu_type = container
            self._container_id = int(inventory)
            container, inventory = None, None
        self.menuType = menu_type
        self.containerId = self._container_id
        self._container = container
        self._inventory = inventory
        self._title = title
        self.slots = NonNullList.create()
        self._data_slots = []
        self._removed = False
        self._quick_move_calls = 0
        self._synchronizer = None
        self._listeners = []
        self._last_slots = NonNullList.create()
        self._remote_slots = NonNullList.create()
        self._remote_data = []
        self._suppress_remote_updates = False
        self._carried = ItemStack()
        self._remote_carried = ItemStack()
        self._flat_data_slots = []
        self._state_id = 0
        if java_constructor:
            from neoforge.mixin_hooks import dispatch_tail, MENU_TAIL
            dispatch_tail(MENU_TAIL, self, (self.menuType, self.containerId))

    # ---------------- 身份 ----------------

    def getContainerId(self):
        """对应 containerId：菜单实例编号。"""
        return self._container_id

    def getTitle(self):
        """对应 getTitle()：界面标题。"""
        return self._title

    def getContainer(self):
        return self._container

    def getInventory(self):
        return self._inventory

    # ---------------- 槽位 ----------------

    def addSlot(self, slot):
        """对应 addSlot(Slot)：加一个槽位，返回它的下标。"""
        if slot is None:
            raise IllegalArgumentException(u"addSlot 收到 None")
        slot.index = len(self.slots)
        self.slots.add(slot)
        self._last_slots.add(ItemStack())
        self._remote_slots.add(ItemStack())
        return slot

    def getSlot(self, index):
        if int(index) < 0 or int(index) >= len(self.slots):
            raise IllegalArgumentException("Menu slot out of range")
        return self.slots[int(index)]

    def getStateId(self):
        return self._state_id

    def incrementStateId(self):
        self._state_id = (self._state_id + 1) & 32767
        return self._state_id

    def isValidSlotIndex(self, index):
        # The Java 1.21.1 predicate also accepts negative indices. It is not an authorization check.
        return int(index) < len(self.slots)

    def getItems(self):
        result = NonNullList.create()
        for slot in self.slots:
            result.add(slot.getItem())
        return result

    def setItem(self, index, state_id, stack):
        self.getSlot(index).set(stack)
        self._state_id = int(state_id)

    def initializeContents(self, state_id, items, carried):
        # Preserve Java's write order: earlier slots can be changed if a later slot fails.
        for index, stack in enumerate(items):
            self.getSlot(index).set(stack)
        self._carried = carried
        self._state_id = int(state_id)

    def getSlotCount(self):
        return len(self.slots)

    def addDataSlots(self, container_data):
        """对应 addDataSlots(ContainerData)：把进度条数据挂上。"""
        if container_data is None:
            raise IllegalArgumentException(u"addDataSlots 收到 None")
        self._data_slots.append(container_data)
        for index in range(container_data.getCount()):
            self.addDataSlot(DataSlot.forContainer(container_data, index))
        return None

    def getDataSlotCount(self):
        return len(self._flat_data_slots)

    def addDataSlot(self, data_slot):
        self._flat_data_slots.append(data_slot)
        self._remote_data.append(0)
        return data_slot

    def setData(self, index, value):
        if int(index) < 0 or int(index) >= len(self._flat_data_slots):
            raise IllegalArgumentException("Menu data index out of range")
        self._flat_data_slots[int(index)].set(value)

    def getCarried(self):
        return self._carried

    def setCarried(self, stack):
        self._carried = stack

    def getType(self):
        if self.menuType is None:
            raise IllegalStateException("Menu type not configured")
        return self.menuType

    def moveItemStackTo(self, stack, start, end, reverse):
        if self._removed:
            raise IllegalStateException("Menu removed")
        start, end = int(start), int(end)
        if start < 0 or end < start or end > len(self.slots):
            raise IllegalArgumentException("Invalid move slot range")
        indices = list(range(start, end))
        if reverse:
            indices.reverse()
        changed = False
        # Fill matching existing stacks, then the first eligible empty slot.
        for index in indices:
            if stack.isEmpty():
                break
            slot = self.slots[index]
            existing = slot.getItem()
            if not existing.isEmpty() and existing.isSameItemSameComponents(stack):
                amount = min(stack.getCount(), max(0, slot.getMaxStackSize(stack) - existing.getCount()))
                if amount:
                    candidate = existing.copy()
                    candidate.grow(amount)
                    slot.set(candidate)
                    stack.shrink(amount)
                    slot.setChanged()
                    changed = True
        for index in indices:
            if stack.isEmpty():
                break
            slot = self.slots[index]
            if slot.getItem().isEmpty() and slot.mayPlace(stack):
                amount = min(stack.getCount(), slot.getMaxStackSize(stack))
                if amount > 0:
                    slot.setByPlayer(stack.copyWithCount(amount))
                    stack.shrink(amount)
                    slot.setChanged()
                    changed = True
                    break
        return changed

    # ---------------- 扩展点 ----------------

    def quickMoveStack(self, player, index):
        """Abstract in Java: a content menu must supply its actual transfer rules."""
        raise UnsupportedOperationException("Menu quickMoveStack requires content transfer rules")

    def stillValid(self, player):
        """对应 stillValid(Player)：界面是否还有效（玩家没走远）。"""
        if self._container is not None \
                and hasattr(self._container, "stillValid"):
            return self._container.stillValid(player)
        raise UnsupportedOperationException("Menu validity requires container or content permission rules")

    def removed(self, player):
        """对应 removed(Player)：界面关闭时的清理。"""
        if self._removed:
            return None
        self._removed = True
        self._synchronizer = None
        self._listeners = []
        if self._container is not None \
                and hasattr(self._container, "stopOpen"):
            self._container.stopOpen(player)
        return None

    def isRemoved(self):
        return self._removed

    @staticmethod
    def _sameStack(left, right):
        return left.getCount() == right.getCount() and left.isSameItemSameComponents(right)

    def setSynchronizer(self, synchronizer):
        if self._removed:
            raise IllegalStateException("Menu removed")
        self._synchronizer = synchronizer
        self.sendAllDataToRemote()

    def addSlotListener(self, listener):
        if self._removed:
            raise IllegalStateException("Menu removed")
        if listener not in self._listeners:
            self._listeners.append(listener)
            self.broadcastChanges()

    def removeSlotListener(self, listener):
        if listener in self._listeners:
            self._listeners.remove(listener)

    def suppressRemoteUpdates(self):
        self._suppress_remote_updates = True

    def resumeRemoteUpdates(self):
        self._suppress_remote_updates = False

    def setRemoteSlot(self, index, stack):
        self._remote_slots.set(index,stack.copy())

    def setRemoteSlotNoCopy(self, index, stack):
        # Vanilla ignores invalid no-copy indices instead of mutating another slot.
        if 0 <= int(index) < len(self._remote_slots):
            self._remote_slots.set(index,stack)

    def setRemoteCarried(self, stack):
        self._remote_carried = stack.copy()

    def sendAllDataToRemote(self):
        from java_stdlib.java_arrays import JavaArrays
        for index,slot in enumerate(self.slots):
            self._remote_slots.set(index,slot.getItem().copy())
        self._remote_carried = self.getCarried().copy()
        for index,data in enumerate(self._flat_data_slots):
            self._remote_data[index] = data.get()
        if self._synchronizer is not None:
            self._synchronizer.sendInitialData(self,self._remote_slots,self._remote_carried,
                                               JavaArrays.initialized('int',1,self._remote_data))

    def _triggerSlotListeners(self,index,stack,snapshot):
        if not self._sameStack(self._last_slots.get(index),stack):
            saved = snapshot()
            self._last_slots.set(index,saved)
            for listener in list(self._listeners):
                listener.slotChanged(self,index,saved)

    def _synchronizeSlotToRemote(self,index,stack,snapshot):
        if self._suppress_remote_updates:
            return
        if not self._sameStack(self._remote_slots.get(index),stack):
            saved = snapshot()
            self._remote_slots.set(index,saved)
            if self._synchronizer is not None:
                self._synchronizer.sendSlotChange(self,index,saved)

    def _updateDataSlotListeners(self,index,value):
        for listener in list(self._listeners):
            listener.dataChanged(self,index,value)

    def broadcastFullState(self):
        for index,slot in enumerate(self.slots):
            stack = slot.getItem()
            self._triggerSlotListeners(index,stack,lambda: stack)
        for index,data in enumerate(self._flat_data_slots):
            if data.checkAndClearUpdateFlag():
                self._updateDataSlotListeners(index,data.get())
        self.sendAllDataToRemote()

    def broadcastChanges(self):
        if self._removed:
            return None
        self._broadcast_count = getattr(self,"_broadcast_count",0) + 1
        for index,slot in enumerate(self.slots):
            stack = slot.getItem()
            saved = []
            def snapshot():
                if not saved:
                    saved.append(stack.copy())
                return saved[0]
            self._triggerSlotListeners(index,stack,snapshot)
            self._synchronizeSlotToRemote(index,stack,snapshot)
        if not self._suppress_remote_updates and not self._sameStack(self.getCarried(),self._remote_carried):
            self._remote_carried = self.getCarried().copy()
            if self._synchronizer is not None:
                self._synchronizer.sendCarriedChange(self,self._remote_carried)
        for index,data in enumerate(self._flat_data_slots):
            value = data.get()
            if data.checkAndClearUpdateFlag():
                self._updateDataSlotListeners(index,value)
            if not self._suppress_remote_updates and self._remote_data[index] != value:
                self._remote_data[index] = value
                if self._synchronizer is not None:
                    self._synchronizer.sendDataChange(self,index,value)

    # ---------------- 展示 ----------------

    def toString(self):
        return u"{}[id={}, {} 个槽位]".format(
            type(self).__name__, self._container_id, len(self.slots))

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<{}>".format(self.toString())


class RecipeBookMenu(AbstractContainerMenu):
    """
    对应 net.minecraft.world.inventory.RecipeBookMenu。

    带「配方书」的菜单（合成台、熔炉用它）。真实代码里
    `class ... extends RecipeBookMenu`。

    配方书摆放与材料统计尚未实现，调用时明确报告缺失。
    """

    def __init__(self, container=None, inventory=None, title=None):
        AbstractContainerMenu.__init__(self, container, inventory, title)
        self._recipe_book_type = None

    def getRecipeBookType(self):
        """对应 getRecipeBookType()：配方书分类（合成/熔炉/…）。"""
        return self._recipe_book_type

    def setRecipeBookType(self, value):
        self._recipe_book_type = value
        return self

    def fillCraftSlotsStackedContents(self, stacked_contents):
        """对应 fillCraftSlotsStackedContents：把合成格内容喂给配方书。"""
        raise UnsupportedOperationException("Recipe-book stacked contents require a recipe adapter")

    def handlePlacement(self, place_all, recipe, player):
        """Original Java argument order; recipe placement is not implemented yet."""
        raise UnsupportedOperationException("Recipe-book placement requires a recipe/inventory adapter")


# ============================================================
# MenuType / MenuProvider
# ============================================================

from neoforge.menu_interfaces import IMenuTypeExtension,IContainerFactory,MenuSupplier
from minecraft.feature_flags import FeatureElement,FeatureFlags
from minecraft.official_interfaces import _invoke as _invoke_menu_factory
class MenuType(IMenuTypeExtension,FeatureElement):
    """
    对应 net.minecraft.world.inventory.MenuType。

    它是「菜单的注册类型」，真实代码把它注册进 `BuiltInRegistries.MENU`，
    并和客户端的 Screen 关联：

        event.register(MENU_CRAFTING.get(), CraftingManaitaScreen::new);

    `create(id, inventory)` 是引擎开界面时调用的工厂。
    """

    def __init__(self, factory=None, identifier=None, menu_class=None,features=None):
        self._factory = factory
        self._identifier = identifier
        self.menu_class = menu_class
        self._screen_constructor = None
        self._required_features=FeatureFlags.DEFAULT_FLAGS if features is None else features

    def create(self, container_id, inventory,*extra):
        """对应 create(int, Inventory)：按工厂造菜单实例。"""
        if self._factory is None:
            raise UnsupportedOperationException("MenuType has no registered menu factory")
        if len(extra)>1:raise TypeError('MenuType.create accepts at most one extra buffer')
        if isinstance(self._factory,IContainerFactory) and extra:
            return _invoke_menu_factory(self._factory,'create',(container_id,inventory,extra[0]),('int','net.minecraft.world.entity.player.Inventory','net.minecraft.network.RegistryFriendlyByteBuf'))
        if isinstance(self._factory,MenuSupplier):
            return _invoke_menu_factory(self._factory,'create',(container_id,inventory),('int','net.minecraft.world.entity.player.Inventory'))
        return self._factory(container_id, inventory)

    def requiredFeatures(self):return self._required_features

    def setScreenConstructor(self, constructor):
        """
        记下客户端界面构造器（真实代码里由 RegisterMenuScreensEvent 配）。

        注意：真实引擎用它在客户端造 Screen；基岩版没有同一套界面体系，
        δ 层会跳过那个事件 —— 这里只是**把关联关系记下来**，
        便于诊断「这个菜单有没有配界面」。
        """
        self._screen_constructor = constructor
        return self

    def getScreenConstructor(self):
        return self._screen_constructor

    def hasScreen(self):
        return self._screen_constructor is not None

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
        return u"<MenuType {}>".format(self._identifier or u"未注册")


class MenuProvider(MenuProviderInterface):
    """
    对应 net.minecraft.world.MenuProvider。

    「能提供一个菜单的东西」—— 方块实体实现它，
    玩家右键时引擎调 `createMenu` 拿到菜单。

    真实用法：
        player.openMenu(state.getMenuProvider(level, pos));
        sender.openMenu((MenuProvider) new ...);

    它有三个方法，只有 `createMenu` 是必须的；
    `getDisplayName` 和 `shouldTriggerClientSideContainerClosingOnOpen`
    在 Java 里是 default 方法，这里给默认实现。
    """

    def createMenu(self, container_id, inventory, player=None):
        """对应 createMenu(int, Inventory, Player)。子类必须覆盖。"""
        raise NotImplementedError()

    def getDisplayName(self):
        """对应 getDisplayName()：界面标题。"""
        return None

    def shouldTriggerClientSideContainerClosingOnOpen(self):
        """对应 shouldTriggerClientSideContainerClosingOnOpen()。默认真。"""
        return True


# ============================================================
# Containers
# ============================================================

class Containers(object):
    """
    对应 net.minecraft.world.Containers。

    真实用法：
        Containers.dropContents(level, pos, container);
    方块被破坏时把容器里的东西撒出来。
    """

    @staticmethod
    def dropContents(level, pos, container):
        """
        对应 dropContents(Level, BlockPos, Container)。

        把容器里所有非空槽位清空并交给世界掉落。
        返回掉落的物品栈列表 —— 真实引擎不返回东西，
        但把清单返回出来让自测能验证「确实撒出来了」。
        """
        if container is None:
            raise IllegalArgumentException(u"dropContents 收到 None")
        if level is None or not hasattr(level, "getAccess") or not hasattr(level.getAccess(), "noteDroppedItems"):
            raise IllegalStateException("Container drops require an implemented world drop adapter")
        dropped = []
        indices = []
        size = container.getContainerSize()
        for index in range(size):
            stack = container.getItem(index)
            if stack is None or stack.isEmpty():
                continue
            dropped.append(stack.copy())
            indices.append(index)
        if level is not None and hasattr(level, "getAccess"):
            access = level.getAccess()
            if hasattr(access, "noteDroppedItems"):
                access.noteDroppedItems(pos, dropped)
        for index in indices:
            container.setItem(index, ItemStack())
        container.setChanged()
        return dropped

    @staticmethod
    def dropItemStack(level, x, y, z, stack):
        """对应 dropItemStack(Level, double, double, double, ItemStack)。"""
        if level is not None and hasattr(level, "getAccess"):
            access = level.getAccess()
            if hasattr(access, "noteDroppedItems"):
                access.noteDroppedItems((x, y, z), [stack])
        return stack


# ============================================================
# 名称映射表
# ============================================================

MenuType.MenuSupplier=MenuSupplier
JAVA_MAP = {
    "net.minecraft.world.inventory.DataSlot": DataSlot,
    "net.minecraft.world.inventory.SimpleContainerData": ContainerData,
    "net.minecraft.world.inventory.AbstractContainerMenu":
        AbstractContainerMenu,
    "net.minecraft.world.inventory.RecipeBookMenu": RecipeBookMenu,
    "net.minecraft.world.inventory.MenuType": MenuType,
    "net.minecraft.world.inventory.Slot": Slot,
    "net.minecraft.world.inventory.ContainerData": ContainerDataInterface,
    "net.minecraft.world.MenuProvider": MenuProviderInterface,
    "net.minecraft.world.Containers": Containers,
}


__all__ = [
    "ContainerData", "Slot",
    "AbstractContainerMenu", "RecipeBookMenu",
    "MenuType", "MenuProvider", "Containers",
    "JAVA_MAP",
]
