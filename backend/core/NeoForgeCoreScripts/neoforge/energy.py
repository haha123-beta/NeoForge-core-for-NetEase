# -*- coding: utf-8 -*-
"""In-memory NeoForge 21.1.233 energy storage; no native network is assumed."""
from __future__ import absolute_import
from minecraft.nbt import IntTag
from neoforge.attachment import INBTSerializable
from java_stdlib._base import IllegalArgumentException


class IEnergyStorage(object):
    def receiveEnergy(self, toReceive, simulate):
        raise NotImplementedError("Implement receiveEnergy")
    def extractEnergy(self, toExtract, simulate):
        raise NotImplementedError("Implement extractEnergy")
    def getEnergyStored(self):
        raise NotImplementedError("Implement getEnergyStored")
    def getMaxEnergyStored(self):
        raise NotImplementedError("Implement getMaxEnergyStored")
    def canExtract(self):
        raise NotImplementedError("Implement canExtract")
    def canReceive(self):
        raise NotImplementedError("Implement canReceive")


class EnergyStorage(IEnergyStorage, INBTSerializable):
    def __init__(self, capacity, maxReceive=None, maxExtract=None, energy=0):
        self.capacity = int(capacity)
        self.maxReceive = self.capacity if maxReceive is None else int(maxReceive)
        self.maxExtract = self.maxReceive if maxExtract is None else int(maxExtract)
        self.energy = max(0, min(self.capacity, int(energy)))

    def receiveEnergy(self, toReceive, simulate):
        if not self.canReceive() or toReceive <= 0:
            return 0
        accepted = min(max(0, self.capacity - self.energy), self.maxReceive, int(toReceive))
        if not simulate:
            self.energy += accepted
        return accepted

    def extractEnergy(self, toExtract, simulate):
        if not self.canExtract() or toExtract <= 0:
            return 0
        extracted = min(self.energy, self.maxExtract, int(toExtract))
        if not simulate:
            self.energy -= extracted
        return extracted

    def getEnergyStored(self):
        return self.energy

    def getMaxEnergyStored(self):
        return self.capacity

    def canExtract(self):
        return self.maxExtract > 0

    def canReceive(self):
        return self.maxReceive > 0

    def serializeNBT(self, provider):
        return IntTag.valueOf(self.getEnergyStored())

    def deserializeNBT(self, provider, tag):
        if not isinstance(tag, IntTag):
            raise IllegalArgumentException("EnergyStorage requires IntTag")
        self.energy = tag.getAsInt()


JAVA_MAP = {
    "net.neoforged.neoforge.energy.IEnergyStorage": IEnergyStorage,
    "net.neoforged.neoforge.energy.EnergyStorage": EnergyStorage,
}
