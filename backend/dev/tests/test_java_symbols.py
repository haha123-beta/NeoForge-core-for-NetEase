import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from java_frontend import parse_source
from java_symbols import declarations


class SymbolTests(unittest.TestCase):
    def test_names_fields_overloads_and_nested_owner_are_preserved(self):
        source = """package original.mod;
class Outer {
  static int count = 1;
  String label;
  Outer(int value) {}
  void is(int in) {}
  void is(String in) {}
  static class Inner { boolean flag; }
}
"""
        ir = declarations(parse_source(source))
        outer, inner = ir['classes']
        self.assertEqual(outer['java_name'], 'original.mod.Outer')
        self.assertEqual(inner['java_name'], 'original.mod.Outer.Inner')
        self.assertEqual(inner['owner'], outer['java_name'])
        self.assertEqual(outer['overloaded_names'], ['is'])
        self.assertEqual([f['name'] for f in outer['fields']], ['count', 'label'])
        self.assertTrue(outer['fields'][0]['static'])
        method = outer['methods'][1]
        self.assertEqual(method['name'], 'is')
        self.assertEqual(method['parameters'], [{'name': 'in', 'declared_type': 'int', 'varargs': False}])
        self.assertFalse(ir['python_generated'])
        self.assertEqual(ir['semantic_resolution'], 'PENDING')

    def test_varargs_and_interface_constants_keep_declarations(self):
        ir = declarations(parse_source('interface I { int LIMIT=2; void f(String... args); }'))
        interface = ir['classes'][0]
        self.assertEqual(interface['fields'][0]['name'], 'LIMIT')
        self.assertTrue(interface['fields'][0]['static'])
        self.assertTrue(interface['fields'][0]['final'])
        self.assertEqual(interface['methods'][0]['parameters'],
            [{'name': 'args', 'declared_type': 'String[]', 'varargs': True}])

    def test_syntax_errors_do_not_become_valid_symbols(self):
        with self.assertRaises(ValueError):
            declarations(parse_source('class Broken { void run( {'))


if __name__ == '__main__':
    unittest.main()
