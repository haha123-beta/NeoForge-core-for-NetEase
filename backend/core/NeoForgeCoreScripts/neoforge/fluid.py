# -*- coding: utf-8 -*-
"""Fluid identity references and component-free fluid stacks; no native flow simulation."""
from __future__ import absolute_import
from java_stdlib._base import IllegalArgumentException


class Fluid(object):
    def __init__(self, identifier):
        self.identifier = identifier

    def getIdentifier(self):
        return self.identifier

    def toString(self):
        return self.identifier

    def getFluidType(self):
        raise NotImplementedError("FluidType properties and native fluid registration are not integrated")


class Fluids(object):
    EMPTY = Fluid("minecraft:empty")
    WATER = Fluid("minecraft:water")
    FLOWING_WATER = Fluid("minecraft:flowing_water")
    LAVA = Fluid("minecraft:lava")
    FLOWING_LAVA = Fluid("minecraft:flowing_lava")


class FluidStack(object):
    EMPTY = None

    def __init__(self, fluid, amount, *patch):
        if patch:
            raise NotImplementedError("Fluid data component patches are not integrated")
        value = getattr(fluid, "value", None)
        self.fluid = value() if callable(value) else fluid
        if self.fluid is None:
            raise IllegalArgumentException("Fluid cannot be null")
        self.amount = int(amount)

    def isEmpty(self):
        return self is FluidStack.EMPTY or self.fluid is Fluids.EMPTY or self.amount <= 0

    def getFluid(self):
        return Fluids.EMPTY if self.isEmpty() else self.fluid

    def getAmount(self):
        return 0 if self.isEmpty() else self.amount

    def setAmount(self, amount):
        self.amount = int(amount)

    def grow(self, amount):
        self.setAmount(self.getAmount() + int(amount))

    def shrink(self, amount):
        self.grow(-int(amount))

    def copy(self):
        return FluidStack.EMPTY if self.isEmpty() else FluidStack(self.fluid, self.amount)

    def copyWithAmount(self, amount):
        if self.isEmpty():
            return FluidStack.EMPTY
        result = self.copy()
        result.setAmount(amount)
        return result

    def split(self, amount):
        taken = min(int(amount), self.getAmount())
        result = self.copyWithAmount(taken)
        self.shrink(taken)
        return result

    @staticmethod
    def isSameFluidSameComponents(first, second):
        # All accepted stacks currently have an empty component patch.
        return first.getFluid() is second.getFluid()

    def _is_fluid(self, fluid):
        if not isinstance(fluid, Fluid):
            raise NotImplementedError("Fluid tag/type overloads are not integrated")
        return self.getFluid() is fluid


setattr(FluidStack, "is", FluidStack._is_fluid)
FluidStack.EMPTY = FluidStack(Fluids.EMPTY, 0)

JAVA_MAP = {
    "net.minecraft.world.level.material.Fluid": Fluid,
    "net.minecraft.world.level.material.Fluids": Fluids,
    "net.neoforged.neoforge.fluids.FluidStack": FluidStack,
}
