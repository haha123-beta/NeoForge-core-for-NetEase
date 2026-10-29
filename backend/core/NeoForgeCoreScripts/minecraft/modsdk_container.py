# -*- coding: utf-8 -*-
"""Live block containers via documented ItemCompServer APIs.

GetContainerSize/GetContainerItem(getUserData=True)/SpawnItemToContainer.
Unsupported Java components require a codec; never strip unknown native metadata.
No multi-slot atomicity is promised by these SDK calls.
"""
from __future__ import absolute_import
import copy
from minecraft.block_entity import Container
from minecraft.item import ItemStack
from minecraft.modsdk_entity_access import EngineBridgeError
from java_stdlib._base import IllegalArgumentException
try:
    _integer_types = (int, long)
except NameError:
    _integer_types = (int,)


class NativeItemCodec(object):
    def __init__(self):
        self._entries = []

    def register(self, item, identifier, aux=0):
        if item is None or not identifier or ":" not in identifier:
            raise IllegalArgumentException("Explicit item/identifier required")
        for existing, name, value in self._entries:
            if existing is item or (name == identifier and value == int(aux)):
                raise IllegalArgumentException("Duplicate native item mapping")
        self._entries.append((item, identifier, int(aux)))
        return self

    def decode(self, data):
        if data is None or data == {}:
            return ItemStack()
        if not isinstance(data, dict):
            raise EngineBridgeError("Malformed native item")
        name = data.get("newItemName", data.get("itemName"))
        count = data.get("count")
        if not isinstance(count, _integer_types) or isinstance(count, bool) or not 0 <= count <= 2147483647:
            raise EngineBridgeError("Invalid native item count")
        if count == 0 or name == "minecraft:air":
            return ItemStack()
        aux = data.get("newAuxValue", data.get("auxValue", 0))
        for item, identifier, value in self._entries:
            if identifier == name and value == aux:
                stack = ItemStack(item, count)
                stack._native_item_data = copy.deepcopy(data)
                stack._native_item_components = {k: copy.deepcopy(v) for k, v in data.items() if k != "count"}
                return stack
        raise EngineBridgeError("Unmapped native item: " + str((name, aux)))

    def encode(self, stack):
        if not isinstance(stack, ItemStack):
            raise IllegalArgumentException("Expected ItemStack")
        if stack.isEmpty():
            return {}
        if stack.getCustomData() or getattr(stack, "_display_name", None) is not None:
            raise EngineBridgeError("Java component/name conversion requires an explicit item codec")
        for item, name, aux in self._entries:
            if stack.getItem() is item:
                data = copy.deepcopy(getattr(stack, "_native_item_data", {"itemName": name, "auxValue": aux}))
                if data.get("newItemName", data.get("itemName")) != name or data.get("newAuxValue", data.get("auxValue", 0)) != aux:
                    raise EngineBridgeError("Native item metadata belongs to another item")
                data["count"] = int(stack.getCount())
                return data
        raise EngineBridgeError("Unmapped Java item")


class ContainerWriteError(EngineBridgeError):
    def __init__(self, message, applied_slots):
        EngineBridgeError.__init__(self, message)
        self.applied_slots = list(applied_slots)


