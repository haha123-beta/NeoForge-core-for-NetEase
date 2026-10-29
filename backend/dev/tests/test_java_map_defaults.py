import os
import sys
import unittest
import random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
from java_codegen import NeedsLowering

PREFIX = 'import java.util.Map;import java.util.LinkedHashMap;import java.util.Collections;import java.util.ConcurrentModificationException;import java.util.function.BiFunction;import java.util.function.BiConsumer;'
SOURCES = [
    'class A {int run(){Map<String,Integer> m=new LinkedHashMap<>();m.put("a",1);int first=m.replace("a",2);boolean second=m.replace("a",2,4);return second?first+m.get("a"):0;}}',
    'class A {int run(){Map<String,Integer> m=new LinkedHashMap<>();m.put("a",2);int value=m.computeIfPresent("a",(k,v)->v+3);return value+m.get("a");}}',
    'class A {int run(){Map<String,Integer> m=new LinkedHashMap<>();m.compute("a",(k,v)->7);m.compute("a",(k,v)->null);return m.size();}}',
    'class A {int run(){Map<String,Integer> m=new LinkedHashMap<>();m.merge("a",2,(old,next)->old+next);m.merge("a",3,(old,next)->old+next);return m.get("a");}}',
    'class A {int run(){Map<String,Integer> m=new LinkedHashMap<>();m.put("a",2);m.put("b",3);m.replaceAll((k,v)->v*2);return m.get("a")+m.get("b");}}',
    'class A {int total;int run(){Map<String,Integer> m=new LinkedHashMap<>();m.put("a",2);m.put("b",3);m.forEach((k,v)->{total+=v;});return total;}}',
    'class A {int combine(Integer old,Integer next){return old+next;}int run(){Map<String,Integer> m=new LinkedHashMap<>();m.put("a",2);m.merge("a",3,this::combine);return m.get("a");}}',
    'class A {int calls;int remap(String key,Integer value){calls++;return value+1;}int run(){Map<String,Integer> m=new LinkedHashMap<>();m.put("a",2);m.compute("a",this::remap);return calls+m.get("a");}}',
    'class A {int run(){Map<String,Integer> m=new LinkedHashMap<>();m.put("a",1);try{m.compute("a",(k,v)->{m.put("b",9);return 7;});}catch(ConcurrentModificationException e){return m.get("a")+m.get("b");}return -1;}}',
    'class A {int run(){Map<String,Integer> source=new LinkedHashMap<>();source.put("a",1);Map<String,Integer> m=Collections.unmodifiableMap(source);try{m.merge("a",2,(a,b)->a+b);}catch(UnsupportedOperationException e){return m.get("a");}return -1;}}',
    'class A {int total;void consume(String k,Integer v){total+=v;}int run(){Map<String,Integer> m=new LinkedHashMap<>();m.put("a",2);m.forEach(this::consume);return total;}}',
    'class A {int run(){BiFunction<Integer,Integer,Integer> f=(a,b)->a+b;return f.apply(2,3);}}',
    'class A {int base=2;int add(int value){return base+value;}int run(){BiFunction<A,Integer,Integer> f=A::add;return f.apply(this,3);}}',
    'class Box {int total;Box(int a,int b){total=a+b;}}class A {int run(){BiFunction<Integer,Integer,Box> f=Box::new;return f.apply(2,3).total;}}',
]

# One deterministic mixed trace compares retained null mappings, deletions,
# replacements and remapping order in the original JVM and both Python runtimes.
_rng = random.Random(43021)
_steps = []
for _index in range(72):
    _key = '"' + _rng.choice(['a', 'b', 'c', 'd']) + '"'
    _value = str(_rng.randint(1, 5))
    _operations = [
        'm.put(' + _key + ',null);',
        'm.put(' + _key + ',' + _value + ');',
        'm.putIfAbsent(' + _key + ',' + _value + ');',
        'm.replace(' + _key + ',' + _value + ');',
        'm.replace(' + _key + ',1,' + _value + ');',
        'm.compute(' + _key + ',(k,v)->' + _value + ');',
        'm.compute(' + _key + ',(k,v)->null);',
        'm.computeIfPresent(' + _key + ',(k,v)->v+1);',
        'm.computeIfPresent(' + _key + ',(k,v)->null);',
        'm.merge(' + _key + ',' + _value + ',(a,b)->a+b);',
        'm.merge(' + _key + ',' + _value + ',(a,b)->null);',
        'm.remove(' + _key + ');',
    ]
    _steps.append(_rng.choice(_operations) + 'trace=trace+m.toString()+"|";')
SOURCES.append('class A {String run(){Map<String,Integer> m=new LinkedHashMap<>();String trace="";' + ''.join(_steps) + 'return trace;}}')


class JavaMapDefaultsTests(unittest.TestCase):
    def test_functional_abi4_rejects_two_argument_callbacks(self):
        unused, result = helper.ArrayTests().python(PREFIX + SOURCES[1])
        functional = helper.pkg.load('java_stdlib.function').Functional
        api = helper.pkg.load('core.java_api')
        scope = api.JavaApiImports(sys).install(api.collect_java_api())
        old = functional.ABI_VERSION
        try:
            functional.ABI_VERSION = 4
            with self.assertRaisesRegex(RuntimeError, 'Functional ABI 9'):
                exec(result['python_source'], {})
        finally:
            functional.ABI_VERSION = old
            scope.close()

    def test_original_java_matches_jdk(self):
        runner = helper.ArrayTests()
        for body in SOURCES:
            with self.subTest(source=body):
                source = PREFIX + body
                namespace, result = runner.python(source)
                self.assertEqual(str(namespace['A']().run()), runner.java(source, 'System.out.print(new A().run());'))
                if '(k,v)' in body or '(old,next)' in body or '(a,b)' in body or '::' in body:
                    self.assertIn('neocore.runtime.Functional@5', result['required_runtime_helpers'])
                if 'Map<' in body:
                    self.assertIn('neocore.runtime.JavaCollections@4', result['required_runtime_helpers'])

    def test_abi3_core_rejects_map_default_code(self):
        unused, result = helper.ArrayTests().python(PREFIX + SOURCES[1])
        util = helper.pkg.load('java_stdlib.util')
        api = helper.pkg.load('core.java_api')
        scope = api.JavaApiImports(sys).install(api.collect_java_api())
        old = util.JavaCollections.ABI_VERSION
        try:
            util.JavaCollections.ABI_VERSION = 3
            required = max(int(name.rsplit('@', 1)[1]) for name in result['required_runtime_helpers']
                           if name.startswith('neocore.runtime.JavaCollections@'))
            with self.assertRaisesRegex(RuntimeError, 'JavaCollections ABI' + str(required)):
                exec(result['python_source'], {})
        finally:
            util.JavaCollections.ABI_VERSION = old
            scope.close()

    def test_unsupported_binaryoperator_stays_diagnosed(self):
        with self.assertRaises(NeedsLowering):
            helper.ArrayTests().python('import java.util.function.BinaryOperator;class A {BinaryOperator<Integer> op=(a,b)->a+b;}')


if __name__ == '__main__':
    unittest.main()
