import os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as arrays_test
from java_codegen import NeedsLowering
from java_exception_signatures import CONSTRUCTORS

class ThrowableTests(unittest.TestCase):
    def compare(self,source,expected=None):
        helper=arrays_test.ArrayTests();namespace,result=helper.python(source)
        actual=str(namespace['A']().run())
        self.assertEqual(actual,helper.java(source,'System.out.print(new A().run());'))
        if expected is not None:self.assertEqual(actual,expected)
        self.assertIn('neocore.runtime.JavaExceptions@3',result['required_runtime_helpers'])
    def test_no_argument_and_string_message(self):
        self.compare('class A {String run(){return new RuntimeException().toString()+"|"+new RuntimeException("message").getMessage();}}','java.lang.RuntimeException|message')
    def test_cause_constructor_derives_message_and_preserves_cause(self):
        self.compare('class A {String run(){RuntimeException cause=new RuntimeException("inner");RuntimeException outer=new RuntimeException(cause);return outer.getMessage()+"|"+outer.getCause().getMessage();}}','java.lang.RuntimeException: inner|inner')
    def test_message_and_cause_constructor(self):
        self.compare('class A {String run(){Throwable cause=new IllegalArgumentException("inner");RuntimeException outer=new RuntimeException("outer",cause);return outer.getLocalizedMessage()+"|"+outer.getCause().getMessage();}}','outer|inner')
    def test_init_cause_is_once_only(self):
        self.compare('class A {String run(){RuntimeException outer=new RuntimeException();outer.initCause(new IllegalArgumentException("inner"));try{outer.initCause(null);}catch(IllegalStateException ex){return outer.getCause().getMessage();}return "bad";}}','inner')
    def test_null_cause_constructor_initializes_cause(self):
        self.compare('class A {String run(){Throwable cause=null;RuntimeException outer=new RuntimeException(cause);try{outer.initCause(new IllegalArgumentException());}catch(IllegalStateException ex){return outer.toString();}return "bad";}}','java.lang.RuntimeException')
    def test_null_string_constructor_leaves_cause_initializable(self):
        self.compare('class A {String run(){String message=null;RuntimeException outer=new RuntimeException(message);outer.initCause(new IllegalArgumentException("inner"));return outer.toString()+"|"+outer.getCause().getMessage();}}','java.lang.RuntimeException|inner')
    def test_index_message_constructor_variants(self):
        self.compare('class A {String run(){return new IndexOutOfBoundsException(4).getMessage()+"|"+new ArrayIndexOutOfBoundsException(5).getMessage()+"|"+new StringIndexOutOfBoundsException(6).getMessage();}}')
    def test_assertion_error_object_cause_and_boolean(self):
        self.compare('class A {String run(){RuntimeException cause=new RuntimeException("inner");AssertionError error=new AssertionError(cause);return error.getMessage()+"|"+error.getCause().getMessage()+"|"+new AssertionError(true).getMessage();}}','java.lang.RuntimeException: inner|inner|true')
    def test_non_lang_exception_names_are_preserved(self):
        self.compare('import java.util.NoSuchElementException;import java.io.IOException;class A {String run(){return new NoSuchElementException("none").toString()+"|"+new IOException("io").toString();}}','java.util.NoSuchElementException: none|java.io.IOException: io')
    def test_null_without_declared_type_is_ambiguous(self):
        with self.assertRaises(NeedsLowering):arrays_test.ArrayTests().python('class A {RuntimeException run(){return new RuntimeException(null);}}')
    def test_recorded_constructor_facts_match_jdk_reflection(self):
        names=sorted(CONSTRUCTORS)
        import json
        body='String[] names={'+','.join(json.dumps(name) for name in names)+'};try{for(String name:names){for(java.lang.reflect.Constructor<?> ctor:Class.forName(name).getConstructors()){System.out.print(name+"|");Class<?>[] p=ctor.getParameterTypes();for(int i=0;i<p.length;i++){if(i>0)System.out.print(",");System.out.print(p[i].getName());}System.out.println();}}}catch(Exception ex){throw new RuntimeException(ex);}'
        facts={}
        for line in arrays_test.ArrayTests().java('',body).splitlines():
            name,params=line.split('|');facts.setdefault(name,[]).append(tuple(params.split(',')) if params else ())
        self.assertEqual({name:sorted(values) for name,values in facts.items()},CONSTRUCTORS)
    def test_runtime_registry_rejects_mismatched_constructor_identity(self):
        pkg=arrays_test.pkg;helper=pkg.load('java_stdlib.java_exceptions').JavaExceptions;lang=pkg.load('java_stdlib.lang')
        with self.assertRaises(lang.UnsupportedOperationException):helper.construct(lang.NullPointerException,'java.lang.RuntimeException',(),[])

    def test_self_cause_is_rejected_and_null_init_cause_is_final(self):
        self.compare('class A {String run(){RuntimeException first=new RuntimeException();try{first.initCause(first);}catch(IllegalArgumentException ex){}first.initCause(null);try{first.initCause(new RuntimeException());}catch(IllegalStateException ex){return "fixed";}return "bad";}}','fixed')
    def test_suppression_and_cause_are_independent(self):
        self.compare('class A {String run(){RuntimeException outer=new RuntimeException("outer",new IllegalStateException("cause"));outer.addSuppressed(new IllegalArgumentException("suppressed"));return outer.getCause().getMessage()+"|"+outer.getSuppressed()[0].getMessage();}}','cause|suppressed')
    def test_unknown_stack_frames_fail_explicitly(self):
        lang=arrays_test.pkg.load('java_stdlib.lang')
        with self.assertRaises(lang.UnsupportedOperationException):lang.RuntimeException().getStackTrace()
    def test_native_cause_shape_is_not_guessed(self):
        lang=arrays_test.pkg.load('java_stdlib.lang')
        value=lang.RuntimeException(lang.IllegalArgumentException())
        with self.assertRaises(lang.UnsupportedOperationException):value.getCause()

if __name__=='__main__':unittest.main()
