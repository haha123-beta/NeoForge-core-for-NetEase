import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
from java_codegen import NeedsLowering

PREFIX = 'import java.util.Set;import java.util.HashSet;import java.util.LinkedHashSet;import java.util.Collection;import java.util.Iterator;import java.util.List;import java.util.ArrayList;import java.util.Map;import java.util.Collections;'
SOURCES = [
    'class A {int run(){Set<String> s=new LinkedHashSet<>();s.add("a");s.add("b");Iterator<String> i=s.iterator();i.next();i.remove();return s.size();}}',
    'class A {int run(){HashSet<String> s=new HashSet<>();s.add("a");s.add("a");return s.size();}}',
    'class A {int run(){Set<String> s=Set.of("a","b");try{s.remove("missing");}catch(UnsupportedOperationException e){return s.size();}return -1;}}',
    'class A {int run(){List<String> input=new ArrayList<>();input.add("a");input.add("a");Set<String> copy=Set.copyOf(input);input.add("b");return copy.size();}}',
    'class A {int run(){Set<String> s=new LinkedHashSet<>();s.add("a");s.add("b");s.removeIf(v -> v.equals("a"));return s.size();}}',
    'class A {int run(){Set<String> s=Collections.emptySet();try{s.add("a");}catch(UnsupportedOperationException e){return s.size();}return -1;}}',
    'class A {int run(){Map<String,Integer> m=Collections.emptyMap();m.clear();try{m.put("a",1);}catch(UnsupportedOperationException e){return m.size();}return -1;}}',
    'class A {int run(){String[] input={"a","b"};Set<String> s=Set.of(input);return s.size();}}',
    'class A {int run(){Set<String> s=new LinkedHashSet<>();s.add("a");String[] values=s.toArray(new String[3]);return values.length;}}',
    'class A {int run(){Set<String> s=new LinkedHashSet<>();s.add("a");s.add("b");Iterator<String> i=s.iterator();i.next();s.add("a");return i.next().length();}}',
    'class A {int run(){Set<String> s=new LinkedHashSet<>();s.add("a");s.add("b");Iterator<String> i=s.iterator();while(i.hasNext()){if(i.next().equals("a")){i.remove();}}return s.size();}}',
]


class JavaSetContractTests(unittest.TestCase):
    def test_collection_declared_list_keeps_existing_abi1_calls(self):
        source = PREFIX + 'class A {int run(){Collection<String> c=new ArrayList<>();c.add("a");return c.size();}}'
        runner = helper.ArrayTests()
        namespace, unused = runner.python(source)
        self.assertEqual(str(namespace['A']().run()), runner.java(source, 'System.out.print(new A().run());'))

    def test_original_java_matches_jdk_and_requires_abi3(self):
        runner = helper.ArrayTests()
        for body in SOURCES:
            with self.subTest(source=body):
                source = PREFIX + body
                namespace, result = runner.python(source)
                self.assertEqual(str(namespace['A']().run()), runner.java(source, 'System.out.print(new A().run());'))
                self.assertIn('neocore.runtime.JavaCollections@3', result['required_runtime_helpers'])

    def test_abi2_core_rejects_new_set_contracts(self):
        unused, result = helper.ArrayTests().python(PREFIX + SOURCES[0])
        util = helper.pkg.load('java_stdlib.util')
        api = helper.pkg.load('core.java_api')
        scope = api.JavaApiImports(sys).install(api.collect_java_api())
        old = util.JavaCollections.ABI_VERSION
        try:
            util.JavaCollections.ABI_VERSION = 2
            with self.assertRaisesRegex(RuntimeError, 'JavaCollections ABI3'):
                exec(result['python_source'], {})
        finally:
            util.JavaCollections.ABI_VERSION = old
            scope.close()

    def test_unreviewed_sequenced_methods_are_diagnosed(self):
        with self.assertRaises(NeedsLowering):
            helper.ArrayTests().python(PREFIX + 'class A {void run(LinkedHashSet<String> s){s.addFirst("a");}}')


if __name__ == '__main__':
    unittest.main()
