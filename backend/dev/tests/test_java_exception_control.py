import os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as array_tests
from java_codegen import NeedsLowering

class ExceptionControlTests(unittest.TestCase):
    def compare(self,source,expected):
        helper=array_tests.ArrayTests();namespace,result=helper.python(source)
        actual=str(namespace['A']().run())
        self.assertEqual(actual,helper.java(source,'System.out.print(new A().run());'))
        self.assertEqual(actual,expected)
        self.assertIn('neocore.runtime.JavaExceptions@1',result['required_runtime_helpers'])
    def test_implicit_java_lang_exception_and_first_compatible_catch(self):
        self.compare('class A {int run(){try{throw new IllegalArgumentException();}catch(IllegalArgumentException ex){return 1;}catch(RuntimeException ex){return 2;}}}','1')
    def test_multi_catch_and_finally_side_effect_order(self):
        self.compare('class A {int trace;int run(){try{throw new IllegalStateException();}catch(IllegalArgumentException | IllegalStateException ex){trace=1;}finally{trace=trace*10+2;}return trace;}}','12')
    def test_finally_return_overrides_try_return(self):
        self.compare('class A {int run(){try{return 1;}finally{return 2;}}}','2')
    def test_return_expression_is_evaluated_before_finally(self):
        self.compare('class A {int value=1;int run(){try{return value;}finally{value=9;}}}','1')
    def test_throw_null_becomes_java_null_pointer(self):
        self.compare('class A {int run(){try{throw null;}catch(NullPointerException ex){return 7;}}}','7')
    def test_rethrow_keeps_exception_identity(self):
        self.compare('class A {int run(){try{try{throw new IllegalArgumentException();}catch(RuntimeException ex){throw ex;}}catch(IllegalArgumentException ex){return 8;}}}','8')
    def test_finally_exception_overrides_pending_exception(self):
        self.compare('class A {int run(){try{try{throw new IllegalArgumentException();}finally{throw new IllegalStateException();}}catch(IllegalStateException ex){return 3;}}}','3')
    def test_loop_continue_and_break_execute_finally(self):
        self.compare('class A {int run(){int total=0;for(int i=0;i<4;i++){try{if(i==0){continue;}if(i==2){break;}total+=i;}finally{total+=10;}}return total;}}','31')
    def test_catch_parameter_scope_is_preserved(self):
        self.compare('class A {int run(){int result=0;try{throw new IllegalArgumentException();}catch(IllegalArgumentException value){result=3;}int value=4;return result+value;}}','7')
    def test_unknown_resource_type_remains_actionable(self):
        helper=array_tests.ArrayTests()
        with self.assertRaises(NeedsLowering) as raised:helper.python('class A {void run(){try(java.io.StringReader reader=new java.io.StringReader("x")){}}}')
        self.assertIn('Unresolved project type',str(raised.exception))

    def test_error_is_not_caught_as_exception(self):
        self.compare('class A {int run(){try{throw new AssertionError();}catch(Exception ex){return 1;}catch(Error ex){return 2;}}}','2')
    def test_throwable_catches_both_error_and_runtime_exception(self):
        self.compare('class A {int run(){int result=0;try{throw new AssertionError();}catch(Throwable ex){result+=1;}try{throw new IllegalArgumentException();}catch(Throwable ex){result+=2;}return result;}}','3')

if __name__=='__main__':unittest.main()
