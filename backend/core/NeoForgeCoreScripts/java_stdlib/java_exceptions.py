# -*- coding: utf-8 -*-
from __future__ import absolute_import
from java_stdlib._base import JavaThrowable
_CONSTRUCTORS = {'java.lang.Throwable': [(), ('java.lang.String',), ('java.lang.String', 'java.lang.Throwable'), ('java.lang.Throwable',)], 'java.lang.Exception': [(), ('java.lang.String',), ('java.lang.String', 'java.lang.Throwable'), ('java.lang.Throwable',)], 'java.lang.RuntimeException': [(), ('java.lang.String',), ('java.lang.String', 'java.lang.Throwable'), ('java.lang.Throwable',)], 'java.lang.Error': [(), ('java.lang.String',), ('java.lang.String', 'java.lang.Throwable'), ('java.lang.Throwable',)], 'java.lang.IllegalArgumentException': [(), ('java.lang.String',), ('java.lang.String', 'java.lang.Throwable'), ('java.lang.Throwable',)], 'java.lang.IllegalStateException': [(), ('java.lang.String',), ('java.lang.String', 'java.lang.Throwable'), ('java.lang.Throwable',)], 'java.lang.NullPointerException': [(), ('java.lang.String',)], 'java.lang.AssertionError': [(), ('boolean',), ('char',), ('double',), ('float',), ('int',), ('java.lang.Object',), ('java.lang.String', 'java.lang.Throwable'), ('long',)], 'java.lang.IndexOutOfBoundsException': [(), ('int',), ('java.lang.String',), ('long',)], 'java.lang.ArrayIndexOutOfBoundsException': [(), ('int',), ('java.lang.String',)], 'java.lang.StringIndexOutOfBoundsException': [(), ('int',), ('java.lang.String',)], 'java.lang.UnsupportedOperationException': [(), ('java.lang.String',), ('java.lang.String', 'java.lang.Throwable'), ('java.lang.Throwable',)], 'java.lang.ArithmeticException': [(), ('java.lang.String',)], 'java.lang.ClassCastException': [(), ('java.lang.String',)], 'java.lang.NumberFormatException': [(), ('java.lang.String',)], 'java.lang.NegativeArraySizeException': [(), ('java.lang.String',)], 'java.lang.ArrayStoreException': [(), ('java.lang.String',)], 'java.util.NoSuchElementException': [(), ('java.lang.String',), ('java.lang.String', 'java.lang.Throwable'), ('java.lang.Throwable',)], 'java.util.ConcurrentModificationException': [(), ('java.lang.String',), ('java.lang.String', 'java.lang.Throwable'), ('java.lang.Throwable',)], 'java.io.IOException': [(), ('java.lang.String',), ('java.lang.String', 'java.lang.Throwable'), ('java.lang.Throwable',)], 'java.lang.CloneNotSupportedException': [(), ('java.lang.String',)]}
from java_stdlib.java_auto_closeable import JavaAutoCloseable
from java_stdlib.lang import NullPointerException, UnsupportedOperationException

class JavaExceptions(object):
    ABI_VERSION = 3
    @staticmethod
    def throwable(value):
        if value is None:return NullPointerException("Java throw null")
        if not isinstance(value,JavaThrowable):raise UnsupportedOperationException("Thrown value has no supported Java exception identity")
        return value
    @staticmethod
    def catchType(value):
        if isinstance(value,tuple):return tuple(JavaExceptions.catchType(part) for part in value)
        if not isinstance(value,type) or not issubclass(value,JavaThrowable):
            raise UnsupportedOperationException("Catch type has no supported Java exception identity")
        return value

    @staticmethod
    def construct(exception_class,identity,signature,arguments):
        from java_stdlib import lang, util, java_arrays, memory_streams
        from java_stdlib.lang import JavaString, java_to_string, _TEXT_TYPES
        registry={}
        for module in (lang,util,java_arrays,memory_streams):registry.update(module.JAVA_MAP)
        if registry.get(identity) is not exception_class or tuple(signature) not in _CONSTRUCTORS.get(identity,[]):
            raise UnsupportedOperationException("Throwable constructor ABI facts do not match runtime type")
        if len(signature)!=len(arguments):raise UnsupportedOperationException("Throwable constructor argument count mismatch")
        cause=None;cause_set=False;message=None
        if signature==('java.lang.Throwable',):
            cause=arguments[0];cause_set=True
            if cause is not None:message=JavaExceptions.require(cause).toString()
        elif signature==('java.lang.String','java.lang.Throwable'):
            message,cause=arguments;cause_set=True
        elif signature==('java.lang.String',):message=arguments[0]
        elif signature in (('int',),('long',)) and identity in ('java.lang.IndexOutOfBoundsException','java.lang.ArrayIndexOutOfBoundsException','java.lang.StringIndexOutOfBoundsException'):
            prefix={'java.lang.IndexOutOfBoundsException':'Index out of range: ','java.lang.ArrayIndexOutOfBoundsException':'Array index out of range: ','java.lang.StringIndexOutOfBoundsException':'String index out of range: '}[identity]
            message=JavaString(prefix+str(arguments[0]))
        elif identity=='java.lang.AssertionError' and len(arguments)==1:
            item=arguments[0]
            if signature[0] in ('float','double','char'):raise UnsupportedOperationException("AssertionError primitive text conversion is not reviewed")
            if item is not None and not isinstance(item,(bool,int,JavaThrowable)+_TEXT_TYPES) and not callable(getattr(item,'toString',None)):
                raise UnsupportedOperationException("AssertionError payload has no reviewed Java toString")
            rendered=item.toString() if callable(getattr(item,'toString',None)) else java_to_string(item)
            if rendered is not None and not isinstance(rendered,_TEXT_TYPES):raise UnsupportedOperationException("AssertionError toString result is not a Java string")
            message=JavaString(rendered) if rendered is not None else None
            if isinstance(item,JavaThrowable):cause=item;cause_set=True
        elif signature:raise UnsupportedOperationException("Throwable constructor form is not implemented")
        if message is not None and not isinstance(message,_TEXT_TYPES):
            raise UnsupportedOperationException("Throwable detail message is not a Java string")
        if cause is not None:JavaExceptions.require(cause)
        value=exception_class(message) if message is not None else exception_class()
        value._nc_java_name=identity
        value._nc_message=message
        value._nc_cause=cause
        value._nc_cause_initialized=cause_set
        return value
    @staticmethod
    def require(value):
        if value is None:raise NullPointerException("Throwable receiver is null")
        if not isinstance(value,JavaThrowable):raise UnsupportedOperationException("Receiver has no Java throwable identity")
        return value
    @staticmethod
    def requireResource(value):
        if value is None:raise NullPointerException("Resource receiver is null")
        if not isinstance(value,JavaAutoCloseable):raise UnsupportedOperationException("Resource implementation lacks reviewed AutoCloseable contract")
        return value
    @staticmethod
    def resource(value):
        if value is not None and not isinstance(value,JavaAutoCloseable):
            raise UnsupportedOperationException("Resource lacks the reviewed AutoCloseable interface")
        return JavaResource(value)

class JavaResource(object):
    def __init__(self,value):self.value=value
    def __enter__(self):return self.value
    def __exit__(self,exception_type,primary,traceback):
        if self.value is None:return False
        try:self.value.close()
        except JavaThrowable as closing:
            if primary is None:raise
            if not isinstance(primary,JavaThrowable):
                raise UnsupportedOperationException("Cannot model suppression on a native Python failure")
            primary.addSuppressed(closing)
        return False

JAVA_MAP={'neocore.runtime.JavaExceptions':JavaExceptions}
