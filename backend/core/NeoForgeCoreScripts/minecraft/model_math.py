# -*- coding: utf-8 -*-
"""Reviewed matrix storage and model-state defaults. No GPU or codec simulation.

Matrix multiplication, SVD decomposition, quaternion interpolation and component
constructors are separate capabilities and are not exposed by this data subset.
"""
from __future__ import absolute_import
import struct
from java_stdlib.function import Functional
from java_stdlib.primitives import Int32
from java_stdlib.lang import NullPointerException,Enum,JavaString
from minecraft.official_interfaces import _declare,method,StringRepresentable

def _float(value):return Functional.float32(value)
def _bits(value):
    if value!=value:return 2143289344
    return struct.unpack('>I',struct.pack('>f',value))[0]


class Matrix4f(object):
    def __init__(self,*args):
        if not args:self.identity()
        elif len(args)==1:
            if args[0] is None:raise NullPointerException()
            if not isinstance(args[0],Matrix4f):raise TypeError('Reviewed Matrix4f copy requires Matrix4f')
            self._values=list(args[0]._values)
        elif len(args)==16:self._values=[_float(v) for v in args]
        else:raise TypeError('Unreviewed Matrix4f constructor')
    def identity(self):
        self._values=[1.0 if i%5==0 else 0.0 for i in range(16)]
        return self
    def zero(self):self._values=[0.0]*16;return self
    def equals(self,other):return type(self) is type(other) and all(_bits(a)==_bits(b) for a,b in zip(self._values,other._values))
    def hashCode(self):
        result=1
        for value in self._values:result=Int32.add(Int32.multiply(result,31),Int32.wrap(_bits(value)))
        return result
    def __eq__(self,other):return self.equals(other)
    def __ne__(self,other):return not self.equals(other)
    def __hash__(self):return self.hashCode()

def _component(index):
    def access(self,*args):
        if not args:return self._values[index]
        if len(args)!=1:raise TypeError('Matrix component requires zero or one argument')
        self._values[index]=_float(args[0]);return self
    return access
for _column in range(4):
    for _row in range(4):setattr(Matrix4f,'m'+str(_column)+str(_row),_component(_column*4+_row))


class Transformation(object):
    def __init__(self,matrix):
        if matrix is not None and not isinstance(matrix,Matrix4f):raise TypeError('Reviewed Transformation requires Matrix4f or null')
        # Original matrix constructor deliberately retains its input reference.
        self._matrix=Matrix4f() if matrix is None else matrix
    @staticmethod
    def identity():return _IDENTITY
    def getMatrix(self):return Matrix4f(self._matrix)
    def equals(self,other):return type(other) is Transformation and self._matrix.equals(other._matrix)
    def hashCode(self):return Int32.add(31,self._matrix.hashCode())
    def __eq__(self,other):return self.equals(other)
    def __ne__(self,other):return not self.equals(other)
    def __hash__(self):return self.hashCode()
_IDENTITY=Transformation(None)


INTERFACE_CONTRACTS={}
INTERFACE_TYPES={}
MODEL='net.minecraft.client.resources.model.ModelState'
def _rotation(self,**kwargs):return Transformation.identity()
def _uv(self,**kwargs):return False
ModelState=_declare(MODEL,[method('getRotation',[],'com.mojang.math.Transformation',True),method('isUvLocked',[],'boolean',True)],
    defaults={'getRotation':_rotation,'isUvLocked':_uv},registry=(INTERFACE_CONTRACTS,INTERFACE_TYPES))
INTERFACE_CONTRACTS[MODEL]['helper_abi']=7
JAVA_MAP=dict(INTERFACE_TYPES)
JAVA_MAP.update({'com.mojang.math.Transformation':Transformation,'org.joml.Matrix4f':Matrix4f})


class ItemDisplayContext(Enum,StringRepresentable):
    def __init__(self):raise TypeError('ItemDisplayContext is an enum')
    def getId(self):return self._ordinal
    def getSerializedName(self):return self._serialized
    def firstPerson(self):return self in (ItemDisplayContext.FIRST_PERSON_LEFT_HAND,ItemDisplayContext.FIRST_PERSON_RIGHT_HAND)
_context_values=[]
for _index,(_name,_serialized) in enumerate((('NONE','none'),('THIRD_PERSON_LEFT_HAND','thirdperson_lefthand'),('THIRD_PERSON_RIGHT_HAND','thirdperson_righthand'),('FIRST_PERSON_LEFT_HAND','firstperson_lefthand'),('FIRST_PERSON_RIGHT_HAND','firstperson_righthand'),('HEAD','head'),('GUI','gui'),('GROUND','ground'),('FIXED','fixed'))):
    _context=object.__new__(ItemDisplayContext);_context._name=JavaString(_name);_context._ordinal=_index;_context._serialized=JavaString(_serialized)
    setattr(ItemDisplayContext,_name,_context);_context_values.append(_context)
ItemDisplayContext._values=tuple(_context_values)
JAVA_MAP['net.minecraft.world.item.ItemDisplayContext']=ItemDisplayContext
