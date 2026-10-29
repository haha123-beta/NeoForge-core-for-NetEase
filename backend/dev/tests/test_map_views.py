import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
u = helper.pkg.load('java_stdlib.util')


class MapViewsTests(unittest.TestCase):
    def java(self, body):
        return helper.ArrayTests().java('', 'java.util.Map<String,Integer> m=new java.util.LinkedHashMap<>();' + body)

    def mapping(self):
        m = u.JavaMap()
        m.put('a', 1)
        m.put('b', 2)
        return m

    def test_three_views_are_live_and_mutations_write_through(self):
        m = self.mapping()
        keys, values, entries = m.keySet(), m.values(), m.entrySet()
        m.put('c', 2)
        self.assertEqual((keys.size(), values.size(), entries.size()), (3, 3, 3))
        values.remove(2)
        keys.remove('a')
        actual = m.toString()
        expected = self.java('m.put("a",1);m.put("b",2);java.util.Set<String> k=m.keySet();java.util.Collection<Integer> v=m.values();m.put("c",2);v.remove(2);k.remove("a");System.out.print(m);')
        self.assertEqual(actual, expected)
        entries.clear()
        self.assertTrue(m.isEmpty())

    def test_entry_is_live_across_nonstructural_replacement(self):
        m = self.mapping()
        entry = m.entrySet().iterator().next()
        m.put('a', 5)
        self.assertEqual(entry.getValue(), 5)
        old = entry.setValue(8)
        self.assertEqual(str(old) + ':' + str(m.get('a')), self.java('m.put("a",1);java.util.Map.Entry<String,Integer> e=m.entrySet().iterator().next();m.put("a",5);System.out.print(e.setValue(8)+":"+m.get("a"));'))

    def test_iterator_replacement_removal_and_exception_order(self):
        m = self.mapping()
        it = m.values().iterator()
        self.assertEqual(it.next(), 1)
        m.put('b', 9)
        self.assertEqual(it.next(), 9)
        it.remove()
        with self.assertRaises(u.IllegalStateException):
            it.remove()
        with self.assertRaises(u.NoSuchElementException):
            it.next()
        self.assertEqual(m.toString(), self.java('m.put("a",1);m.put("b",2);java.util.Iterator<Integer> i=m.values().iterator();i.next();m.put("b",9);i.next();i.remove();System.out.print(m);'))

    def test_structural_changes_detected_but_has_next_is_not_a_check(self):
        m = self.mapping()
        it = m.keySet().iterator()
        m.put('c', 3)
        self.assertTrue(it.hasNext())
        with self.assertRaises(u.IllegalStateException):
            it.remove()
        with self.assertRaises(u.ConcurrentModificationException):
            it.next()
        self.assertEqual(self.java('m.put("a",1);java.util.Iterator<String> i=m.keySet().iterator();m.clear();try{i.remove();}catch(IllegalStateException e){System.out.print("state:");}try{i.next();}catch(java.util.ConcurrentModificationException e){System.out.print("changed");}'), 'state:changed')

    def test_views_do_not_support_add_and_empty_add_all_is_a_noop(self):
        m = self.mapping()
        for view in (m.keySet(), m.values(), m.entrySet()):
            with self.assertRaises(u.UnsupportedOperationException):
                view.add(None)
            self.assertFalse(view.addAll([]))
            with self.assertRaises(u.JavaNullPointerException):
                view.addAll(None)
        self.assertEqual(self.java('System.out.print(m.keySet().addAll(java.util.List.of())+":"+m.values().addAll(java.util.List.of()));'), 'false:false')

    def test_entry_removal_requires_matching_key_and_value(self):
        m = self.mapping()
        self.assertFalse(m.entrySet().remove(u.MapEntry('a', 99)))
        self.assertTrue(m.entrySet().remove(u.MapEntry('a', 1)))
        self.assertEqual(m.toString(), self.java('m.put("a",1);m.put("b",2);m.entrySet().remove(new java.util.AbstractMap.SimpleEntry<>("a",99));m.entrySet().remove(new java.util.AbstractMap.SimpleEntry<>("a",1));System.out.print(m);'))

    def test_bulk_view_removal_and_retain_preserve_map(self):
        m = self.mapping()
        m.put('c', 2)
        self.assertTrue(m.values().removeAll(u.JavaList([2])))
        self.assertFalse(m.keySet().retainAll(u.JavaList(['a'])))
        self.assertEqual(m.toString(), self.java('m.put("a",1);m.put("b",2);m.put("c",2);m.values().removeAll(java.util.List.of(2));m.keySet().retainAll(java.util.List.of("a"));System.out.print(m);'))

    def test_unmodifiable_map_is_live_and_rejects_all_exposed_mutators(self):
        m = self.mapping()
        view = u.Collections.unmodifiableMap(m)
        m.put('c', 3)
        self.assertEqual(view.get('c'), 3)
        called = []
        operations = [lambda: view.put('x', 3), lambda: view.remove('missing'),
            lambda: view.clear(), lambda: view.putAll(u.JavaMap()),
            lambda: view.putIfAbsent('a', 7), lambda: view.computeIfAbsent('a', lambda k: called.append(k)),
            lambda: view.replace('a', 8), lambda: view.merge('a', 3, None)]
        for operation in operations:
            with self.assertRaises(u.UnsupportedOperationException):
                operation()
        self.assertEqual(called, [])
        self.assertEqual(self.java('m.put("a",1);java.util.Map<String,Integer> v=java.util.Collections.unmodifiableMap(m);try{v.computeIfAbsent("a",k->{throw new AssertionError();});}catch(UnsupportedOperationException e){System.out.print("blocked");}'), 'blocked')

    def test_unmodifiable_entries_are_wrapped_for_iterator_array_and_callbacks(self):
        m = self.mapping()
        entries = u.Collections.unmodifiableMap(m).entrySet()
        observed = []
        entries.iterator().forEachRemaining(lambda entry: observed.append(entry))
        for entry in list(entries) + list(entries.toArray()) + observed:
            with self.assertRaises(u.UnsupportedOperationException):
                entry.setValue(9)
        m.put('a', 4)
        self.assertEqual(observed[0].getValue(), 4)
        with self.assertRaises(u.UnsupportedOperationException):
            entries.iterator().remove()
        self.assertEqual(self.java('m.put("a",1);java.util.Map.Entry<String,Integer> e=java.util.Collections.unmodifiableMap(m).entrySet().iterator().next();m.put("a",4);System.out.print(e.getValue());'), '4')

    def test_readonly_view_even_noop_mutators_throw(self):
        m = self.mapping()
        for view in (u.Collections.unmodifiableMap(m).keySet(), u.Collections.unmodifiableMap(m).values(), u.Collections.unmodifiableMap(m).entrySet()):
            for operation in (lambda: view.remove('missing'), lambda: view.addAll([]), lambda: view.removeIf(None)):
                with self.assertRaises(u.UnsupportedOperationException):
                    operation()
        self.assertEqual(self.java('java.util.Collection<Integer> v=java.util.Collections.unmodifiableMap(m).values();try{v.removeIf(null);}catch(UnsupportedOperationException e){System.out.print("blocked");}'), 'blocked')

    def test_unmodifiable_set_tracks_original(self):
        original = u.JavaSet(['a'])
        view = u.Collections.unmodifiableSet(original)
        original.add('b')
        self.assertEqual(view.size(), 2)
        with self.assertRaises(u.UnsupportedOperationException):
            view.remove('missing')
        self.assertEqual(view.hashCode(), original.hashCode())

    def test_hash_collisions_keep_distinct_keys_and_equal_replacement_keeps_original(self):
        class Key:
            def __init__(self, value):
                self.value = value
            def hashCode(self):
                return 7
            def equals(self, other):
                return isinstance(other, Key) and self.value == other.value
        m = u.JavaMap()
        first = Key('a')
        m.put(first, 1)
        m.put(Key('b'), 2)
        m.put(Key('a'), 3)
        self.assertEqual(m.size(), 2)
        self.assertIs(m.keySet().iterator().next(), first)
        self.assertEqual(m.get(Key('a')), 3)
        source = 'class K {String s;K(String s){this.s=s;}public int hashCode(){return 7;}public boolean equals(Object o){return o instanceof K && s.equals(((K)o).s);}}'
        expected = helper.ArrayTests().java(source, 'java.util.Map<K,Integer> m=new java.util.LinkedHashMap<>();K a=new K("a");m.put(a,1);m.put(new K("b"),2);m.put(new K("a"),3);System.out.print(m.size()+":"+(m.keySet().iterator().next()==a)+":"+m.get(new K("a")));')
        self.assertEqual(expected, '2:true:3')

    def test_compute_null_result_and_callback_structural_change(self):
        m = self.mapping()
        self.assertIsNone(m.computeIfAbsent('missing', lambda k: None))
        self.assertFalse(m.containsKey('missing'))
        def change(key):
            m.put('side', 7)
            return 8
        with self.assertRaises(u.ConcurrentModificationException):
            m.computeIfAbsent('new', change)
        self.assertFalse(m.containsKey('new'))
        self.assertEqual(self.java('m.computeIfAbsent("missing",k->null);try{m.computeIfAbsent("new",k->{m.put("side",7);return 8;});}catch(java.util.ConcurrentModificationException e){System.out.print(m.containsKey("missing")+":"+m.containsKey("new")+":"+m.get("side"));}'), 'false:false:7')

    def test_factory_maps_reject_mutation_null_and_duplicate_keys(self):
        original = self.mapping()
        copy = u.JavaMap.copyOf(original)
        original.put('a', 9)
        self.assertEqual(copy.get('a'), 1)
        for operation in (lambda: u.JavaMap.of('a', 1).put('b', 2), lambda: copy.clear()):
            with self.assertRaises(u.UnsupportedOperationException):
                operation()
        with self.assertRaises(u.JavaNullPointerException):
            u.JavaMap.of(None, 1)
        with self.assertRaises(u.IllegalArgumentException):
            u.JavaMap.of('a', 1, 'a', 2)
        self.assertEqual(self.java('m.put("a",1);java.util.Map<String,Integer> c=java.util.Map.copyOf(m);m.put("a",9);System.out.print(c.get("a"));'), '1')

    def test_native_and_java_text_key_identity_matches_python27(self):
        text = helper.pkg.load('java_stdlib.lang').JavaString
        m = u.JavaMap()
        m.put(text('key'), 1)
        self.assertEqual(m.get('key'), 1)
        m.put('key', 2)
        self.assertEqual(m.size(), 1)

    def test_for_each_reentrant_append_order_and_final_check_match_jdk(self):
        m = self.mapping()
        trace = []
        def callback(value):
            trace.append(str(value))
            if value == 1:
                m.put('c', 3)
        with self.assertRaises(u.ConcurrentModificationException):
            m.values().forEach(callback)
        expected = self.java('m.put("a",1);m.put("b",2);StringBuilder trace=new StringBuilder();try{m.values().forEach(v->{trace.append(v);if(v==1)m.put("c",3);});}catch(java.util.ConcurrentModificationException e){trace.append("changed");}System.out.print(trace);')
        self.assertEqual(''.join(trace) + 'changed', expected)

    def test_readonly_entry_typed_array_cannot_expose_mutable_nodes(self):
        m = self.mapping()
        arrays = helper.pkg.load('java_stdlib.java_arrays').JavaArrays
        destination = arrays.initialized('java.util.Map.Entry', 1, [None, None, None], u.MapEntry)
        result = u.Collections.unmodifiableMap(m).entrySet().toArray(destination)
        self.assertIs(result, destination)
        self.assertIsNone(result[2])
        with self.assertRaises(u.UnsupportedOperationException):
            result[0].setValue(99)
        self.assertEqual(m.get('a'), 1)
        expected = self.java('m.put("a",1);Object[] a=java.util.Collections.unmodifiableMap(m).entrySet().toArray(new java.util.Map.Entry<?,?>[2]);try{((java.util.Map.Entry<String,Integer>)a[0]).setValue(99);}catch(UnsupportedOperationException e){System.out.print(m.get("a"));}')
        self.assertEqual(expected, '1')

    def test_key_hash_and_equals_errors_are_not_swallowed(self):
        class BadHash:
            def hashCode(self):
                raise ValueError('hash failed')
        m = self.mapping()
        for operation in (m.containsKey, m.keySet().contains, m.get, m.keySet().remove):
            with self.assertRaisesRegex(ValueError, 'hash failed'):
                operation(BadHash())
        self.assertEqual(m.size(), 2)


if __name__ == '__main__':
    unittest.main()
