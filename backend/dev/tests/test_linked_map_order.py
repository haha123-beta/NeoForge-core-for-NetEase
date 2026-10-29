import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
u = helper.pkg.load('java_stdlib.util')


class LinkedMapOrderTests(unittest.TestCase):
    def test_containsvalue_compares_in_current_access_order(self):
        m = u.JavaLinkedHashMap(16, 1, True)
        m.put('a', 'one')
        m.put('b', 'two')
        m.get('a')
        seen = []
        class Query(object):
            def equals(self, other):
                seen.append(str(other))
                return False
        self.assertFalse(m.containsValue(Query()))
        source = 'import java.util.*;class Query {StringBuilder t;Query(StringBuilder t){this.t=t;}public boolean equals(Object v){t.append(v).append(",");return false;}}'
        body = 'Map<String,String> m=new LinkedHashMap<>(16,1,true);m.put("a","one");m.put("b","two");m.get("a");StringBuilder t=new StringBuilder();m.containsValue(new Query(t));System.out.print(t);'
        expected = helper.ArrayTests().java(source, body)
        self.assertEqual(','.join(seen) + ',', expected)
        self.assertEqual(list(m.keySet()), ['b', 'a'])

    def make(self, access=True):
        result = u.JavaLinkedHashMap(16, 1, access)
        for key, value in [('a', 1), ('b', 2), ('c', 3)]:
            result.put(key, value)
        return result

    def oracle(self, body):
        return helper.ArrayTests().java('import java.util.*;', 'Map<String,Integer> m=new LinkedHashMap<>(16,1,true);m.put("a",1);m.put("b",2);m.put("c",3);' + body)

    def test_get_default_and_put_move_accessed_entry_to_tail(self):
        m = self.make()
        m.get('a')
        m.getOrDefault('b', 0)
        m.put('c', 9)
        actual = str(m)
        self.assertEqual(actual, self.oracle('m.get("a");m.getOrDefault("b",0);m.put("c",9);System.out.print(m);'))

    def test_default_mode_stays_in_insertion_order(self):
        m = self.make(False)
        m.get('a')
        m.put('b', 7)
        self.assertEqual(list(m.keySet()), ['a', 'b', 'c'])

    def test_contains_and_entry_setvalue_do_not_count_as_accesses(self):
        m = self.make()
        m.containsKey('a')
        m.containsValue(1)
        m.entrySet().iterator().next().setValue(9)
        self.assertEqual(list(m.keySet()), ['a', 'b', 'c'])

    def test_get_of_tail_does_not_invalidate_iterator_but_other_access_does(self):
        m = self.make()
        it = m.keySet().iterator()
        m.get('c')
        self.assertEqual(it.next(), 'a')
        m.get('a')
        with self.assertRaises(u.ConcurrentModificationException):
            it.next()

    def test_replace_only_moves_when_replacement_occurs(self):
        m = self.make()
        self.assertFalse(m.replace('a', 9, 7))
        self.assertEqual(list(m.keySet()), ['a', 'b', 'c'])
        self.assertTrue(m.replace('a', 1, 7))
        m.replace('b', 8)
        self.assertEqual(str(m), self.oracle('m.replace("a",9,7);m.replace("a",1,7);m.replace("b",8);System.out.print(m);'))

    def test_compute_null_result_does_not_access_existing_null_mapping(self):
        m = self.make()
        m.put('a', None)
        m.get('b')
        before = list(m.keySet())
        m.computeIfAbsent('a', lambda key: None)
        self.assertEqual(list(m.keySet()), before)
        m.computeIfAbsent('a', lambda key: 7)
        self.assertEqual(str(m), self.oracle('m.put("a",null);m.get("b");m.computeIfAbsent("a",k->null);m.computeIfAbsent("a",k->7);System.out.print(m);'))

    def test_compute_and_merge_access_order_matches_jdk(self):
        m = self.make()
        m.compute('a', lambda k, v: v + 1)
        m.computeIfPresent('b', lambda k, v: v + 1)
        m.merge('a', 2, lambda old, new: old + new)
        self.assertEqual(str(m), self.oracle('m.compute("a",(k,v)->v+1);m.computeIfPresent("b",(k,v)->v+1);m.merge("a",2,(a,b)->a+b);System.out.print(m);'))

    def test_putifabsent_and_putall_generate_accesses_in_source_order(self):
        m = self.make()
        m.putIfAbsent('a', 7)
        m.putAll(u.JavaMap({'b': 5, 'c': 6}))
        self.assertEqual(str(m), self.oracle('m.putIfAbsent("a",7);Map<String,Integer> input=new LinkedHashMap<>();input.put("b",5);input.put("c",6);m.putAll(input);System.out.print(m);'))

    def test_compute_existing_value_and_missing_queries(self):
        m = self.make()
        self.assertEqual(m.getOrDefault('missing', 7), 7)
        self.assertEqual(list(m.keySet()), ['a', 'b', 'c'])
        self.assertEqual(m.computeIfAbsent('a', lambda key: self.fail('must not invoke mapping callback')), 1)
        self.assertEqual(list(m.keySet()), ['b', 'c', 'a'])

    def test_read_in_callback_can_be_structural_and_effects_remain(self):
        m = self.make()
        def callback(k, v):
            m.get('a')
            return 8
        with self.assertRaises(u.ConcurrentModificationException):
            m.compute('b', callback)
        self.assertEqual(list(m.keySet()), ['b', 'c', 'a'])

    def test_replaceall_and_readonly_reads_keep_underlying_rules(self):
        m = self.make()
        m.replaceAll(lambda k, v: v * 2)
        self.assertEqual(list(m.keySet()), ['a', 'b', 'c'])
        readonly = u.Collections.unmodifiableMap(m)
        self.assertEqual(readonly.get('a'), 2)
        self.assertEqual(list(m.keySet()), ['b', 'c', 'a'])

    def test_copy_constructor_and_clone_have_different_future_order_modes(self):
        m = self.make()
        clone, copy = m.clone(), u.JavaLinkedHashMap(m)
        clone.get('a')
        copy.get('a')
        self.assertEqual(list(clone.keySet()), ['b', 'c', 'a'])
        self.assertEqual(list(copy.keySet()), ['a', 'b', 'c'])
        clone.clear()
        self.assertEqual(m.size(), 3)

    def test_capacity_load_factor_and_null_constructor_checks(self):
        for args in [(-1,), (16, 0), (16, -1), (16, float('nan'))]:
            with self.subTest(args=args), self.assertRaises(u.IllegalArgumentException):
                u.JavaLinkedHashMap(*args)
        with self.assertRaises(u.NullPointerException):
            u.JavaLinkedHashMap(None)
        self.assertEqual(u.JavaLinkedHashMap(0, float('inf')).size(), 0)


if __name__ == '__main__':
    unittest.main()
