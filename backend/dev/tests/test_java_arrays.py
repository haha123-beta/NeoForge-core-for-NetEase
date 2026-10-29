import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from java_frontend import parse_source,api_index
from java_codegen import generate
from harness import Package
pkg=Package();api=pkg.load("core.java_api")
JAVA=Path(r"E:\Java\jdk-21.0.10\bin\java.exe");JAVAC=JAVA.with_name("javac.exe")

class ArrayTests(unittest.TestCase):
    def python(self,source):
        known,_=api_index();result=generate(parse_source(source,known_types=known))
        scope=api.JavaApiImports(sys).install(api.collect_java_api())
        try:
            namespace={};exec(result["python_source"],namespace);return namespace,result
        finally:scope.close()
    def java(self,source,body):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"Probe.java";path.write_text(source+'\npublic class Probe {public static void main(String[] args){'+body+'}}',encoding="utf-8")
            compiled=subprocess.run([str(JAVAC),"-encoding","UTF-8",str(path)],capture_output=True,text=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            result=subprocess.run([str(JAVA),"-cp",directory,"Probe"],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);return result.stdout.strip()
    def test_initializer_access_length_and_enhanced_for(self):
        source='class A {int values[]={1,2};int run(){int local[]=new int[]{3,4};int sum=0;for(int value:local){sum+=value;}local[0]+=1;return sum+local[0]+values.length;}}'
        namespace,result=self.python(source);actual=str(namespace["A"]().run())
        self.assertEqual(actual,self.java(source,'System.out.print(new A().run());'));self.assertEqual(actual,"13")
        self.assertIn("neocore.runtime.JavaArrays@1",result["required_runtime_helpers"])
    def test_rectangular_and_partial_dimensions_have_independent_rows(self):
        source='class A {int run(){int[][] grid=new int[2][3];int[][] partial=new int[4][];grid[0][1]=8;return grid[1][1]+grid[0].length+partial.length;}}'
        namespace,_=self.python(source);actual=str(namespace["A"]().run())
        self.assertEqual(actual,self.java(source,'System.out.print(new A().run());'));self.assertEqual(actual,"7")
    def test_nested_initializer_and_updates(self):
        source='class A {int run(){int[][] values={{1,2},{3}};values[1][0]++;return values[0][1]+values[1][0];}}'
        namespace,_=self.python(source);actual=str(namespace["A"]().run())
        self.assertEqual(actual,self.java(source,'System.out.print(new A().run());'));self.assertEqual(actual,"6")
    def test_simple_and_compound_assignment_check_order(self):
        source='class A {int trace;int[] array(){trace=trace*10+1;return null;}int index(){trace=trace*10+2;return 0;}int rhs(){trace=trace*10+3;return 4;}void simple(){array()[index()]=rhs();}void compound(){array()[index()]+=rhs();}}'
        namespace,_=self.python(source);null_type=pkg.load("java_stdlib.lang").NullPointerException
        simple,compound=namespace["A"](),namespace["A"]()
        with self.assertRaises(null_type):simple.simple()
        with self.assertRaises(null_type):compound.compound()
        actual=str(simple.trace)+","+str(compound.trace)
        self.assertEqual(actual,self.java(source,'A a=new A();A b=new A();try{a.simple();}catch(NullPointerException e){}try{b.compound();}catch(NullPointerException e){}System.out.print(a.trace+","+b.trace);'));self.assertEqual(actual,"123,12")
    def test_negative_size_checks_after_all_dimension_expressions(self):
        source='class A {int trace;int first(){trace=trace*10+1;return -1;}int second(){trace=trace*10+2;return 3;}int[][] make(){return new int[first()][second()];}}'
        namespace,_=self.python(source);obj=namespace["A"]()
        with self.assertRaises(pkg.load("java_stdlib.java_arrays").NegativeArraySizeException):obj.make()
        self.assertEqual(str(obj.trace),self.java(source,'A a=new A();try{a.make();}catch(NegativeArraySizeException e){}System.out.print(a.trace);'));self.assertEqual(obj.trace,12)
    def test_bounds_are_not_python_negative_indices(self):
        source='class A {int[] values={4};int read(int index){return values[index];}}'
        namespace,_=self.python(source);obj=namespace["A"]();exception=pkg.load("java_stdlib.lang").ArrayIndexOutOfBoundsException
        for index in (-1,1):
            with self.assertRaises(exception):obj.read(index)
        self.assertEqual(obj.read(0),4)
    def test_reference_covariance_checks_actual_array_component(self):
        source='class Base {}class Child extends Base {}class A {void run(){Base[] values=new Child[1];values[0]=new Base();}}'
        namespace,_=self.python(source)
        with self.assertRaises(pkg.load("java_stdlib.java_arrays").ArrayStoreException):namespace["A"]().run()
        self.assertEqual(self.java(source,'try{new A().run();}catch(ArrayStoreException e){System.out.print("store");}'),"store")
    def test_for_break_continue_and_array_element_writes_remain_live(self):
        source='class A {int run(){int[] values={1,2,3,4};int total=0;for(int value:values){if(value==1){values[1]=9;continue;}if(value==4){break;}total+=value;}return total;}}'
        namespace,_=self.python(source);actual=str(namespace["A"]().run())
        self.assertEqual(actual,self.java(source,'System.out.print(new A().run());'));self.assertEqual(actual,"12")

    def test_as_list_is_backed_and_iterator_sees_replacements(self):
        source='import java.util.Arrays;import java.util.List;class A {String[] values={"a","b"};List<String> view=Arrays.asList(values);String run(){view.set(0,"x");String total="";for(String value:view){total=total+value;values[1]="y";}return total;}}'
        namespace,_=self.python(source);obj=namespace["A"]();actual=str(obj.run())
        self.assertEqual(actual,self.java(source,'System.out.print(new A().run());'));self.assertEqual(actual,"xy")
        with self.assertRaises(pkg.load("java_stdlib.lang").UnsupportedOperationException):obj.view.add(None)
    def test_primitive_array_is_single_as_list_element(self):
        source='import java.util.Arrays;class A {int run(){int[] values={1,2};return Arrays.asList(values).size();}}'
        namespace,_=self.python(source);actual=str(namespace["A"]().run())
        self.assertEqual(actual,self.java(source,'System.out.print(new A().run());'));self.assertEqual(actual,"1")
    def test_copy_padding_range_and_overlapping_system_copy(self):
        source='import java.util.Arrays;class A {int run(){int[] a={1,2,3};System.arraycopy(a,0,a,1,2);int[] b=Arrays.copyOf(a,5);int[] c=Arrays.copyOfRange(a,2,5);Arrays.sort(a);return a[0]*100+a[1]*10+a[2]+b[4]+c[2];}}'
        namespace,_=self.python(source);actual=str(namespace["A"]().run())
        self.assertEqual(actual,self.java(source,'System.out.print(new A().run());'));self.assertEqual(actual,"112")
    def test_typed_collection_to_array_reuses_large_destination(self):
        source='import java.util.Arrays;import java.util.List;class A {String[] run(){List<String> values=Arrays.asList(new String[]{"a","b"});String[] destination={"x","y","z","last"};return values.toArray(destination);}}'
        namespace,_=self.python(source);array=namespace["A"]().run();actual=','.join('null' if value is None else str(value) for value in array)
        self.assertEqual(actual,self.java(source,'System.out.print(String.join(",",new A().run()));'));self.assertEqual(actual,"a,b,null,last")
    def test_to_array_no_argument_erases_component_and_is_independent(self):
        source='import java.util.Arrays;import java.util.List;class A {Object[] run(){String[] source={"a"};List<String> values=Arrays.asList(source);Object[] copy=values.toArray();source[0]="b";return copy;}}'
        namespace,_=self.python(source);array=namespace["A"]().run()
        self.assertEqual(array.component,'java.lang.Object');self.assertEqual(str(array[0]),self.java(source,'System.out.print(new A().run()[0]);'))
    def test_system_copy_reference_failure_preserves_successful_prefix(self):
        source='class Base {}class Child extends Base {}class A {Base[] source={new Child(),new Base()};Child[] destination=new Child[2];void run(){System.arraycopy(source,0,destination,0,2);}}'
        namespace,_=self.python(source);obj=namespace["A"]()
        with self.assertRaises(pkg.load("java_stdlib.java_arrays").ArrayStoreException):obj.run()
        actual=str(obj.destination[0] is not None).lower()+','+str(obj.destination[1] is None).lower()
        self.assertEqual(actual,self.java(source,'A a=new A();try{a.run();}catch(ArrayStoreException e){}System.out.print((a.destination[0]!=null)+","+(a.destination[1]==null));'))

    def test_array_copy_primitive_type_check_precedes_bounds(self):
        arrays=pkg.load("java_stdlib.java_arrays")
        with self.assertRaises(arrays.ArrayStoreException):
            arrays.JavaArrays.arraycopy(arrays.JavaArrays.create('int',(1,)),-1,arrays.JavaArrays.create('long',(1,)),0,1)
        self.assertEqual(self.java('', 'try{System.arraycopy(new int[1],-1,new long[1],0,1);}catch(Exception e){System.out.print(e.getClass().getSimpleName());}'),"ArrayStoreException")

if __name__=="__main__":unittest.main()
