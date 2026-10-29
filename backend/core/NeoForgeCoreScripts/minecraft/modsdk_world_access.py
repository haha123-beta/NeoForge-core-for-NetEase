# -*- coding: utf-8 -*-
"""Explicit block-state bridge. No guessed Java/Bedrock state or flag mappings.

Contracts: official ModSDK BlockInfo.GetBlockNew/SetBlockNew and
BlockState.GetBlockStates/GetBlockAuxValueFromStates (local refs/mcn-docs).
Write policy must explicitly map Java flags to the native neighbor-update bit.
Same-identifier state changes are refused: SetBlockNew may clear containers.
"""
from __future__ import absolute_import
from minecraft.level_access import ILevelAccess
from minecraft.modsdk_entity_access import EngineBridgeError
from minecraft.block import BlockState
from java_stdlib._base import IllegalArgumentException


class BlockStateMappings(object):
    """Finite, reviewed state mappings; registration has no engine side effects."""
    def __init__(self):
        self._entries = []

    @staticmethod
    def _key(name, values):
        if not isinstance(name, (str, type(u""))) or not name or ":" not in name:
            raise IllegalArgumentException("A namespaced native block identifier is required")
        if not isinstance(values, dict):
            raise IllegalArgumentException("Native states must be a dictionary")
        pairs = []
        for key, value in values.items():
            if not isinstance(key, (str, type(u""))) or not isinstance(value, (str, type(u""), int, bool)):
                raise IllegalArgumentException("Native states must contain scalar named values")
            pairs.append((key, type(value).__name__, value))
        return (name, tuple(sorted(pairs)))

    def register(self, state, native_name, native_states):
        if not isinstance(state, BlockState):
            raise IllegalArgumentException("Mapping requires a BlockState")
        key = self._key(native_name, native_states)
        for existing, name, values, native_key in self._entries:
            if existing.equals(state) or native_key == key:
                raise IllegalArgumentException("Duplicate or ambiguous block-state mapping")
        self._entries.append((state, native_name, dict(native_states), key))
        return self

    def encode(self, state):
        for existing, name, values, key in self._entries:
            if existing.equals(state):
                return name, dict(values)
        raise EngineBridgeError("Unmapped Java block state: " + str(state))

    def decode(self, name, values):
        key = self._key(name, values)
        for state, native_name, native_values, native_key in self._entries:
            if key == native_key:
                return state
        raise EngineBridgeError("Unmapped native block state: " + str(key))


class ModSdkWorldAccess(ILevelAccess):
    name = "modsdk-world"

    def __init__(self, server_api, dimension_id, mappings, write_policy=None):
        ILevelAccess.__init__(self)
        if not isinstance(mappings, BlockStateMappings):
            raise IllegalArgumentException("Explicit block-state mappings required")
        if write_policy is not None and not callable(write_policy):
            raise IllegalArgumentException("World write policy must be callable")
        self.server_api = server_api
        self._containers = []
        self.dimension_id = int(dimension_id)
        self.mappings = mappings
        self.write_policy = write_policy
        factory = server_api.GetEngineCompFactory()
        level_id = server_api.GetLevelId()
        self.blocks = factory.CreateBlockInfo(level_id)
        self.states = factory.CreateBlockState(level_id)
        self._closed = False

    def _unsupported(self, method_name, *args):
        self.unsupported.append((method_name, args))
        raise EngineBridgeError("Unimplemented ModSDK world operation: " + str(method_name))

    def _position(self, pos):
        if self._closed:
            raise EngineBridgeError("World access is closed")
        return (int(pos.getX()), int(pos.getY()), int(pos.getZ()))

    def _read(self, pos):
        block = self.blocks.GetBlockNew(pos, self.dimension_id)
        values = self.states.GetBlockStates(pos, self.dimension_id)
        if not isinstance(block, dict) or not block.get("name") or not isinstance(values, dict):
            raise EngineBridgeError("Cannot read block in loaded terrain: " + str(pos))
        return block["name"], values

    def getBlockState(self, pos):
        name, values = self._read(self._position(pos))
        return self.mappings.decode(name, values)

    def setBlock(self, pos, state, flags=3):
        position = self._position(pos)
        name, values = self.mappings.encode(state)
        old_name, old_values = self._read(position)
        if self.mappings._key(name, values) == self.mappings._key(old_name, old_values):
            return False  # SDK same-state writes can still clear container inventory.
        if old_name == name:
            raise EngineBridgeError("Same-identifier state mutation requires a container-safe state/update bridge")
        if self.write_policy is None:
            raise EngineBridgeError("Java block update flags have no configured native policy")
        neighbors = self.write_policy(flags)
        if not isinstance(neighbors, bool):
            raise EngineBridgeError("Native update policy must return a boolean or raise")
        aux = self.states.GetBlockAuxValueFromStates(name, dict(values))
        if not isinstance(aux, int) or isinstance(aux, bool) or aux < 0:
            raise EngineBridgeError("Native state-to-legacy-aux conversion failed")
        changed = self.blocks.SetBlockNew(position, {"name": name, "aux": aux},
                                          0, self.dimension_id, True, neighbors)
        if not changed:
            return False
        actual_name, actual_values = self._read(position)
        if self.mappings._key(actual_name, actual_values) != self.mappings._key(name, values):
            raise EngineBridgeError("Native block write changed terrain but readback differs; no rollback claimed")
        return True

    def isClientSide(self):
        return False

    def openContainer(self, pos, codec, validity=None):
        self._position(pos)
        from minecraft.modsdk_container import ModSdkContainer
        container = ModSdkContainer(self.server_api, pos, self.dimension_id, codec, validity)
        self._containers.append(container)
        return container

    def close(self):
        self._closed = True
        errors = []
        for container in self._containers:
            try:
                dirty = container.close()
                if dirty:
                    errors.append("Uncommitted container slots: " + str(dirty))
            except Exception as error:
                errors.append(str(error))
        self._containers = []
        self.server_api = None
        self.blocks = None
        self.states = None
        if errors:
            raise EngineBridgeError("; ".join(errors))
