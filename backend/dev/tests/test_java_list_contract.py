import os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as arrays_test
pkg=arrays_test.pkg
util=pkg.load("java_stdlib.util")
lang=pkg.load("java_stdlib.lang")

def display(values):
    return '['+','.join('null' if value is None else str(value) for value in values)+']'

class ListContractTests(unittest.TestCase):
    def java(self,body):
        return arrays_test.ArrayTests().java('',body).replace(' ','')
    def test_iterator_reads_replacement_and_removes_original(self):
        values=util.JavaList([1,2,3]);it=values.iterator()
        self.assertEqual(it.next(),1);values.set(1,9);self.assertEqual(it.next(),9)
        it.remove()
        with self.assertRaises(util.IllegalStateException):it.remove()
        self.assertEqual(it.next(),3)
        with self.assertRaises(util.NoSuchElementException):it.next()
        self.assertEqual(display(values),self.java('java.util.List<Integer> a=new java.util.ArrayList<>(java.util.List.of(1,2,3));java.util.Iterator<Integer> i=a.iterator();i.next();a.set(1,9);i.next();i.remove();i.next();System.out.print(a);'))
    def test_external_structural_change_is_detected(self):
        values=util.JavaList([1,2]);it=values.iterator();values.add(3)
        with self.assertRaises(util.ConcurrentModificationException):it.next()
        self.assertEqual(self.java('java.util.List<Integer> a=new java.util.ArrayList<>(java.util.List.of(1,2));java.util.Iterator<Integer> i=a.iterator();a.add(3);try{i.next();}catch(java.util.ConcurrentModificationException e){System.out.print("modified");}'),'modified')
    def test_list_iterator_previous_set_add_and_remove(self):
        values=util.JavaList([1,2,3]);it=values.listIterator(1)
        self.assertEqual(it.previous(),1);it.set(9);it.add(7);self.assertEqual(it.next(),9);it.remove()
        actual=display(values)+'|'+str(it.nextIndex())+'|'+str(it.previousIndex())
        expected=self.java('java.util.List<Integer> a=new java.util.ArrayList<>(java.util.List.of(1,2,3));java.util.ListIterator<Integer> i=a.listIterator(1);i.previous();i.set(9);i.add(7);i.next();i.remove();System.out.print(a+"|"+i.nextIndex()+"|"+i.previousIndex());')
        self.assertEqual(actual,expected)
    def test_nested_sublist_changes_update_ancestors_and_external_edits_invalidate(self):
        values=util.JavaList([0,1,2,3,4]);view=values.subList(1,4);child=view.subList(1,2)
        child.add(9);child.remove(0);view.set(0,8)
        actual=display(values)+'|'+display(view)+'|'+display(child)
        expected=self.java('java.util.List<Integer> a=new java.util.ArrayList<>(java.util.List.of(0,1,2,3,4));java.util.List<Integer> v=a.subList(1,4);java.util.List<Integer> c=v.subList(1,2);c.add(9);c.remove(0);v.set(0,8);System.out.print(a+"|"+v+"|"+c);')
        self.assertEqual(actual,expected)
        values.add(5)
        with self.assertRaises(util.ConcurrentModificationException):view.size()
        with self.assertRaises(util.ConcurrentModificationException):child.get(0)
    def test_indexed_add_accepts_null_and_returns_void(self):
        values=util.JavaList([1]);self.assertIsNone(values.add(0,None))
        actual=display(values)
        self.assertEqual(actual,self.java('java.util.List<Integer> a=new java.util.ArrayList<>(java.util.List.of(1));a.add(0,null);System.out.print(a);'))
        for bad in (-1,2):
            with self.assertRaises(lang.IndexOutOfBoundsException):values.get(bad)
    def test_factory_snapshot_null_rejection_and_live_read_only_wrapper(self):
        original=util.JavaList([1,2]);snapshot=util.JavaList.copyOf(original);view=util.Collections.unmodifiableList(original)
        original.set(0,9);original.add(3)
        actual=display(snapshot)+'|'+display(view)
        expected=self.java('java.util.List<Integer> a=new java.util.ArrayList<>(java.util.List.of(1,2));java.util.List<Integer> c=java.util.List.copyOf(a);java.util.List<Integer> v=java.util.Collections.unmodifiableList(a);a.set(0,9);a.add(3);System.out.print(c+"|"+v);')
        self.assertEqual(actual,expected)
        for fixed in (snapshot,view,util.JavaList.of(1)):
            with self.assertRaises(lang.UnsupportedOperationException):fixed.add(4)
            with self.assertRaises(lang.UnsupportedOperationException):fixed.clear()
        with self.assertRaises(lang.NullPointerException):util.JavaList.of(None)
        with self.assertRaises(lang.NullPointerException):util.JavaList.copyOf([None])
    def test_array_backed_sublist_cannot_resize(self):
        arrays=pkg.load('java_stdlib.java_arrays');array=arrays.JavaArrays.initialized('java.lang.Object',1,[1,2,3],object)
        sub=util.Arrays.asList(array).subList(1,3);sub.set(0,8)
        with self.assertRaises(lang.UnsupportedOperationException):sub.remove(0)
        self.assertEqual(display(array),self.java('Integer[] a={1,2,3};java.util.List<Integer> v=java.util.Arrays.asList(a).subList(1,3);v.set(0,8);try{v.remove(0);}catch(UnsupportedOperationException e){}System.out.print(java.util.Arrays.toString(a));'))
    def test_translated_enhanced_for_uses_live_iterator(self):
        source='import java.util.ArrayList;import java.util.List;class A {String run(){List<String> values=new ArrayList<>();values.add("a");values.add("b");String result="";for(String value:values){result=result+value;values.set(1,"z");}return result;}}'
        helper=arrays_test.ArrayTests();namespace,_=helper.python(source)
        self.assertEqual(str(namespace['A']().run()),helper.java(source,'System.out.print(new A().run());'))

    def test_translated_integer_list_unboxing_and_remove_overloads(self):
        source='import java.util.List;import java.util.ArrayList;class A {int run(){List<Integer> values=new ArrayList<>();values.add(10);values.add(20);values.add(10);Object key=10;boolean found=values.remove(key);int removed=values.remove(0);int total=0;for(int value:values){total+=value;}if(found){total+=removed;}return total+values.get(0);}}'
        helper=arrays_test.ArrayTests();namespace,result=helper.python(source)
        self.assertEqual(str(namespace['A']().run()),helper.java(source,'System.out.print(new A().run());'))
        self.assertIn('neocore.runtime.JavaCollections@1',result['required_runtime_helpers'])
    def test_translated_list_iterator_keeps_element_generic_type(self):
        source='import java.util.List;import java.util.ArrayList;import java.util.ListIterator;class A {int run(){List<Integer> values=new ArrayList<>();values.add(2);values.add(3);ListIterator<Integer> it=values.listIterator();int first=it.next();it.set(7);it.add(9);int next=it.next();it.remove();return first+next+values.get(1);}}'
        helper=arrays_test.ArrayTests();namespace,_=helper.python(source)
        self.assertEqual(str(namespace['A']().run()),helper.java(source,'System.out.print(new A().run());'))
    def test_bulk_integer_removal_uses_values_instead_of_indexes(self):
        values=util.JavaList([1,2,1,3]);self.assertTrue(values.removeAll(util.JavaList([1])));self.assertTrue(values.retainAll(util.JavaList([3])))
        self.assertEqual(display(values),self.java('java.util.List<Integer> a=new java.util.ArrayList<>(java.util.List.of(1,2,1,3));a.removeAll(java.util.List.of(1));a.retainAll(java.util.List.of(3));System.out.print(a);'))

    def test_collections_empty_and_singleton_no_op_operations(self):
        empty=util.Collections.emptyList();empty.clear();empty.sort()
        with self.assertRaises(lang.UnsupportedOperationException):empty.add(1)
        singleton=util.Collections.singletonList(1);singleton.sort()
        self.assertEqual(self.java('java.util.Collections.emptyList().clear();java.util.Collections.singletonList(1).sort(null);System.out.print("ok");'),'ok')

    def test_exception_superclasses_match_java_and_share_library_identity(self):
        base=pkg.load('java_stdlib._base')
        self.assertIs(base.RuntimeException,lang.RuntimeException)
        self.assertIs(base.UnsupportedOperationException,lang.UnsupportedOperationException)
        names=('IllegalArgumentException','IllegalStateException','IndexOutOfBoundsException','ArrayIndexOutOfBoundsException','StringIndexOutOfBoundsException')
        actual=','.join(getattr(lang,name).__bases__[0].__name__ for name in names)
        expected=self.java('Class<?>[] types={IllegalArgumentException.class,IllegalStateException.class,IndexOutOfBoundsException.class,ArrayIndexOutOfBoundsException.class,StringIndexOutOfBoundsException.class};for(int i=0;i<types.length;i++){if(i>0)System.out.print(",");System.out.print(types[i].getSuperclass().getSimpleName());}')
        self.assertEqual(actual,expected)
        self.assertTrue(issubclass(util.NoSuchElementException,lang.RuntimeException))

if __name__=='__main__':unittest.main()
