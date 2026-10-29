# -*- coding: utf-8 -*-
"""Stable public compiler intrinsics. This module executes no JVM code."""
from __future__ import absolute_import
from java_stdlib.lang import ArithmeticException
import math
import struct


class Int32(object):
    ABI_VERSION = 2

    @staticmethod
    def wrap(value):
        # Python 2 promotes the large modulo constant to long; restore a native int.
        return int(((int(value) + 2147483648) % 4294967296) - 2147483648)

    @staticmethod
    def add(left, right):
        return Int32.wrap(left + right)

    @staticmethod
    def subtract(left, right):
        return Int32.wrap(left - right)

    @staticmethod
    def multiply(left, right):
        return Int32.wrap(left * right)

    @staticmethod
    def negate(value):
        return Int32.wrap(-value)

    @staticmethod
    def bitAnd(left, right):
        return Int32.wrap(Int32.wrap(left) & Int32.wrap(right))

    @staticmethod
    def bitOr(left, right):
        return Int32.wrap(Int32.wrap(left) | Int32.wrap(right))

    @staticmethod
    def bitXor(left, right):
        return Int32.wrap(Int32.wrap(left) ^ Int32.wrap(right))

    @staticmethod
    def bitNot(value):
        return Int32.wrap(~Int32.wrap(value))

    @staticmethod
    def shiftLeft(left, distance):
        return Int32.wrap(Int32.wrap(left) << (int(distance) & 31))

    @staticmethod
    def shiftRight(left, distance):
        return Int32.wrap(left) >> (int(distance) & 31)

    @staticmethod
    def unsignedShiftRight(left, distance):
        return Int32.wrap((Int32.wrap(left) & 4294967295) >> (int(distance) & 31))

    @staticmethod
    def divide(left, right):
        left, right = Int32.wrap(left), Int32.wrap(right)
        if right == 0:
            raise ArithmeticException('/ by zero')
        result = abs(left) // abs(right)
        if (left < 0) != (right < 0):
            result = -result
        return Int32.wrap(result)

    @staticmethod
    def remainder(left, right):
        left, right = Int32.wrap(left), Int32.wrap(right)
        if right == 0:
            raise ArithmeticException('/ by zero')
        quotient = abs(left) // abs(right)
        if (left < 0) != (right < 0):
            quotient = -quotient
        return Int32.wrap(left - quotient * right)


class PrimitiveMath(object):
    """Java binary numeric promotion for long/float/double operations."""
    ABI_VERSION = 1

    @staticmethod
    def _long(value):
        return ((int(value) + 9223372036854775808) % 18446744073709551616) - 9223372036854775808

    @staticmethod
    def _float(value):
        from java_stdlib.function import Functional
        return Functional.float32(value)

    @staticmethod
    def unary(kind,operator,value):
        value=PrimitiveMath._long(value) if kind=='long' else PrimitiveMath._float(value) if kind=='float' else float(value)
        result=-value if operator=='-' else value
        return PrimitiveMath._long(result) if kind=='long' else PrimitiveMath._float(result) if kind=='float' else result

    @staticmethod
    def binary(kind,operator,left,right):
        if kind=='long':
            left,right=PrimitiveMath._long(left),PrimitiveMath._long(right)
            if operator in ('/','%'):
                if right==0:raise ArithmeticException('/ by zero')
                quotient=abs(left)//abs(right)
                if (left<0)!=(right<0):quotient=-quotient
                result=quotient if operator=='/' else left-quotient*right
            elif operator=='+':result=left+right
            elif operator=='-':result=left-right
            elif operator=='*':result=left*right
            else:raise ValueError('Unknown numeric operator: '+operator)
            return PrimitiveMath._long(result)
        convert=PrimitiveMath._float if kind=='float' else float
        left,right=convert(left),convert(right)
        if operator=='+':result=left+right
        elif operator=='-':result=left-right
        elif operator=='*':result=left*right
        elif operator=='/':
            if right==0.0:
                if left==0.0 or math.isnan(left):result=float('nan')
                else:result=math.copysign(float('inf'),left*right)
            else:result=left/right
        elif operator=='%':
            if right==0.0 or math.isinf(left):result=float('nan')
            elif math.isinf(right):result=left
            else:result=math.fmod(left,right)
        else:raise ValueError('Unknown numeric operator: '+operator)
        return convert(result)


JAVA_MAP = {'neocore.runtime.Int32': Int32, 'neocore.runtime.PrimitiveMath': PrimitiveMath}
