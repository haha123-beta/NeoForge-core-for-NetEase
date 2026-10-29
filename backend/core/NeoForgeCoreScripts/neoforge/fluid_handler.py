# -*- coding: utf-8 -*-
"""Component-free NeoForge 21.1.233 tank operations. World flow and codecs remain gaps."""
from __future__ import absolute_import
from neoforge.fluid import FluidStack


class FluidAction(object):
    def __init__(self, name):
        self._name = name
    def name(self):
        return self._name
    def execute(self):
        return self is FluidAction.EXECUTE
    def simulate(self):
        return self is FluidAction.SIMULATE


FluidAction.EXECUTE = FluidAction("EXECUTE")
FluidAction.SIMULATE = FluidAction("SIMULATE")


class IFluidHandler(object):
    FluidAction = FluidAction
    def getTanks(self):
        raise NotImplementedError("Implement getTanks")
    def getFluidInTank(self, tank):
        raise NotImplementedError("Implement getFluidInTank")
    def getTankCapacity(self, tank):
        raise NotImplementedError("Implement getTankCapacity")
    def isFluidValid(self, tank, stack):
        raise NotImplementedError("Implement isFluidValid")
    def fill(self, resource, action):
        raise NotImplementedError("Implement fill")
    def drain(self, resource, action):
        raise NotImplementedError("Implement drain")


class IFluidHandlerItem(IFluidHandler):
    def getContainer(self):
        raise NotImplementedError("Implement getContainer")


class IFluidTank(object):
    def getFluid(self):
        raise NotImplementedError("Implement getFluid")
    def getFluidAmount(self):
        raise NotImplementedError("Implement getFluidAmount")
    def getCapacity(self):
        raise NotImplementedError("Implement getCapacity")
    def isFluidValid(self, stack):
        raise NotImplementedError("Implement isFluidValid")
    def fill(self, resource, action):
        raise NotImplementedError("Implement fill")
    def drain(self, resource, action):
        raise NotImplementedError("Implement drain")


class FluidTank(IFluidHandler, IFluidTank):
    def __init__(self, capacity, validator=None):
        self.capacity = int(capacity)
        self.validator = validator or (lambda value: True)
        self.fluid = FluidStack.EMPTY

    def setCapacity(self, capacity):
        self.capacity = int(capacity)
        return self

    def setValidator(self, validator):
        if validator is not None:
            self.validator = validator
        return self

    def isFluidValid(self, *args):
        if len(args) not in (1, 2):
            raise TypeError("Expected stack or tank/stack")
        method = getattr(self.validator, "test", None)
        return bool((method if callable(method) else self.validator)(args[-1]))

    def getCapacity(self):
        return self.capacity
    def getFluid(self):
        return self.fluid
    def getFluidAmount(self):
        return self.fluid.getAmount()
    def getTanks(self):
        return 1
    def getFluidInTank(self, tank):
        return self.fluid
    def getTankCapacity(self, tank):
        return self.capacity
    def getSpace(self):
        return max(0, self.capacity - self.getFluidAmount())
    def isEmpty(self):
        return self.fluid.isEmpty()
    def setFluid(self, stack):
        self.fluid = stack
    def onContentsChanged(self):
        pass

    def fill(self, resource, action):
        if resource.isEmpty() or not self.isFluidValid(resource):
            return 0
        if action.simulate():
            if self.fluid.isEmpty():
                return min(self.capacity, resource.getAmount())
            if not FluidStack.isSameFluidSameComponents(self.fluid, resource):
                return 0
            return min(self.capacity - self.getFluidAmount(), resource.getAmount())
        if self.fluid.isEmpty():
            self.fluid = resource.copyWithAmount(min(self.capacity, resource.getAmount()))
            self.onContentsChanged()
            return self.getFluidAmount()
        if not FluidStack.isSameFluidSameComponents(self.fluid, resource):
            return 0
        filled = self.capacity - self.getFluidAmount()
        if resource.getAmount() < filled:
            self.fluid.grow(resource.getAmount())
            filled = resource.getAmount()
        else:
            self.fluid.setAmount(self.capacity)
        if filled > 0:
            self.onContentsChanged()
        return filled

    def drain(self, resource, action):
        if isinstance(resource, FluidStack):
            if resource.isEmpty() or not FluidStack.isSameFluidSameComponents(resource, self.fluid):
                return FluidStack.EMPTY
            resource = resource.getAmount()
        drained = min(int(resource), self.getFluidAmount())
        result = self.fluid.copyWithAmount(drained)
        if action.execute() and drained > 0:
            self.fluid.shrink(drained)
            self.onContentsChanged()
        return result

    def readFromNBT(self, provider, tag):
        raise NotImplementedError("FluidStack registry/component-aware NBT parse is not integrated")
    def writeToNBT(self, provider, tag):
        raise NotImplementedError("FluidStack registry/component-aware NBT save is not integrated")


JAVA_MAP = {
    "net.neoforged.neoforge.fluids.IFluidTank": IFluidTank,
    "net.neoforged.neoforge.fluids.capability.IFluidHandler": IFluidHandler,
    "net.neoforged.neoforge.fluids.capability.IFluidHandler$FluidAction": FluidAction,
    "net.neoforged.neoforge.fluids.capability.IFluidHandlerItem": IFluidHandlerItem,
    "net.neoforged.neoforge.fluids.capability.templates.FluidTank": FluidTank,
}
