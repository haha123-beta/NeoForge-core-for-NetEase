import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
u = helper.pkg.load('java_stdlib.util')
lang = helper.pkg.load('java_stdlib.lang')


class Key(object):
    def __init__(self, value):
        self.value = value
    def hashCode(self):
        return 7
    def equals(self, other):
        return isinstance(other, Key) and other.value == self.value


class SetContractsTests(unittest.TestCase):
    def test_specialized_goal_and_profiler_sets_keep_their_own_storage(self):
        goals = helper.pkg.load('minecraft.goals')
        profile = helper.pkg.load('minecraft.profiling')
        selector = goals.GoalSelector()
        values = selector.getAvailableGoals()
        self.assertEqual(values.size(), 0)
        self.assertEqual(list(values.toArray()), [])
        empty = profile.InactiveProfiler.INSTANCE.getChartedPaths()
        self.assertEqual(empty.size(), 0)
        self.assertFalse(empty.contains('missing'))
        self.assertEqual(empty.hashCode(), 0)
        self.assertTrue(empty.equals(u.JavaSet()))

    def oracle(self, body):
        return helper.ArrayTests().java('import java.util.*;', body)

    def test_colliding_keys_preserve_distinct_and_original_objects(self):
        first, second = Key(1), Key(2)
        values = u.JavaSet([first, second])
        self.assertEqual(values.size(), 2)
        self.assertFalse(values.add(Key(1)))
        self.assertIs(values.iterator().next(), first)
        self.assertTrue(values.remove(Key(2)))
        self.assertTrue(values.contains(Key(1)))

    def test_unicode_and_java_strings_share_membership(self):
        s = u.JavaSet([lang.JavaString(u'\U0001f600')])
        self.assertFalse(s.add(u'\U0001f600'))
        self.assertTrue(s.remove(u'\U0001f600'))
        self.assertEqual(s.size(), 0)

    def test_iterator_removal_writes_through_and_keeps_order(self):
        s = u.JavaSet(['a', 'b', 'c'])
        it = s.iterator()
        self.assertEqual(it.next(), 'a')
        it.remove()
        self.assertEqual(it.next(), 'b')
        actual = ','.join(s)
        self.assertEqual(actual, self.oracle('Set<String> s=new LinkedHashSet<>(List.of("a","b","c"));Iterator<String> i=s.iterator();i.next();i.remove();i.next();System.out.print(String.join(",",s));'))

    def test_duplicate_add_does_not_invalidate_iterator(self):
        s = u.JavaSet(['a', 'b'])
        it = s.iterator()
        self.assertFalse(s.add('a'))
        self.assertEqual(it.next(), 'a')
        s.add('c')
        self.assertTrue(it.hasNext())
        with self.assertRaises(u.ConcurrentModificationException):
            it.next()

    def test_iterator_exception_order_and_exhaustion(self):
        s = u.JavaSet(['a'])
        it = s.iterator()
        s.clear()
        with self.assertRaises(u.IllegalStateException):
            it.remove()
        with self.assertRaises(u.ConcurrentModificationException):
            it.next()
        it = s.iterator()
        with self.assertRaises(u.NoSuchElementException):
            it.next()

    def test_null_element_and_copy_constructor(self):
        s = u.JavaSet([None, 'a'])
        copy = u.JavaSet(s)
        self.assertTrue(copy.remove(None))
        self.assertTrue(s.contains(None))
        with self.assertRaises(lang.NullPointerException):
            u.JavaSet(None)
        with self.assertRaises(u.IllegalArgumentException):
            u.JavaSet(-1)

    def test_bulk_aliases_and_predicate_writeback(self):
        s = u.JavaSet(['a', 'b', 'c'])
        self.assertFalse(s.addAll(s))
        self.assertFalse(s.retainAll(s))
        self.assertTrue(s.removeIf(lambda v: v == 'b'))
        self.assertEqual(list(s), ['a', 'c'])
        self.assertTrue(s.removeAll(s))
        self.assertEqual(s.size(), 0)
        for name in ('addAll', 'removeAll', 'retainAll', 'containsAll', 'removeIf', 'forEach'):
            with self.subTest(name=name), self.assertRaises(lang.NullPointerException):
                getattr(s, name)(None)

    def test_removeall_uses_argument_contains_for_small_receiver(self):
        trace = []
        class Source(object):
            def __len__(self):
                return 3
            def contains(self, value):
                trace.append(value)
                return value == 'a'
        s = u.JavaSet(['a', 'b'])
        self.assertTrue(s.removeAll(Source()))
        self.assertEqual(trace, ['a', 'b'])
        self.assertEqual(list(s), ['b'])

    def test_typed_arrays_and_hash_match_jdk(self):
        s = u.JavaSet([lang.JavaString('a'), lang.JavaString('b')])
        arrays = helper.pkg.load('java_stdlib.java_arrays')
        destination = arrays.JavaArrays.initialized('java.lang.String', 1, [lang.JavaString(v) for v in ['x', 'y', 'z', 'last']], lang.JavaString)
        self.assertIs(s.toArray(destination), destination)
        actual = ','.join('null' if v is None else str(v) for v in destination) + ':' + str(s.hashCode())
        self.assertEqual(actual, self.oracle('Set<String> s=new LinkedHashSet<>(List.of("a","b"));String[] a={"x","y","z","last"};s.toArray(a);System.out.print(String.join(",",a)+":"+s.hashCode());'))

    def test_set_equality_does_not_accept_list(self):
        s = u.JavaSet(['a'])
        self.assertFalse(s.equals(u.JavaList(['a'])))
        self.assertFalse(s.equals(['a']))
        self.assertTrue(s.equals(u.JavaSet.of('a')))
        self.assertTrue(u.JavaSet.of('a').equals(s))

    def test_of_rejects_duplicate_and_null_with_jdk_evidence(self):
        with self.assertRaises(u.IllegalArgumentException):
            u.JavaSet.of('a', 'a')
        with self.assertRaises(lang.NullPointerException):
            u.JavaSet.of('a', None)
        self.assertEqual(self.oracle('try{Set.of("a","a");}catch(IllegalArgumentException e){System.out.print("duplicate:");}try{Set.of("a",(String)null);}catch(NullPointerException e){System.out.print("null");}'), 'duplicate:null')

    def test_copyof_deduplicates_and_detaches(self):
        source = u.JavaList(['a', 'a', 'b'])
        copy = u.JavaSet.copyOf(source)
        source.add('c')
        self.assertEqual(copy.size(), 2)
        self.assertFalse(copy.contains('c'))
        with self.assertRaises(lang.NullPointerException):
            u.JavaSet.copyOf([None])

    def test_immutable_factories_reject_noop_mutations_and_callbacks(self):
        for s in (u.JavaSet.of(), u.JavaSet.of('a'), u.JavaSet.copyOf([])):
            called = []
            for name, args in (('clear', ()), ('addAll', ([],)), ('remove', ('missing',)),
                               ('retainAll', (s,)), ('removeAll', ([],)),
                               ('removeIf', (lambda v: called.append(v) or False,))):
                with self.subTest(name=name), self.assertRaises(u.UnsupportedOperationException):
                    getattr(s, name)(*args)
            self.assertEqual(called, [])

    def test_emptyset_special_noops_and_no_global_contamination(self):
        s = u.Collections.emptySet()
        self.assertFalse(s.remove('a'))
        self.assertFalse(s.addAll([]))
        self.assertFalse(s.removeAll(['a']))
        self.assertFalse(s.retainAll([]))
        self.assertFalse(s.removeIf(lambda v: True))
        self.assertIsNone(s.clear())
        with self.assertRaises(u.UnsupportedOperationException):
            s.add('a')
        with self.assertRaises(u.UnsupportedOperationException):
            s.addAll(['a'])
        self.assertTrue(u.Collections.emptySet().isEmpty())
        self.assertEqual(self.oracle('Set<String> s=Collections.emptySet();System.out.print(s.remove("a")+":"+s.addAll(List.of())+":"+s.removeIf(v->true));s.clear();'), 'false:false:false')

    def test_emptymap_special_noops_and_readonly_views(self):
        m = u.Collections.emptyMap()
        self.assertIsNone(m.remove('a'))
        self.assertIsNone(m.putAll(u.JavaMap()))
        self.assertIsNone(m.clear())
        self.assertIsNone(m.replaceAll(lambda k, v: 7))
        with self.assertRaises(lang.NullPointerException):
            m.replaceAll(None)
        for name, args in (('put', ('a', 1)), ('remove', ('a', 1)), ('putIfAbsent', ('a', 1))):
            with self.subTest(name=name), self.assertRaises(u.UnsupportedOperationException):
                getattr(m, name)(*args)
        self.assertIs(m.keySet(), u.Collections.emptySet())
        self.assertIs(m.values(), u.Collections.emptySet())
        self.assertTrue(u.Collections.emptyMap().isEmpty())

    def test_hash_exceptions_are_not_swallowed(self):
        class Broken(object):
            def hashCode(self):
                raise u.IllegalStateException('hash failed')
        with self.assertRaises(u.IllegalStateException):
            u.JavaSet([Broken()])


if __name__ == '__main__':
    unittest.main()
