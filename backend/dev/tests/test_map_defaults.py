import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
u = helper.pkg.load('java_stdlib.util')
fn = helper.pkg.load('java_stdlib.function')


class MapDefaultsTests(unittest.TestCase):
    def oracle(self, body):
        return helper.ArrayTests().java('import java.util.*;', 'Map<String,Integer> m=new LinkedHashMap<>();' + body)

    def test_replace_overloads_distinguish_absent_and_null(self):
        m = u.JavaMap()
        m.put('a', None)
        self.assertIsNone(m.replace('missing', 1))
        self.assertFalse(m.containsKey('missing'))
        self.assertTrue(m.replace('a', None, 2))
        self.assertFalse(m.replace('a', 1, 9))
        self.assertEqual(m.replace('a', 3), 2)
        self.assertEqual(str(m), self.oracle('m.put("a",null);m.replace("missing",1);m.replace("a",null,2);m.replace("a",1,9);m.replace("a",3);System.out.print(m);'))

    def test_replace_does_not_invalidate_entry_or_cursor(self):
        m = u.JavaMap({'a': 1})
        it = m.entrySet().iterator()
        m.replace('a', 2)
        entry = it.next()
        self.assertEqual(entry.getValue(), 2)
        m.replace('a', 3)
        self.assertEqual(entry.getValue(), 3)

    def test_computeifpresent_skips_absent_and_null(self):
        m = u.JavaMap({'a': None, 'b': 2})
        calls = []
        remap = lambda k, v: calls.append(k) or v + 1
        self.assertIsNone(m.computeIfPresent('missing', remap))
        self.assertIsNone(m.computeIfPresent('a', remap))
        self.assertEqual(m.computeIfPresent('b', remap), 3)
        self.assertEqual(calls, ['b'])
        self.assertIsNone(m.computeIfPresent('b', lambda k, v: None))
        self.assertFalse(m.containsKey('b'))

    def test_compute_inserts_replaces_and_removes_null_mapping(self):
        m = u.JavaMap()
        self.assertEqual(m.compute('a', lambda k, v: 2), 2)
        self.assertEqual(m.compute('a', lambda k, v: v + 3), 5)
        self.assertIsNone(m.compute('a', lambda k, v: None))
        m.put('b', None)
        m.compute('b', lambda k, v: None)
        self.assertFalse(m.containsKey('a'))
        self.assertFalse(m.containsKey('b'))

    def test_merge_skips_callback_for_absent_and_null(self):
        m = u.JavaMap({'a': None})
        calls = []
        remap = lambda old, new: calls.append((old, new)) or old + new
        self.assertEqual(m.merge('a', 2, remap), 2)
        self.assertEqual(m.merge('missing', 3, remap), 3)
        self.assertEqual(calls, [])
        self.assertEqual(m.merge('a', 4, remap), 6)
        self.assertEqual(calls, [(2, 4)])
        self.assertIsNone(m.merge('a', 7, lambda a, b: None))
        self.assertFalse(m.containsKey('a'))

    def test_null_callbacks_and_merge_value_are_checked_before_lookup(self):
        class Key(object):
            def hashCode(self):
                raise AssertionError('key must not be hashed')
        m = u.JavaMap()
        for name, args in (('computeIfPresent', (Key(), None)), ('compute', (Key(), None)),
                           ('merge', (Key(), None, lambda a, b: a)), ('merge', (Key(), 1, None)),
                           ('replaceAll', (None,)), ('forEach', (None,))):
            with self.subTest(name=name), self.assertRaises(u.NullPointerException):
                getattr(m, name)(*args)

    def test_compute_callbacks_detect_structure_and_keep_effects(self):
        for method in ('computeIfPresent', 'compute', 'merge'):
            m = u.JavaMap({'a': 1})
            def callback(first, second):
                m.put('b', 9)
                return 7
            args = ('a', 2, callback) if method == 'merge' else ('a', callback)
            with self.subTest(method=method), self.assertRaises(u.ConcurrentModificationException):
                getattr(m, method)(*args)
            self.assertEqual(m.get('a'), 1)
            self.assertEqual(m.get('b'), 9)
        self.assertEqual(self.oracle('m.put("a",1);try{m.compute("a",(k,v)->{m.put("b",9);return 7;});}catch(ConcurrentModificationException e){}System.out.print(m);'), '{a=1, b=9}')

    def test_nonstructural_callback_write_is_allowed_and_result_wins(self):
        m = u.JavaMap({'a': 1})
        def callback(k, v):
            m.put('a', 9)
            return v + 2
        self.assertEqual(m.compute('a', callback), 3)
        self.assertEqual(m.get('a'), 3)
        self.assertEqual(self.oracle('m.put("a",1);m.compute("a",(k,v)->{m.put("a",9);return v+2;});System.out.print(m.get("a"));'), '3')

    def test_callback_exception_wins_and_side_effects_remain(self):
        m = u.JavaMap({'a': 1})
        def callback(k, v):
            m.put('b', 2)
            raise u.IllegalStateException('callback')
        with self.assertRaises(u.IllegalStateException):
            m.compute('a', callback)
        self.assertEqual(m.get('b'), 2)
        self.assertEqual(m.get('a'), 1)

    def test_replaceall_is_nonstructural_and_allows_null_values(self):
        m = u.JavaMap({'a': 1, 'b': 2})
        it = m.values().iterator()
        m.replaceAll(lambda k, v: None if k == 'a' else v + 3)
        self.assertIsNone(it.next())
        self.assertEqual(it.next(), 5)
        self.assertEqual(str(m), self.oracle('m.put("a",1);m.put("b",2);m.replaceAll((k,v)->k.equals("a")?null:v+3);System.out.print(m);'))

    def test_replaceall_appended_nodes_are_seen_before_final_failure(self):
        m = u.JavaMap({'a': 1})
        seen = []
        def callback(k, v):
            seen.append(k)
            if k == 'a':
                m.put('b', 2)
            return v + 10
        with self.assertRaises(u.ConcurrentModificationException):
            m.replaceAll(callback)
        actual = ','.join(seen) + ':' + str(m)
        self.assertEqual(actual, self.oracle('m.put("a",1);StringBuilder trace=new StringBuilder();try{m.replaceAll((k,v)->{trace.append(k).append(",");if(k.equals("a"))m.put("b",2);return v+10;});}catch(ConcurrentModificationException e){}System.out.print(trace.substring(0,trace.length()-1)+":"+m);'))

    def test_replaceall_exception_preserves_prior_replacements(self):
        m = u.JavaMap({'a': 1, 'b': 2, 'c': 3})
        def callback(k, v):
            if k == 'b':
                raise u.IllegalStateException('stop')
            return v + 10
        with self.assertRaises(u.IllegalStateException):
            m.replaceAll(callback)
        self.assertEqual(m.items(), [('a', 11), ('b', 2), ('c', 3)])

    def test_readonly_rejects_defaults_without_running_callbacks(self):
        m = u.JavaMap({'a': 1})
        readonly = u.Collections.unmodifiableMap(m)
        calls = []
        callback = lambda *args: calls.append(args) or 3
        for name, args in (('replace', ('a', 2)), ('replace', ('a', 1, 2)),
                           ('compute', ('a', callback)), ('computeIfPresent', ('a', callback)),
                           ('merge', ('a', 2, callback)), ('replaceAll', (callback,))):
            with self.subTest(name=name), self.assertRaises(u.UnsupportedOperationException):
                getattr(readonly, name)(*args)
        self.assertEqual(calls, [])
        self.assertEqual(m.get('a'), 1)

    def test_bifunction_andthen_and_biconsumer_short_circuit(self):
        composed = fn.BiFunction(lambda a, b: a + b).andThen(fn.Function(lambda v: v * 2))
        self.assertEqual(composed.apply(2, 3), 10)
        seen = []
        first = fn.BiConsumer(lambda a, b: seen.append(('first', a, b)))
        first.andThen(fn.BiConsumer(lambda a, b: seen.append(('second', a, b)))).accept(2, 3)
        self.assertEqual(seen, [('first', 2, 3), ('second', 2, 3)])
        seen[:] = []
        def fail(a, b):
            seen.append('first')
            raise u.IllegalStateException('stop')
        with self.assertRaises(u.IllegalStateException):
            fn.BiConsumer(fail).andThen(first).accept(2, 3)
        self.assertEqual(seen, ['first'])
        for callback in (fn.BiFunction(lambda a, b: a), first):
            with self.assertRaises(u.NullPointerException):
                callback.andThen(None)


if __name__ == '__main__':
    unittest.main()
