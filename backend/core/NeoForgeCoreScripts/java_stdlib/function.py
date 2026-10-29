# -*- coding: utf-8 -*-
"""Java functional-interface adapters for typed translated lambdas and references."""
from __future__ import absolute_import
from java_stdlib.lang import NullPointerException, Runnable, Integer, Boolean, ClassCastException


def _callable(value, method):
    if value is None:
        raise NullPointerException("Functional argument is null")
    target = getattr(value, method, None)
    if callable(target):
        return target
    if callable(value):
        return value
    raise TypeError("Expected functional interface " + method)


class Supplier(object):
    def __init__(self, callback=None):
        self._callback = None if callback is None else _callable(callback, "get")

    def get(self):
        if self._callback is None:
            raise NotImplementedError("Implement Supplier.get")
        return self._callback()

    def __call__(self):
        return self.get()


class Function(object):
    def __init__(self, callback=None):
        self._callback = None if callback is None else _callable(callback, "apply")

    def apply(self, value):
        if self._callback is None:
            raise NotImplementedError("Implement Function.apply")
        return self._callback(value)

    def __call__(self, value):
        return self.apply(value)

    def compose(self, before):
        method = _callable(before, "apply")
        return Function(lambda value: self.apply(method(value)))

    def andThen(self, after):
        method = _callable(after, "apply")
        return Function(lambda value: method(self.apply(value)))

    @staticmethod
    def identity():
        return Function(lambda value: value)


JAVA_MAP = {
    "java.util.function.Supplier": Supplier,
    "java.util.function.Function": Function,
}


class Consumer(object):
    def __init__(self, callback=None):
        self._callback = None if callback is None else _callable(callback, "accept")
    def accept(self, value):
        if self._callback is None:
            raise NotImplementedError("Implement Consumer.accept")
        self._callback(value)
    def __call__(self, value):
        return self.accept(value)
    def andThen(self, after):
        method = _callable(after, "accept")
        def run(value):
            self.accept(value)
            method(value)
        return Consumer(run)


class Predicate(object):
    def __init__(self, callback=None):
        self._callback = None if callback is None else _callable(callback, "test")
    def test(self, value):
        if self._callback is None:
            raise NotImplementedError("Implement Predicate.test")
        return self._callback(value)
    def __call__(self, value):
        return self.test(value)
    def negate(self):
        return Predicate(lambda value: not self.test(value))


class BiFunction(object):
    def __init__(self, callback=None):
        self._callback = None if callback is None else _callable(callback, 'apply')

    def apply(self, first, second):
        if self._callback is None:
            raise NotImplementedError('Implement BiFunction.apply')
        return self._callback(first, second)

    def __call__(self, first, second):
        return self.apply(first, second)

    def andThen(self, after):
        method = _callable(after, 'apply')
        return BiFunction(lambda first, second: method(self.apply(first, second)))


class BiConsumer(object):
    def __init__(self, callback=None):
        self._callback = None if callback is None else _callable(callback, 'accept')

    def accept(self, first, second):
        if self._callback is None:
            raise NotImplementedError('Implement BiConsumer.accept')
        self._callback(first, second)

    def __call__(self, first, second):
        self.accept(first, second)

    def andThen(self, after):
        method = _callable(after, 'accept')
        def run(first, second):
            self.accept(first, second)
            method(first, second)
        return BiConsumer(run)




class _Reference(object):
    def __init__(self, callback, arity, event_type=None):
        self.callback, self.arity = callback, arity
        if event_type is not None:
            self.__neocore_event_type__ = event_type
    def __call__(self, *args):
        if len(args) != self.arity:
            raise TypeError("Functional callback argument arity mismatch")
        parameter_type = getattr(self, "__neocore_event_type__", None)
        if parameter_type is not None and len(args) == 1:
            if parameter_type is Integer:
                Functional.castInteger(args[0])
            else:
                Functional.castReference(args[0], parameter_type)
        return self.callback(*args)
    def get(self):
        return self()
    def apply(self, *values):
        return self(*values)
    def accept(self, *values):
        self(*values)
    def test(self, value):
        return self(value)
    def run(self):
        self()


