# -*- coding: utf-8 -*-
"""Java scalar ABI conversions. Uses the existing wrappers, never duck typing."""
from __future__ import absolute_import
import math
from java_stdlib.lang import (Integer, Long, Float, Double, Boolean, Byte, Short,
                              Character, Number, ClassCastException, NullPointerException)

try:
    _integers = (int, long)
    _strings = (basestring,)
    _character = unichr
except NameError:
    _integers = (int,)
    _strings = (str,)
    _character = chr

WRAPPERS = {'boolean': Boolean, 'byte': Byte, 'short': Short, 'char': Character,
            'int': Integer, 'long': Long, 'float': Float, 'double': Double}
_NUMERIC = (Byte, Short, Integer, Long, Float, Double)
_BITS = {'byte': 8, 'short': 16, 'int': 32, 'long': 64}
_CACHE = {}


def _float32(value):
    from java_stdlib.function import Functional
    return Functional.float32(value)


def _char(value):
    if not isinstance(value, _strings) or len(value) != 1 or ord(value) > 65535:
        raise ClassCastException('Expected one UTF-16 char unit')
    return value


def box(kind, value):
    cls = WRAPPERS.get(kind)
    if cls is None:
        raise ValueError('Unreviewed boxing kind: ' + kind)
    if value is None or type(value) is cls:
        return value
    if type(value) in WRAPPERS.values():
        raise ClassCastException('Boxing cannot change wrapper identity')
    if kind == 'boolean':
        if type(value) is not bool:
            raise ClassCastException('Expected boolean boxing input')
        if kind not in _CACHE:
            _CACHE[kind] = (Boolean(False), Boolean(True))
        return _CACHE[kind][1 if value else 0]
    if kind == 'char':
        scalar = _char(value)
        ordinal = ord(scalar)
    elif kind in _BITS:
        if not isinstance(value, _integers) or isinstance(value, bool):
            raise ClassCastException('Expected integral boxing input')
        bits = _BITS[kind]
        if not -(1 << (bits - 1)) <= value < (1 << (bits - 1)):
            raise ClassCastException('Boxing input outside declared primitive range')
        scalar = value
        ordinal = value
    else:
        if not isinstance(value, _integers + (float,)) or isinstance(value, bool):
            raise ClassCastException('Expected floating boxing input')
        scalar = _float32(value) if kind == 'float' else float(value)
        return cls(scalar)
    # Required small-value identities; explicit constructors remain distinct.
    if (kind == 'char' and 0 <= ordinal <= 127) or (kind != 'char' and -128 <= ordinal <= 127):
        key = (kind, scalar)
        if key not in _CACHE:
            _CACHE[key] = cls(scalar)
        return _CACHE[key]
    return cls(scalar)


def unbox(kind, value):
    cls = WRAPPERS.get(kind)
    if cls is None:
        raise ValueError('Unreviewed unboxing kind: ' + kind)
    if value is None:
        raise NullPointerException('Unboxing value is null')
    # Byte and Short currently reuse Integer implementation, but Java declares
    # these as distinct final classes. Python isinstance is insufficient.
    if type(value) is not cls:
        raise ClassCastException('Unboxing wrapper differs from declared type')
    method = {'boolean':'booleanValue','byte':'byteValue','short':'shortValue',
              'char':'charValue','int':'intValue','long':'longValue',
              'float':'floatValue','double':'doubleValue'}[kind]
    result = getattr(value, method)()
    return _float32(result) if kind == 'float' else result


def cast_reference(value, expected):
    if value is None:
        return None
    if expected in WRAPPERS.values():
        valid = type(value) is expected
    elif expected is Number and type(value) in _NUMERIC:
        valid = True
    else:
        valid = isinstance(value, expected)
    if not valid:
        raise ClassCastException('Reference has incompatible Java identity')
    return value


def cast_primitive(target, source, value):
    if target not in WRAPPERS or source not in WRAPPERS:
        raise ValueError('Unreviewed primitive conversion')
    if 'boolean' in (source, target):
        if source != target or type(value) is not bool:
            raise ClassCastException('Boolean has no numeric conversion')
        return value
    if source == 'char':
        value = ord(_char(value))
    elif source in _BITS:
        if not isinstance(value, _integers) or isinstance(value, bool):
            raise ClassCastException('Expected integral primitive')
    else:
        if not isinstance(value, _integers + (float,)) or isinstance(value, bool):
            raise ClassCastException('Expected floating primitive')
        value = _float32(value) if source == 'float' else float(value)
    if target == 'float':
        return _float32(value)
    if target == 'double':
        return float(value)
    if source in ('float', 'double'):
        bits = 64 if target == 'long' else 32
        low, high = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
        value = 0 if math.isnan(value) else high if value >= high else low if value <= low else int(value)
    bits = 16 if target == 'char' else _BITS[target]
    if target == 'char':
        return _character(int(value) & 65535)
    return ((int(value) + (1 << (bits - 1))) % (1 << bits)) - (1 << (bits - 1))
