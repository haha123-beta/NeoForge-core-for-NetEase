# -*- coding: utf-8 -*-
"""21.1.233 item handler operations; registry-aware NBT remains an explicit gap."""
from __future__ import absolute_import
from minecraft.item import Item, ItemStack
from neoforge.attachment import INBTSerializable


class IItemHandler(object):
    def getSlots(self):
        raise NotImplementedError("Implement getSlots")
    def getStackInSlot(self, slot):
        raise NotImplementedError("Implement getStackInSlot")
    def insertItem(self, slot, stack, simulate):
        raise NotImplementedError("Implement insertItem")
    def extractItem(self, slot, amount, simulate):
        raise NotImplementedError("Implement extractItem")
    def getSlotLimit(self, slot):
        raise NotImplementedError("Implement getSlotLimit")
    def isItemValid(self, slot, stack):
        raise NotImplementedError("Implement isItemValid")


class IItemHandlerModifiable(IItemHandler):
    def setStackInSlot(self, slot, stack):
        raise NotImplementedError("Implement setStackInSlot")


class ItemStackHandler(IItemHandlerModifiable, INBTSerializable):
    def __init__(self, size=1):
        if isinstance(size, list):
            if any(not isinstance(stack, ItemStack) for stack in size):
                raise ValueError("Expected non-null ItemStack list")
            self.stacks = size
        else:
            self.setSize(size)

    def setSize(self, size):
        size = int(size)
        if size < 0:
            raise ValueError("Negative inventory size")
        self.stacks = [ItemStack.EMPTY for unused in range(size)]

    def validateSlotIndex(self, slot):
        if slot < 0 or slot >= len(self.stacks):
            raise RuntimeError("Slot out of range: " + str(slot))

    def getSlots(self):
        return len(self.stacks)

    def getStackInSlot(self, slot):
        self.validateSlotIndex(slot)
        return self.stacks[slot]

    def setStackInSlot(self, slot, stack):
        self.validateSlotIndex(slot)
        if not isinstance(stack, ItemStack):
            raise ValueError("Expected ItemStack")
        self.stacks[slot] = stack
        self.onContentsChanged(slot)

    def getSlotLimit(self, slot):
        return Item.ABSOLUTE_MAX_STACK_SIZE

    def getStackLimit(self, slot, stack):
        return min(self.getSlotLimit(slot), stack.getMaxStackSize())

    def isItemValid(self, slot, stack):
        return True

    def insertItem(self, slot, stack, simulate):
        if stack.isEmpty():
            return ItemStack.EMPTY
        if not self.isItemValid(slot, stack):
            return stack
        self.validateSlotIndex(slot)
        existing = self.stacks[slot]
        limit = self.getStackLimit(slot, stack)
        if not existing.isEmpty():
            if not stack.isSameItemSameComponents(existing):
                return stack
            limit -= existing.getCount()
        if limit <= 0:
            return stack
        reached = stack.getCount() > limit
        if not simulate:
            if existing.isEmpty():
                self.stacks[slot] = stack.copyWithCount(limit) if reached else stack
            else:
                existing.grow(limit if reached else stack.getCount())
            self.onContentsChanged(slot)
        return stack.copyWithCount(stack.getCount() - limit) if reached else ItemStack.EMPTY

    def extractItem(self, slot, amount, simulate):
        if amount == 0:
            return ItemStack.EMPTY
        self.validateSlotIndex(slot)
        existing = self.stacks[slot]
        if existing.isEmpty():
            return ItemStack.EMPTY
        taken = min(amount, existing.getMaxStackSize())
        if existing.getCount() <= taken:
            if simulate:
                return existing.copy()
            self.stacks[slot] = ItemStack.EMPTY
            self.onContentsChanged(slot)
            return existing
        if not simulate:
            self.stacks[slot] = existing.copyWithCount(existing.getCount() - taken)
            self.onContentsChanged(slot)
        return existing.copyWithCount(taken)

    def serializeNBT(self, provider):
        raise NotImplementedError("ItemStack codec and registry-aware NBT save are not integrated")

    def deserializeNBT(self, provider, tag):
        raise NotImplementedError("ItemStack codec and registry-aware NBT parse are not integrated")

    def onContentsChanged(self, slot):
        pass

    def onLoad(self):
        pass


JAVA_MAP = {
    "net.neoforged.neoforge.items.IItemHandler": IItemHandler,
    "net.neoforged.neoforge.items.IItemHandlerModifiable": IItemHandlerModifiable,
    "net.neoforged.neoforge.items.ItemStackHandler": ItemStackHandler,
}
