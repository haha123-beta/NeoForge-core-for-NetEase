import os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
pkg=helper.pkg;lang=pkg.load('java_stdlib.lang');util=pkg.load('java_stdlib.util');arrays=pkg.load('java_stdlib.java_arrays');EnumSet=util.EnumSet
Flag=pkg.load('minecraft.goals').Goal.Flag

def enum_type(name,count):
    cls=type(name,(lang.Enum,),{'_values':()});values=[]
    for ordinal in range(count):
        value=cls();value._name='V'+str(ordinal);value._ordinal=ordinal;values.append(value);setattr(cls,value._name,value)
    cls._values=tuple(values);return cls
Other=enum_type('Other',2);Large=enum_type('Large',130);Empty=enum_type('Empty',0)

class EnumSets(unittest.TestCase):
    def test_declared_order_all_range_complement_and_copy_match_jdk(self):
        java='import java.util.*;class Logic {enum Flag {MOVE,LOOK,JUMP,TARGET}static String run(){EnumSet<Flag> a=EnumSet.of(Flag.TARGET,Flag.MOVE);return a+":"+EnumSet.range(Flag.LOOK,Flag.TARGET)+":"+EnumSet.complementOf(a)+":"+EnumSet.allOf(Flag.class);}}'
        oracle=helper.ArrayTests().java(java,'System.out.print(Logic.run());')
        a=EnumSet.of(Flag.TARGET,Flag.MOVE)
        actual=':'.join(str(x) for x in [a,EnumSet.range(Flag.LOOK,Flag.TARGET),EnumSet.complementOf(a),EnumSet.allOf(Flag)])
        self.assertEqual(actual,oracle)
    def test_typed_empty_clone_and_copy_of_empty_collection(self):
        a=EnumSet.noneOf(Flag);b=EnumSet.copyOf(a);b.add(Flag.MOVE);self.assertTrue(a.isEmpty());self.assertEqual(str(b),'[MOVE]')
        for operation in [lambda:EnumSet.copyOf([]),lambda:EnumSet.copyOf(util.JavaList())]:
            with self.assertRaises(lang.IllegalArgumentException):operation()
        self.assertTrue(EnumSet.allOf(Empty).isEmpty());self.assertTrue(EnumSet.complementOf(EnumSet.noneOf(Empty)).isEmpty())
    def test_null_type_and_different_enum_checks(self):
        a=EnumSet.noneOf(Flag)
        for operation in [lambda:a.add(None),lambda:EnumSet.of(None),lambda:EnumSet.noneOf(None),lambda:EnumSet.copyOf(None),lambda:EnumSet.complementOf(None),lambda:EnumSet.range(Flag.MOVE,None),lambda:Flag.valueOf(None)]:
            with self.assertRaises(lang.NullPointerException):operation()
        for value in [Other.V0,'MOVE',1]:
            with self.assertRaises(lang.ClassCastException):a.add(value)
            self.assertFalse(a.contains(value));self.assertFalse(a.remove(value))
        self.assertFalse(a.contains(None));self.assertFalse(a.remove(None))
        with self.assertRaises(lang.ClassCastException):EnumSet.noneOf(str)
        with self.assertRaises(lang.ClassCastException):EnumSet.range(Flag.MOVE,Other.V0)
        with self.assertRaises(lang.IllegalArgumentException):EnumSet.range(Flag.TARGET,Flag.MOVE)
    def test_bulk_operations_keep_type_and_partial_add_failure(self):
        a=EnumSet.of(Flag.MOVE);self.assertFalse(a.addAll(EnumSet.noneOf(Other)));self.assertTrue(a.containsAll(EnumSet.noneOf(Other)))
        with self.assertRaises(lang.ClassCastException):a.addAll(EnumSet.of(Other.V0))
        with self.assertRaises(lang.ClassCastException):a.addAll([Flag.LOOK,Other.V0])
        self.assertEqual(str(a),'[MOVE, LOOK]');self.assertFalse(a.removeAll(EnumSet.allOf(Other)))
        self.assertTrue(a.retainAll(EnumSet.allOf(Other)));self.assertTrue(a.isEmpty())
        for name in ['addAll','containsAll','removeAll','retainAll']:
            with self.assertRaises(lang.NullPointerException):getattr(a,name)(None)
    def test_empty_sets_of_different_enum_types_equal_and_hashset_equality_symmetric(self):
        self.assertEqual(EnumSet.noneOf(Flag),EnumSet.noneOf(Other))
        a=EnumSet.of(Flag.MOVE,Flag.JUMP);b=util.JavaSet([Flag.MOVE,Flag.JUMP])
        self.assertTrue(a.equals(b));self.assertTrue(b.equals(a));self.assertEqual(a.hashCode(),b.hashCode());self.assertFalse(a.equals([Flag.MOVE,Flag.JUMP]))
    def test_small_iterator_snapshots_and_removes_current_live_value(self):
        a=EnumSet.of(Flag.MOVE,Flag.JUMP);cursor=a.iterator();a.remove(Flag.MOVE);a.add(Flag.LOOK)
        with self.assertRaises(lang.IllegalStateException):cursor.remove()
        self.assertIs(cursor.next(),Flag.MOVE);cursor.remove()
        with self.assertRaises(lang.IllegalStateException):cursor.remove()
        self.assertIs(cursor.next(),Flag.JUMP);self.assertFalse(cursor.hasNext())
        with self.assertRaises(pkg.load('java_stdlib._base').NoSuchElementException):cursor.next()
        self.assertEqual(str(a),'[LOOK, JUMP]')
    def test_large_iterator_reads_future_words_weakly_consistently_matches_jdk(self):
        constants=','.join('V'+str(i) for i in range(130))
        java='import java.util.*;class Logic {enum E {'+constants+'}static String run(){EnumSet<E> a=EnumSet.of(E.V0,E.V64);Iterator<E> i=a.iterator();a.add(E.V1);a.add(E.V65);a.remove(E.V64);String s="";while(i.hasNext()){s+=i.next().ordinal()+",";}return s+":"+a.size();}}'
        oracle=helper.ArrayTests().java(java,'System.out.print(Logic.run());')
        a=EnumSet.of(Large.V0,Large.V64);i=a.iterator();a.add(Large.V1);a.add(Large.V65);a.remove(Large.V64)
        actual=','.join(str(v.ordinal()) for v in i)+',:'+str(a.size());self.assertEqual(actual,oracle);self.assertEqual(actual,'0,65,:3')
    def test_large_ranges_complement_and_iterator_remove_at_word_boundaries(self):
        a=EnumSet.range(Large.V63,Large.V129);self.assertEqual(a.size(),67)
        self.assertEqual(EnumSet.complementOf(a).size(),63)
        i=a.iterator();self.assertIs(i.next(),Large.V63);i.remove();self.assertIs(i.next(),Large.V64);a.remove(Large.V64);i.remove();self.assertEqual(a.size(),65)
    def test_typed_to_array_and_goal_flag_values(self):
        a=EnumSet.of(Flag.JUMP,Flag.MOVE);dest=arrays.JavaArrays.create('net.minecraft.world.entity.ai.goal.Goal.Flag',[4],Flag)
        result=a.toArray(dest);self.assertIs(result,dest);self.assertIs(result[0],Flag.MOVE);self.assertIs(result[1],Flag.JUMP);self.assertIsNone(result[2])
        values=Flag.values();self.assertIsInstance(values,arrays.JavaArray);self.assertEqual([v.name() for v in values],['MOVE','LOOK','JUMP','TARGET']);values[0]=Flag.LOOK;self.assertIs(Flag.values()[0],Flag.MOVE)
        self.assertIs(Flag.valueOf('MOVE'),Flag.MOVE);self.assertIs(Flag.MOVE.getDeclaringClass(),Flag)
    def test_generic_copy_factory_observes_isempty_then_iterator_next_order(self):
        trace=[]
        class Cursor(object):
            def next(self):trace.append('next');return Flag.MOVE
            def hasNext(self):trace.append('hasNext');return False
        class Collection(object):
            def isEmpty(self):trace.append('isEmpty');return False
            def iterator(self):trace.append('iterator');return Cursor()
        result=EnumSet.copyOf(Collection());self.assertEqual(str(result),'[MOVE]')
        self.assertEqual(trace,['isEmpty','iterator','next','hasNext'])
    def test_self_bulk_aliases_and_java_varargs_array(self):
        array=arrays.JavaArrays.initialized('net.minecraft.world.entity.ai.goal.Goal.Flag',1,[Flag.LOOK,Flag.JUMP],Flag)
        a=EnumSet.of(Flag.MOVE,array);self.assertEqual(str(a),'[MOVE, LOOK, JUMP]')
        self.assertFalse(a.addAll(a));self.assertFalse(a.retainAll(a));self.assertTrue(a.removeAll(a));self.assertTrue(a.isEmpty())
    def test_null_default_callbacks_and_partial_filter_failure(self):
        a=EnumSet.allOf(Flag)
        for operation in [lambda:a.forEach(None),lambda:a.removeIf(None),lambda:a.iterator().forEachRemaining(None)]:
            with self.assertRaises(lang.NullPointerException):operation()
        def predicate(value):
            if value is Flag.LOOK:raise lang.IllegalArgumentException('fixture')
            return True
        with self.assertRaises(lang.IllegalArgumentException):a.removeIf(predicate)
        self.assertEqual(str(a),'[LOOK, JUMP, TARGET]')
    def test_capability_guard_refuses_untyped_and_changed_constants(self):
        gate=pkg.load('java_stdlib.enum_sets').EnumSets
        self.assertIs(gate.requireEnum('goal.Flag',Flag,['MOVE','LOOK','JUMP','TARGET']),Flag)
        with self.assertRaisesRegex(RuntimeError,'typed enum'):gate.requireEnum('goal.Flag',str,['MOVE'])
        with self.assertRaisesRegex(RuntimeError,'constants changed'):gate.requireEnum('goal.Flag',Flag,['MOVE'])
    def test_enum_and_object_hashes_follow_java_identity_int_contract(self):
        self.assertEqual(lang.System.identityHashCode(None),0)
        for value in [Flag.MOVE,Other.V0,lang.Object()]:
            self.assertEqual(value.hashCode(),lang.System.identityHashCode(value))
            self.assertTrue(-2147483648 <= value.hashCode() <= 2147483647)
        oracle=helper.ArrayTests().java('enum E {A}', 'System.out.print(System.identityHashCode(null)+":"+(E.A.hashCode()==System.identityHashCode(E.A)));')
        self.assertEqual(oracle,'0:true')
    def test_constant_specific_subclass_keeps_declaring_enum_type(self):
        class Constant(Other):pass
        value=Constant();value._name='CUSTOM';value._ordinal=0
        a=EnumSet.noneOf(Other);self.assertTrue(a.add(value));self.assertTrue(a.contains(Other.V0));self.assertIs(value.getDeclaringClass(),Other)

if __name__=='__main__':unittest.main()
