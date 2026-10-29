import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from py3only_lint import check_source
package = Package()
hooks = package.load('core.python_hooks')
names = package.load('core.java_names')


class CompatibilityTests(unittest.TestCase):
    def test_python27_exception_syntax_is_not_rejected(self):
        self.assertEqual(check_source("try:\n    work()\nexcept Exception as error:\n    print(error)\n"), [])
        self.assertTrue(check_source("async def work():\n    pass\n"))

    def test_original_names_and_subclass_dispatch(self):
        class Base(object):
            def isItem(self, value):
                return value + 1
        names.install_java_aliases({'net.minecraft.world.item.ItemStack': Base})
        class Child(Base):
            def isItem(self, value):
                return value + 3
        self.assertEqual(getattr(Child(), 'is')(7), 10)
        class Static(object):
            @staticmethod
            def orShapes(a, b):
                return a + b
        names.install_java_aliases({'net.minecraft.world.phys.shapes.Shapes': Static})
        self.assertEqual(getattr(Static, 'or')(2, 4), 6)
        class ClassMethod(object):
            @classmethod
            def passResult(cls):
                return cls
        names.install_java_aliases({'net.neoforged.neoforge.common.util.EventResult': ClassMethod})
        self.assertIs(getattr(ClassMethod, 'pass')(), ClassMethod)

    def test_order_return_replacement_and_unload(self):
        registry = hooks.PythonHookRegistry()
        seen = []
        @registry.target('sample:add')
        def add(a, b):
            seen.append('body')
            return a + b
        registry.inject('sample:add', lambda ci, a, k: seen.append('low'), priority=1)
        remove = registry.inject('sample:add', lambda ci, a, k: seen.append('high'), priority=2)
        registry.inject('sample:add', lambda ci, a, k: ci.setReturnValue(ci.getReturnValue() * 2), at='RETURN', cancellable=True)
        self.assertEqual(add(2, 3), 10)
        self.assertEqual(seen, ['high', 'low', 'body'])
        remove()
        remove()
        registry.clear()
        self.assertEqual(add(2, 3), 5)

    def test_cancel_and_unsupported_points(self):
        registry = hooks.PythonHookRegistry()
        @registry.target('sample:fail')
        def fail():
            raise AssertionError('body must not execute')
        registry.inject('sample:fail', lambda ci, a, k: ci.setReturnValue(17), cancellable=True)
        self.assertEqual(fail(), 17)
        with self.assertRaises(ValueError):
            registry.inject('sample:fail', lambda *a: None, at='INVOKE')
        with self.assertRaises(ValueError):
            hooks.CallbackInfo('x').cancel()


if __name__ == '__main__':
    unittest.main()