class Functional(object):
    ABI_VERSION = 9
    @staticmethod
    def entityFactory(callback):
        from minecraft.entity import _EntityFactory
        return _EntityFactory(callback)
    @staticmethod
    def float32(value):
        import struct
        try:integer_types=(int,long)
        except NameError:integer_types=(int,)
        if isinstance(value,integer_types):
            # Round an exact integral significand once. Going via Python's
            # double can lose the sticky bit before the float rounding step.
            magnitude=abs(value);shift=magnitude.bit_length()-24
            if shift>0:
                significand,remainder=divmod(magnitude,1<<shift)
                half=1<<(shift-1)
                if remainder>half or remainder==half and significand&1:significand+=1
                magnitude=significand<<shift
                value=-magnitude if value<0 else magnitude
        try:
            return struct.unpack('f', struct.pack('f', float(value)))[0]
        except OverflowError:
            return float('-inf') if value < 0 else float('inf')
    @staticmethod
    def requireNonNull(value):
        if value is None:
            raise NullPointerException("Instance invocation receiver is null")
        return value

    @staticmethod
    def boxInt(value):
        if value is None or type(value) is Integer:
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            return Functional.box('int', value)
        raise ClassCastException("Boxing input is not an int")

    @staticmethod
    def _methodArgs(values, signature, input_types):
        result = list(values)
        for index, formal in enumerate(signature or ()):
            actual = input_types[index] if index < len(input_types) else None
            from java_stdlib._boxing import WRAPPERS
            names=dict(('java.lang.'+cls.__name__,kind) for kind,cls in WRAPPERS.items())
            if formal in WRAPPERS and actual in WRAPPERS and actual!=formal:
                result[index]=Functional.castPrimitive(formal,actual,result[index])
            elif formal in WRAPPERS and actual in names:
                primitive=names[actual]
                value=Functional.unbox(primitive,result[index])
                result[index]=value if formal==primitive else Functional.castPrimitive(formal,primitive,value)
            elif actual in WRAPPERS and (formal in names or formal in ('java.lang.Object','java.lang.Number')):
                result[index]=Functional.box(actual,result[index])
        return result

    @staticmethod
    def castInteger(value):
        if value is None or type(value) is Integer or (isinstance(value, int) and not isinstance(value, bool)):
            return value
        raise ClassCastException("Functional argument is not an Integer")

    @staticmethod
    def castReference(value, expected):
        from java_stdlib._boxing import cast_reference
        return cast_reference(value, expected)

    @staticmethod
    def isInstance(value, expected):
        if value is None:
            return False
        try:
            Functional.castReference(value, expected)
            return True
        except ClassCastException:
            return False

    @staticmethod
    def box(kind, value):
        from java_stdlib._boxing import box
        return box(kind, value)

    @staticmethod
    def unbox(kind, value):
        from java_stdlib._boxing import unbox
        return unbox(kind, value)

    @staticmethod
    def castPrimitive(target, source, value):
        from java_stdlib._boxing import cast_primitive
        return cast_primitive(target, source, value)

    @staticmethod
    def boxBoolean(value):
        if value is None or isinstance(value, Boolean):
            return value
        if isinstance(value, bool):
            return Boolean.valueOf(value)
        raise ClassCastException("Boxing input is not a boolean")

    @staticmethod
    def unboxBoolean(value):
        if value is None:
            raise NullPointerException("Boolean unboxing value is null")
        if isinstance(value, Boolean):
            return value.booleanValue()
        if isinstance(value, bool):
            return value
        raise ClassCastException("Functional argument is not a Boolean")

    @staticmethod
    def unboxInt(value):
        if value is None:
            raise NullPointerException("Integer unboxing value is null")
        if type(value) is Integer:
            return value.intValue()
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        raise ClassCastException("Functional argument is not an Integer")

    @staticmethod
    def make(kind, callback, arity, event_type=None):
        reference = _Reference(callback, arity, event_type)
        if isinstance(kind,dict):
            from minecraft.runtime_classes import RuntimeClasses
            binding=kind.get('generic_binding')
            base=(RuntimeClasses.bindGenericInterface(binding['java_name'],binding['arguments'],kind) if binding else RuntimeClasses.bindInterface(kind['java_name'],kind))
            methods=[m for m in kind['methods'] if m['abstract'] and not m['static']]
            if len(methods)!=1 or len(methods[0]['parameters'])!=arity:raise TypeError('Functional interface requires exactly one reviewed abstract method')
            abstract=methods[0];family=[m for m in kind['methods'] if m['name']==abstract['name'] and not m['static']]
            def invoke(self,*args,**kwargs):
                signature=kwargs.pop('_nc_java_signature',None)
                if kwargs:raise TypeError('Unexpected functional interface invocation keyword')
                matches=[m for m in family if (tuple(m['parameters'])==tuple(signature) if signature is not None else len(m['parameters'])==len(args))]
                if len(matches)!=1 or len(args)!=len(matches[0]['parameters']):raise TypeError('Functional interface invocation needs an unambiguous signature')
                selected=matches[0]
                if selected['abstract']:
                    result=reference(*args)
                    return None if selected['return_type']=='void' else result
                return getattr(base,abstract['name'])(self,*args,**{'_nc_java_signature':tuple(selected['parameters'])})
            proxy=type(str('_NativeSAM_'+base.__name__),(base,),{abstract['name']:invoke})
            return proxy()
        if kind is None:
            return reference
        adapters = {"Supplier": Supplier, "Function": Function, "Consumer": Consumer,
                    "Predicate": Predicate, "Runnable": Runnable,
                    "BiFunction": BiFunction, "BiConsumer": BiConsumer}
        result = adapters[kind](reference)
        if event_type is not None:
            result.__neocore_event_type__ = event_type
        return result
    @staticmethod
    def constructor(kind, owner, arity, signature, input_types=()):
        def create(*values):
            converted = Functional._methodArgs(values, signature, input_types)
            return owner(*converted, **{"_nc_java_constructor": signature})
        return Functional.make(kind, create, arity)

    @staticmethod
    def bound(kind, receiver, name, arity, event_type=None, signature=None, input_types=()):
        if receiver is None:
            raise NullPointerException("Bound method reference receiver is null")
        # Evaluate receiver exactly once and bind at reference creation.
        method = getattr(receiver, name)
        if signature is None:
            return Functional.make(kind, method, arity, event_type)
        def invoke(*values):
            converted = Functional._methodArgs(values, signature, input_types)
            return method(*converted, **{"_nc_java_signature": signature})
        return Functional.make(kind, invoke, arity, event_type)
    @staticmethod
    def unbound(kind, owner, name, arity, signature=None, input_types=()):
        def invoke(receiver, *args):
            if receiver is None:
                raise NullPointerException("Unbound method reference receiver is null")
            if not isinstance(receiver, owner):
                raise TypeError("Unbound reference receiver has incompatible type")
            method = getattr(receiver, name)
            return method(*Functional._methodArgs(args, signature, input_types), **{"_nc_java_signature": signature}) if signature is not None else method(*args)
        return Functional.make(kind, invoke, arity)


JAVA_MAP.update({"java.util.function.Consumer": Consumer,
                 "java.util.function.Predicate": Predicate,
                 "java.lang.Runnable": Runnable,
                 "neocore.runtime.Functional": Functional})

JAVA_MAP.update({"java.util.function.BiFunction": BiFunction,
                 "java.util.function.BiConsumer": BiConsumer})