class ModSdkContainer(Container):
    def __init__(self, server_api, pos, dimension_id, codec, validity=None):
        self.position = (int(pos.getX()), int(pos.getY()), int(pos.getZ()))
        self.dimension_id = int(dimension_id)
        self.codec = codec
        self.validity = validity
        self.component = server_api.GetEngineCompFactory().CreateItem(server_api.GetLevelId())
        self._initialize()

    def _initialize(self):
        self._size = self.component.GetContainerSize(self.position, self.dimension_id)
        if not isinstance(self._size, int) or self._size < 0:
            raise EngineBridgeError("Native container unavailable or unsupported")
        self._cache = {}
        self._baseline = {}
        self._closed = False
        self.change_count = 0

    def _check(self, index=None):
        if self._closed:
            raise EngineBridgeError("Native container closed")
        if self.component.GetContainerSize(self.position, self.dimension_id) != self._size:
            raise EngineBridgeError("Native container unloaded, removed or resized")
        if index is not None and (int(index) < 0 or int(index) >= self._size):
            raise IllegalArgumentException("Native container slot out of range")

    def _read(self, index):
        raw = self.component.GetContainerItem(self.position, int(index), self.dimension_id, True)
        stack = self.codec.decode(copy.deepcopy(raw))
        return stack, self.codec.encode(stack)

    def getContainerSize(self):
        self._check()
        return self._size

    def getItem(self, index):
        self._check(index)
        index = int(index)
        if index in self._cache and self.codec.encode(self._cache[index]) != self._baseline[index]:
            return self._cache[index]
        stack, raw = self._read(index)
        self._cache[index], self._baseline[index] = stack, raw
        return stack

    def _write(self, index, stack):
        self._check(index)
        if not stack.isEmpty() and stack.getCount() > min(self.getMaxStackSize(), stack.getMaxStackSize()):
            raise IllegalArgumentException("Native container stack exceeds slot limit")
        encoded = self.codec.encode(stack)
        current, raw = self._read(index)
        if index in self._baseline and raw != self._baseline[index]:
            raise EngineBridgeError("Native slot changed externally; refusing stale write")
        if raw != encoded:
            if not self.component.SpawnItemToContainer(copy.deepcopy(encoded), int(index), self.position, self.dimension_id):
                raise EngineBridgeError("Native container write rejected")
            actual, verified = self._read(index)
            if verified != encoded:
                raise EngineBridgeError("Native slot changed but readback mismatched; rollback not claimed")
        self._cache[index], self._baseline[index] = stack.copy(), copy.deepcopy(encoded)

    def setItem(self, index, stack):
        self._write(int(index), stack)
        self.change_count += 1

    def setChanged(self):
        self._check()
        applied = []
        for index in sorted(self._cache):
            stack = self._cache[index]
            if self.codec.encode(stack) != self._baseline[index]:
                try:
                    self._write(index, stack)
                    applied.append(index)
                except Exception as error:
                    raise ContainerWriteError(str(error), applied)
        self.change_count += 1

    def removeItem(self, index, amount):
        stack = self.getItem(index)
        if int(amount) <= 0 or stack.isEmpty():
            return ItemStack()
        remaining = stack.copy()
        taken = remaining.split(int(amount))
        self.setItem(index, remaining)
        return taken

    def removeItemNoUpdate(self, index):
        stack = self.getItem(index).copy()
        self._write(int(index), ItemStack())
        return stack

    def isEmpty(self):
        return all(self.getItem(index).isEmpty() for index in range(self.getContainerSize()))

    def clearContent(self):
        self._check()
        applied = []
        for index in range(self._size):
            try:
                self.setItem(index, ItemStack())
                applied.append(index)
            except Exception as error:
                raise ContainerWriteError(str(error), applied)

    def stillValid(self, player):
        if self._closed or self.validity is None:
            return False
        try:
            self._check()
            return bool(self.validity(player, self.position, self.dimension_id))
        except EngineBridgeError:
            return False

    def close(self):
        # Dirty uncommitted mutations are not written as an implicit close side effect.
        dirty = []
        for index in self._cache:
            try:
                if self.codec.encode(self._cache[index]) != self._baseline[index]:
                    dirty.append(index)
            except Exception:
                dirty.append(index)
        self._closed = True
        self._cache.clear()
        self._baseline.clear()
        self.component = None
        return dirty


class _EnderBackend(object):
    def __init__(self, component, player_id, available):
        self.component, self.player_id, self.available = component, player_id, available

    def GetContainerSize(self, pos, dimension):
        return 27 if self.available(self.player_id) else -1

    def GetContainerItem(self, pos, index, dimension, user_data):
        return self.component.GetEnderChestItem(self.player_id, index, user_data)

    def SpawnItemToContainer(self, data, index, pos, dimension):
        return self.component.SpawnItemToEnderChest(data, index)


class ModSdkEnderChest(ModSdkContainer):
    """Per-player storage; availability must come from trusted engine player state."""
    def __init__(self, server_api, player_id, codec, available):
        if not player_id or not callable(available):
            raise IllegalArgumentException("Native player ID and availability resolver required")
        self.position, self.dimension_id = (0, 0, 0), 0
        self.codec = codec
        self.validity = lambda player, pos, dim: player == player_id and available(player_id)
        component = server_api.GetEngineCompFactory().CreateItem(player_id)
        self.component = _EnderBackend(component, player_id, available)
        self._initialize()
