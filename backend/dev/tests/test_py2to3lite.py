# -*- coding: utf-8 -*-
"""Regression checks for UTF-8 source signatures in the local adapter."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from py2to3lite import adapt_source, compile_module


class SourceEncodingTests(unittest.TestCase):
    def test_bytes_and_text_with_and_without_signature(self):
        source = u'# -*- coding: utf-8 -*-\nvalue = u"中文\\ufeff内容"\n'
        for raw in (source, u'\ufeff' + source, source.encode('utf-8'),
                    source.encode('utf-8-sig')):
            adapted = adapt_source(raw)
            self.assertEqual(adapted, source)
            namespace = {}
            exec(compile(adapted, '<test>', 'exec'), namespace)
            self.assertEqual(namespace['value'], u'中文\ufeff内容')

    def test_compile_bom_file_with_python_two_exception(self):
        source = (u'# -*- coding: utf-8 -*-\n'
                  u'try:\n    raise ValueError("expected")\n'
                  u'except ValueError, error:\n    value = str(error)\n')
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'sample.py')
            with open(path, 'wb') as stream:
                stream.write(source.encode('utf-8-sig'))
            module = compile_module(path, '_bom_regression', False)
            self.assertEqual(module.value, 'expected')


if __name__ == '__main__':
    unittest.main()