import os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as arrays_test
from java_codegen import NeedsLowering
RESOURCE='class R implements AutoCloseable {static int trace;int id;boolean fail;R(int id,boolean fail){this.id=id;this.fail=fail;}public void close(){trace=trace*10+id;if(fail){throw new IllegalArgumentException();}}}'
class ResourceTests(unittest.TestCase):
    def compare(self,source,expected):
        helper=arrays_test.ArrayTests();namespace,result=helper.python(source)
        actual=str(namespace['A']().run())
        self.assertEqual(actual,helper.java(source,'System.out.print(new A().run());'))
        self.assertEqual(actual,expected)
        self.assertIn('neocore.runtime.JavaExceptions@2',result['required_runtime_helpers'])
    def test_reverse_close_order(self):
        self.compare(RESOURCE+'class A {int run(){try(R one=new R(1,false);R two=new R(2,false)){R.trace=3;}return R.trace;}}','321')
    def test_body_exception_retains_two_close_failures(self):
        self.compare(RESOURCE+'class A {int run(){try(R one=new R(1,true);R two=new R(2,true)){throw new IllegalStateException();}catch(IllegalStateException ex){return ex.getSuppressed().length*100+R.trace;}}}','221')
    def test_close_failure_is_primary_when_body_succeeds(self):
        self.compare(RESOURCE+'class A {int run(){try(R one=new R(1,true);R two=new R(2,true)){}catch(IllegalArgumentException ex){return ex.getSuppressed().length*100+R.trace;}return 0;}}','121')
    def test_failed_initializer_closes_earlier_resource(self):
        source=RESOURCE+'class A {R fail(){throw new IllegalStateException();}int run(){try(R one=new R(1,true);R two=fail()){}catch(IllegalStateException ex){return ex.getSuppressed().length*100+R.trace;}return 0;}}'
        self.compare(source,'101')
    def test_return_and_null_resources(self):
        self.compare(RESOURCE+'class A {int run(){try(R one=null;R two=new R(2,false)){return 7;}finally{R.trace+=10;}}}','7')
    def test_existing_effectively_final_resource_reference(self):
        self.compare(RESOURCE+'class A {int run(){R one=new R(1,false);try(one){R.trace=2;}return R.trace;}}','21')
    def test_interface_requires_real_close_and_unknown_interfaces_are_rejected(self):
        helper=arrays_test.ArrayTests()
        for source in ('class R implements AutoCloseable {}','class R implements Runnable {public void run(){}}'):
            with self.assertRaises(NeedsLowering):helper.python(source)
    def test_suppressed_array_is_snapshot_and_rejects_self_or_null(self):
        pkg=arrays_test.pkg;lang=pkg.load('java_stdlib.lang')
        primary=lang.IllegalStateException();first=lang.IllegalArgumentException();second=lang.NullPointerException()
        primary.addSuppressed(first);snapshot=primary.getSuppressed();primary.addSuppressed(second)
        self.assertEqual(len(snapshot),1);self.assertIs(snapshot[0],first);self.assertEqual(len(primary.getSuppressed()),2)
        with self.assertRaises(lang.IllegalArgumentException):primary.addSuppressed(primary)
        with self.assertRaises(lang.NullPointerException):primary.addSuppressed(None)
        self.assertEqual(arrays_test.ArrayTests().java('', 'Throwable a=new IllegalStateException();a.addSuppressed(new IllegalArgumentException());Throwable[] s=a.getSuppressed();a.addSuppressed(new NullPointerException());System.out.print(s.length+","+a.getSuppressed().length);'),'1,2')

    def test_final_field_resource_reference(self):
        self.compare(RESOURCE+'class A {final R value=new R(1,false);int run(){try(this.value){R.trace=3;}return R.trace;}}','31')
    def test_var_resource_infers_original_source_class(self):
        self.compare(RESOURCE+'class A {int run(){try(var value=new R(1,false)){R.trace=2;}return R.trace;}}','21')
    def test_native_memory_output_stream_remains_usable_after_close(self):
        source='import java.io.ByteArrayOutputStream;import java.io.IOException;class A {int run(){ByteArrayOutputStream out=new ByteArrayOutputStream();try(out){out.write(7);}catch(IOException ex){return -1;}out.write(8);return out.toByteArray().length;}}'
        self.compare(source,'2')
    def test_resource_reference_reassignment_is_diagnosed(self):
        helper=arrays_test.ArrayTests()
        with self.assertRaises(NeedsLowering):helper.python(RESOURCE+'class A {void run(){R value=new R(1,false);value=new R(2,false);try(value){}}}')

    def test_reified_byte_array_copy_is_signed_and_independent(self):
        self.compare('import java.io.ByteArrayOutputStream;import java.io.IOException;class A {int run(){ByteArrayOutputStream out=new ByteArrayOutputStream();try(out){out.write(255);}catch(IOException ex){return -1;}byte[] copy=out.toByteArray();copy[0]=0;int first=out.toByteArray()[0];return out.size()*100+first;}}','99')
    def test_same_primary_and_close_throwable_rejects_self_suppression(self):
        self.compare('class R implements AutoCloseable {static RuntimeException failure=new IllegalStateException();public void close(){throw failure;}}class A {int run(){try(R value=new R()){throw R.failure;}catch(IllegalArgumentException ex){return 7;}catch(RuntimeException ex){return 1;}}}','7')
    def test_reference_interface_overload_selects_auto_closeable(self):
        self.compare(RESOURCE+'class A {int choose(Object value){return 1;}int choose(AutoCloseable value){return 2;}int run(){R value=new R(1,false);try(value){}return choose(value);}}','2')

if __name__=='__main__':unittest.main()
