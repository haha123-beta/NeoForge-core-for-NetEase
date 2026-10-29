import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
pkg = Package()
fluid = pkg.load('neoforge.fluid')
handlers = pkg.load('neoforge.fluid_handler')
capabilities = pkg.load('neoforge.capabilities')


class FluidTests(unittest.TestCase):
    def test_fill_simulation_capacity_mismatch_and_drain_overloads(self):
        tank = handlers.FluidTank(1000)
        source = fluid.FluidStack(fluid.Fluids.WATER, 750)
        action = handlers.FluidAction
        self.assertEqual(tank.fill(source, action.SIMULATE), 750)
        self.assertTrue(tank.isEmpty())
        self.assertEqual(tank.fill(source, action.EXECUTE), 750)
        self.assertEqual(source.getAmount(), 750)
        self.assertEqual(tank.fill(fluid.FluidStack(fluid.Fluids.WATER, 600), action.EXECUTE), 250)
        self.assertEqual(tank.getFluidAmount(), 1000)
        self.assertEqual(tank.getSpace(), 0)
        self.assertEqual(tank.fill(fluid.FluidStack(fluid.Fluids.LAVA, 100), action.EXECUTE), 0)
        self.assertEqual(tank.drain(500, action.SIMULATE).getAmount(), 500)
        self.assertEqual(tank.getFluidAmount(), 1000)
        self.assertTrue(tank.drain(fluid.FluidStack(fluid.Fluids.LAVA, 100), action.EXECUTE).isEmpty())
        self.assertEqual(tank.drain(fluid.FluidStack(fluid.Fluids.WATER, 300), action.EXECUTE).getAmount(), 300)
        self.assertEqual(tank.getFluidAmount(), 700)
        self.assertEqual(tank.drain(900, action.EXECUTE).getAmount(), 700)
        self.assertTrue(tank.isEmpty())

    def test_validator_copy_identity_keywords_and_explicit_gaps(self):
        tank = handlers.FluidTank(100, lambda stack: stack.getFluid() is fluid.Fluids.WATER)
        water = fluid.FluidStack(fluid.Fluids.WATER, 50)
        lava = fluid.FluidStack(fluid.Fluids.LAVA, 50)
        self.assertEqual(tank.fill(lava, handlers.FluidAction.EXECUTE), 0)
        self.assertTrue(tank.isFluidValid(0, water))
        clone = water.copy()
        clone.shrink(20)
        self.assertEqual(water.getAmount(), 50)
        self.assertEqual(clone.getAmount(), 30)
        self.assertTrue(getattr(clone, 'is')(fluid.Fluids.WATER))
        self.assertTrue(fluid.FluidStack.isSameFluidSameComponents(clone, water))
        self.assertIs(fluid.FluidStack.EMPTY.getFluid(), fluid.Fluids.EMPTY)
        self.assertIs(fluid.FluidStack.EMPTY.copy(), fluid.FluidStack.EMPTY)
        with self.assertRaises(NotImplementedError):
            fluid.FluidStack(fluid.Fluids.WATER, 10, {})
        with self.assertRaises(NotImplementedError):
            tank.writeToNBT(None, None)
        self.assertIs(capabilities.Capabilities.FluidHandler.ITEM.typeClass(), handlers.IFluidHandlerItem)
        self.assertIs(capabilities.Capabilities.FluidHandler.BLOCK.typeClass(), handlers.IFluidHandler)


if __name__ == '__main__':
    unittest.main()
