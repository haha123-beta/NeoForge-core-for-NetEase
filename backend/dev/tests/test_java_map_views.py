import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
from java_codegen import NeedsLowering

PREFIX = 'import java.util.Map;import java.util.LinkedHashMap;import java.util.Collection;import java.util.Set;import java.util.Iterator;import java.util.Collections;'

SOURCES = [
    'class A {int run(){Map<String,Integer> m=new LinkedHashMap<>();m.put("a",2);Collection<Integer> live=m.values();m.put("b",3);int total=0;for(Integer value:live){total+=value;}return total+live.size();}}',
    'class A {int run(){Map<String,Integer> m=new LinkedHashMap<>();m.put("a",2);Iterator<Map.Entry<String,Integer>> it=m.entrySet().iterator();Map.Entry<String,Integer> entry=it.next();int old=entry.setValue(7);return old+m.get("a");}}',
    'class A {int run(){Map<String,Integer> m=new LinkedHashMap<>();m.put("a",2);m.put("b",3);m.keySet().remove("a");m.values().remove(3);return m.size();}}',
    'class A {int run(){Map<String,Integer> m=new LinkedHashMap<>();m.put("a",2);Map<String,Integer> view=Collections.unmodifiableMap(m);m.put("b",3);try{view.put("c",9);}catch(UnsupportedOperationException e){return view.size()+view.get("a");}return -1;}}',
    'class A {int run(){Map<String,Integer> m=new LinkedHashMap<>();m.put("a",2);Map<String,Integer> view=Collections.unmodifiableMap(m);try{view.entrySet().iterator().next().setValue(99);}catch(UnsupportedOperationException e){return m.get("a");}return -1;}}',
    'class A {int run(){Map<String,Integer> m=new LinkedHashMap<>();m.put("a",2);m.put("b",3);Iterator<Integer> it=m.values().iterator();int first=it.next();m.put("b",7);int second=it.next();it.remove();return first+second+m.size();}}',
    'class A {int run(){Map<String,Integer> m=new LinkedHashMap<>();int first=m.computeIfAbsent("a",key -> 4);int second=m.computeIfAbsent("a",key -> 9);return first+second;}}',
    'class A {int run(){Map<String,Integer> m=new LinkedHashMap<>();m.put("a",2);m.put("b",7);m.values().removeIf(value -> value.intValue()>3);return m.size()+m.get("a");}}',
    'class A {int run(){Map<String,Integer> m=Map.of("a",2,"b",3);try{m.clear();}catch(UnsupportedOperationException e){return m.get("a")+m.size();}return -1;}}',
    'class A {int run(){Map<String,Integer> m=new LinkedHashMap<>();m.put("a",2);Map<String,Integer> copy=Map.copyOf(m);m.put("a",9);return copy.get("a");}}',
    'class A {int run(){Map<String,Integer> m=new LinkedHashMap<>();m.put("a",2);Set<String> keys=Collections.unmodifiableSet(m.keySet());m.put("b",7);try{keys.clear();}catch(UnsupportedOperationException e){return keys.size();}return -1;}}',
]


class JavaMapViewsTests(unittest.TestCase):
    def test_original_java_map_chains_match_jdk(self):
        runner = helper.ArrayTests()
        for source in SOURCES:
            with self.subTest(source=source):
                source = PREFIX + source
                namespace, result = runner.python(source)
                self.assertEqual(str(namespace['A']().run()), runner.java(source, 'System.out.print(new A().run());'))
                self.assertIn('neocore.runtime.JavaCollections@2', result['required_runtime_helpers'])

    def test_unreviewed_map_methods_are_not_guessed(self):
        for body in ('Map.ofEntries();', 'm.entrySet().spliterator();'):
            source = PREFIX + 'class A {void run(Map<String,Integer> m){' + body + '}}'
            with self.subTest(body=body), self.assertRaises(NeedsLowering):
                helper.ArrayTests().python(source)

    def test_map_receiver_and_arguments_keep_java_order(self):
        source = PREFIX + 'class A {int calls;String key(){calls++;return "x";}int run(){Map<String,Integer> m=null;try{m.put(key(),3);}catch(NullPointerException e){return calls;}return -1;}}'
        namespace, unused = helper.ArrayTests().python(source)
        self.assertEqual(str(namespace['A']().run()), helper.ArrayTests().java(source, 'System.out.print(new A().run());'))

    def test_abi1_core_cannot_run_new_map_code(self):
        source = PREFIX + SOURCES[1]
        namespace, result = helper.ArrayTests().python(source)
        util = helper.pkg.load('java_stdlib.util')
        api = helper.pkg.load('core.java_api')
        scope = api.JavaApiImports(sys).install(api.collect_java_api())
        old = util.JavaCollections.ABI_VERSION
        try:
            util.JavaCollections.ABI_VERSION = 1
            required = max(int(name.rsplit('@', 1)[1]) for name in result['required_runtime_helpers']
                           if name.startswith('neocore.runtime.JavaCollections@'))
            with self.assertRaisesRegex(RuntimeError, 'JavaCollections ABI' + str(required)):
                exec(result['python_source'], {})
        finally:
            util.JavaCollections.ABI_VERSION = old
            scope.close()


if __name__ == '__main__':
    unittest.main()
