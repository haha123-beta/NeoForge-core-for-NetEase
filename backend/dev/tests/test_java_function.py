import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
pkg = Package()
functions = pkg.load('java_stdlib.function')
attachments = pkg.load('neoforge.attachment')
entities = pkg.load('minecraft.entity')


class FunctionTests(unittest.TestCase):
    def test_composition_order_identity_and_exception(self):
        twice = functions.Function(lambda x: x * 2)
        plus = functions.Function(lambda x: x + 3)
        self.assertEqual(twice.compose(plus).apply(4), 14)
        self.assertEqual(twice.andThen(plus).apply(4), 11)
        value = object()
        self.assertIs(functions.Function.identity().apply(value), value)
        with self.assertRaises(functions.NullPointerException):
            twice.andThen(None)
        calls = []
        def fail(value):
            raise ValueError('original error')
        with self.assertRaisesRegex(ValueError, 'original error'):
            functions.Function(fail).andThen(lambda v: calls.append(v)).apply(1)
        self.assertEqual(calls, [])

    def test_supplier_and_holder_function_with_attachments(self):
        supplier = functions.Supplier(lambda: [])
        kind = attachments.AttachmentType.builder(supplier).build()
        first, second = entities.Entity(), entities.Entity()
        first.getData(kind).append(1)
        self.assertEqual(second.getData(kind), [])
        holder_kind = attachments.AttachmentType.builder(
            functions.Function(lambda holder: {'owner': holder})).build()
        self.assertIs(first.getData(holder_kind)['owner'], first)
        class Custom(functions.Supplier):
            def get(self):
                return 42
        self.assertEqual(functions.Supplier(Custom()).get(), 42)


if __name__ == '__main__':
    unittest.main()
