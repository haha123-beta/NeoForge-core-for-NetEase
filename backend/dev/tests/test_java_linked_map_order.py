import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
from java_codegen import NeedsLowering

PREFIX = 'import java.util.Map;import java.util.HashMap;import java.util.LinkedHashMap;import java.util.Iterator;import java.util.ConcurrentModificationException;'
SOURCES = [
    'class A {String run(){Map<String,Integer> m=new LinkedHashMap<>(16,1,true);m.put("a",1);m.put("b",2);m.get("a");return m.toString();}}',
    'class A {String run(){Map<String,Integer> m=new LinkedHashMap<>(16,1,false);m.put("a",1);m.put("b",2);m.get("a");return m.toString();}}',
    'class A {int run(){Map<String,Integer> m=new LinkedHashMap<>(16,1,true);m.put("a",1);m.put("b",2);Iterator<String> i=m.keySet().iterator();m.get("a");try{i.next();}catch(ConcurrentModificationException e){return m.size();}return -1;}}',
    'class A {String run(){Map<String,Integer> m=new LinkedHashMap<>(16,1,true);m.put("a",1);m.put("b",2);m.compute("a",(k,v)->v+3);return m.toString();}}',
    'class A {String run(){Map<String,Integer> m=new LinkedHashMap<>();m.put("a",1);m.put("b",2);Map<String,Integer> copy=new LinkedHashMap<>(m);copy.get("a");return copy.toString();}}',
    'class A {int run(){Map<String,Integer> m=new HashMap<>(16,1);m.put("a",2);return m.get("a");}}',
    'class A {String run(){Map<String,Integer> m=new LinkedHashMap<>(16,1,true);m.put("a",1);m.put("b",2);m.entrySet().iterator().next().setValue(7);return m.toString();}}',
    'class A {String run(){Map<String,Integer> m=new LinkedHashMap<>(16,1,true);m.put("a",null);m.put("b",2);m.computeIfAbsent("a",k->null);return m.toString();}}',
    'class Query {String trace="";public boolean equals(Object value){trace=trace+value;return false;}}class A {String run(){Map<String,String> m=new LinkedHashMap<>(16,1,true);m.put("a","one");m.put("b","two");m.get("a");Query q=new Query();m.containsValue(q);return q.trace;}}',
]


class JavaLinkedMapOrderTests(unittest.TestCase):
    def test_original_java_access_order_matches_jdk(self):
        runner = helper.ArrayTests()
        for body in SOURCES:
            with self.subTest(source=body):
                source = PREFIX + body
                namespace, result = runner.python(source)
                self.assertEqual(str(namespace['A']().run()), runner.java(source, 'System.out.print(new A().run());'))
                self.assertIn('neocore.runtime.JavaCollections@5', result['required_runtime_helpers'])

    def test_abi4_core_is_rejected_before_new_constructor(self):
        unused, result = helper.ArrayTests().python(PREFIX + SOURCES[0])
        util = helper.pkg.load('java_stdlib.util')
        api = helper.pkg.load('core.java_api')
        scope = api.JavaApiImports(sys).install(api.collect_java_api())
        previous = util.JavaCollections.ABI_VERSION
        try:
            util.JavaCollections.ABI_VERSION = 4
            with self.assertRaisesRegex(RuntimeError, 'JavaCollections ABI5'):
                exec(result['python_source'], {})
        finally:
            util.JavaCollections.ABI_VERSION = previous
            scope.close()

    def test_sequenced_methods_and_invalid_constructors_are_diagnosed(self):
        for source in ('class A {void run(LinkedHashMap<String,Integer> m){m.putFirst("a",1);}}',
                       'class A {void run(){new HashMap<String,Integer>(16,1,true);}}'):
            with self.subTest(source=source), self.assertRaises(NeedsLowering):
                helper.ArrayTests().python(PREFIX + source)


if __name__ == '__main__':
    unittest.main()
