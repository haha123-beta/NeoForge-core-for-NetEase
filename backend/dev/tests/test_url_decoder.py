import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
net = Package().load('java_stdlib.net')


class DecoderTests(unittest.TestCase):
    def test_charset_names_and_errors(self):
        self.assertIs(net.Charset.forName('uTf8'), net.StandardCharsets.UTF_8)
        self.assertEqual(net.Charset.forName('latin-1').name(), 'ISO-8859-1')
        self.assertTrue(net.Charset.isSupported('UTF-16BE'))
        self.assertFalse(net.Charset.isSupported('unknown-codec'))
        for name in ('', '-utf8', 'utf 8'):
            with self.assertRaises(net.IllegalCharsetNameException):
                net.Charset.forName(name)
        with self.assertRaises(net.IllegalArgumentException):
            net.Charset.forName(None)
        with self.assertRaises(net.UnsupportedCharsetException):
            net.Charset.forName('unknown-codec')

    def test_utf16_byte_order(self):
        for text in ('%00%41', '%FE%FF%00%41', '%FF%FE%41%00'):
            self.assertEqual(net.URLDecoder.decode(text, net.StandardCharsets.UTF_16), 'A')
        self.assertEqual(net.URLDecoder.decode('%FF%FE%41%00', net.StandardCharsets.UTF_16LE), '\ufeffA')

    def test_sample_explicit_charset_unicode_and_plus(self):
        self.assertEqual(net.URLDecoder.decode('E%3A%2F%E6%A8%A1%E7%BB%84+folder%2B',
            net.StandardCharsets.UTF_8), 'E:/模组 folder+')
        self.assertEqual(net.URLDecoder.decode('already decoded', 'UTF-8'), 'already decoded')
        self.assertEqual(net.URLDecoder.decode('%E9', 'latin-1'), 'é')

    def test_invalid_escapes_and_explicit_default_limit(self):
        for text in ('%', '%2', '%GG', '%+1'):
            with self.assertRaises(net.IllegalArgumentException):
                net.URLDecoder.decode(text, 'utf-8')
        with self.assertRaises(NotImplementedError):
            net.URLDecoder.decode('x')
        with self.assertRaises(net.UnsupportedEncodingException):
            net.URLDecoder.decode('%41', 'unknown-codec')
        with self.assertRaises(net.NullPointerException):
            net.URLDecoder.decode(None, 'utf-8')


if __name__ == '__main__':
    unittest.main()
