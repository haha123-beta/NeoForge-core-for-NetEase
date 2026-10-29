import os,sys,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_interfaces082 as oracle
from harness import Package

class ArrayCasts087(unittest.TestCase):
    def compare(self,body,expected):
        oracle.Interfaces082().compare({'use/Run.java':'package use;public class Run {public int run(){'+body+'}}'},expected)
    def test_same_component_and_object_view_preserve_identity_actual_python2(self):
        self.compare('Object value=new String[]{"x"};String[] a=(String[])value;Object[] b=(Object[])a;Object x=a;Object y=b;if(x!=y)return 99;return a.length+b.length;','2')
    def test_source_subclass_array_covariance_actual_python2(self):
        oracle.Interfaces082().compare({
            'data/Parent.java':'package data;public class Parent {}',
            'data/Child.java':'package data;public class Child extends Parent {}',
            'use/Run.java':'package use;import data.Parent;import data.Child;public class Run {public int run(){Object value=new Child[1];Parent[] a=(Parent[])value;return a.length;}}'
        },'1')
    def test_multidimensional_primitive_arrays_are_objects_at_outer_level(self):
        self.compare('Object value=new int[2][];Object[] a=(Object[])value;return a.length;','2')
    def test_incompatible_reified_casts_throw_original_class_cast(self):
        for body in ['Object value=new String[1];try{Integer[] bad=(Integer[])value;return 99;}catch(ClassCastException e){return 7;}',
                     'Object value=new int[1];try{Object[] bad=(Object[])value;return 99;}catch(ClassCastException e){return 7;}']:
            self.compare(body,'7')
    def test_covariant_view_keeps_array_store_check_and_null_cast(self):
        self.compare('Object[] a=(Object[])new String[1];try{a[0]=new Object();return 99;}catch(ArrayStoreException e){String[] n=(String[])null;return n==null?7:98;}','7')
    def test_declaration_metadata_rejects_core_alias_siblings(self):
        p=Package();a=p.load('java_stdlib.java_arrays');l=p.load('java_stdlib.lang')
        # Core aliases need their declared Java identities, not just Python isinstance.
        left=a.JavaArray('net.minecraft.world.entity.player.Player',1,[],object)
        self.assertIs(a.JavaArrays.cast(left,'net.minecraft.world.entity.Entity',1,object),left)
        with self.assertRaises(l.ClassCastException):a.JavaArrays.cast(left,'net.minecraft.world.entity.projectile.AbstractArrow',1,object)

if __name__=='__main__':unittest.main()
