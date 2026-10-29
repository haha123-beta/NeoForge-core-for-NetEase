import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
pkg = Package()
lang = pkg.load('java_stdlib.lang')
String = lang.JAVA_MAP['java.lang.String']


class StringBridgeTests(unittest.TestCase):
    def test_public_type_constructor_static_and_instance_methods(self):
        text = String('Hello')
        self.assertIsInstance(text, String)
        self.assertEqual(text.length(), 5)
        self.assertEqual(text.substring(1, 4), 'ell')
        self.assertEqual(String().length(), 0)
        self.assertIsInstance(String.valueOf(42), String)
        self.assertTrue(String.valueOf(None).equals('null'))
        self.assertEqual(String.join(',', ['a', 'b']), 'a,b')
        self.assertEqual(String.format('%s %d', 'x', 2), 'x 2')
        with self.assertRaises(lang.NullPointerException):
            String(None)
        with self.assertRaises(NotImplementedError):
            String(bytearray([65]))

    def test_utf16_indexing_and_surrogate_bounds(self):
        text = String('A\U0001f600B')
        self.assertEqual(text.length(), 4)
        self.assertEqual(ord(text.charAt(1)), 0xD83D)
        self.assertEqual(ord(text.charAt(2)), 0xDE00)
        self.assertEqual(text.substring(1, 3), '\U0001f600')
        self.assertEqual(len(text.toCharArray()), 4)
        self.assertEqual(String('中文').length(), 2)
        self.assertFalse(String('null').equals(None))
        self.assertTrue(String('\U0001f600').equals('\ud83d\ude00'))
        self.assertEqual(String('\U0001f600').hashCode(), 1772899)
        with self.assertRaises(lang.StringIndexOutOfBoundsException):
            text.charAt(4)


if __name__ == '__main__':
    unittest.main()
