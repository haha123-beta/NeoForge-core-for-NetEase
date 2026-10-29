# -*- coding: utf-8 -*-
"""Minecraft 1.21.1 vertex layout data; GPU/registration APIs stay unsupported."""
from __future__ import absolute_import
from java_stdlib.lang import Enum, JavaString, NullPointerException, IllegalArgumentException, IllegalStateException, ArrayIndexOutOfBoundsException, UnsupportedOperationException
from java_stdlib.primitives import Int32
from java_stdlib.java_arrays import JavaArray
from java_stdlib.util import ImmutableList


def _nonnull(value):
    if value is None:raise NullPointerException()
    return value


class _Type(Enum):
    def __init__(self):raise TypeError('VertexFormatElement.Type is an enum')
    def size(self):return self._size
    def glType(self):return self._gl_type
    def toString(self):return self._label


class _Usage(Enum):
    def __init__(self):raise TypeError('VertexFormatElement.Usage is an enum')
    def toString(self):return self._label


class _Mode(Enum):
    def __init__(self):raise TypeError('VertexFormat.Mode is an enum')
    def indexCount(self,count):
        count=Int32.wrap(count)
        return Int32.multiply(Int32.divide(count,4),6) if self in (_Mode.LINES,_Mode.QUADS) else count


class _IndexType(Enum):
    def __init__(self):raise TypeError('VertexFormat.IndexType is an enum')
    @staticmethod
    def least(count):return _IndexType.INT if Int32.bitAnd(count,-65536) else _IndexType.SHORT


def _values(cls,rows):
    values=[]
    for index,(name,attributes) in enumerate(rows):
        value=object.__new__(cls);value._name=JavaString(name);value._ordinal=index
        for key,item in attributes.items():setattr(value,key,item)
        setattr(cls,name,value);values.append(value)
    cls._values=tuple(values)
_values(_Type,[(n,dict(_size=s,_label=JavaString(label),_gl_type=gl)) for n,s,label,gl in (
    ('FLOAT',4,'Float',5126),('UBYTE',1,'Unsigned Byte',5121),('BYTE',1,'Byte',5120),('USHORT',2,'Unsigned Short',5123),('SHORT',2,'Short',5122),('UINT',4,'Unsigned Int',5125),('INT',4,'Int',5124))])
_values(_Usage,[(n,dict(_label=JavaString(label))) for n,label in (('POSITION','Position'),('NORMAL','Normal'),('COLOR','Vertex Color'),('UV','UV'),('GENERIC','Generic'))])
_values(_Mode,[(n,dict(asGLMode=gl,primitiveLength=length,primitiveStride=stride,connectedPrimitives=connected)) for n,gl,length,stride,connected in (
    ('LINES',4,2,2,False),('LINE_STRIP',5,2,1,True),('DEBUG_LINES',1,2,2,False),('DEBUG_LINE_STRIP',3,2,1,True),('TRIANGLES',4,3,3,False),('TRIANGLE_STRIP',5,3,1,True),('TRIANGLE_FAN',6,3,1,True),('QUADS',4,4,4,False))])
_values(_IndexType,[('SHORT',dict(asGLType=5123,bytes=2)),('INT',dict(asGLType=5125,bytes=4))])


class VertexFormatElement(object):
    __slots__=('_id','_index','_type','_usage','_count')
    MAX_COUNT=32
    Type=_Type;Usage=_Usage
    def __init__(self,identity,index,kind,usage,count):
        identity=Int32.wrap(identity);index=Int32.wrap(index)
        if identity<0 or identity>=32:raise IllegalArgumentException('Vertex element ID outside 0..31')
        if index!=0 and usage is not _Usage.UV:raise IllegalStateException('Multiple non-UV vertex elements are unsupported')
        for name,value in (('_id',identity),('_index',index),('_type',kind),('_usage',usage),('_count',Int32.wrap(count))):object.__setattr__(self,name,value)
    def __setattr__(self,name,value):raise AttributeError('VertexFormatElement record is immutable')
    def id(self):return self._id
    def index(self):return self._index
    def type(self):return self._type
    def usage(self):return self._usage
    def count(self):return self._count
    def mask(self):return Int32.shiftLeft(1,self._id)
    def byteSize(self):return Int32.multiply(_nonnull(self._type).size(),self._count)
    def equals(self,other):return type(other) is VertexFormatElement and self._id==other._id and self._index==other._index and self._type is other._type and self._usage is other._usage and self._count==other._count
    def hashCode(self):
        value=Int32.add(Int32.multiply(self._id,31),self._index)
        for part in (0 if self._type is None else self._type.hashCode(),0 if self._usage is None else self._usage.hashCode(),self._count):value=Int32.add(Int32.multiply(value,31),part)
        return value
    def toString(self):return JavaString('%s,%s,%s (%s)'%(self._count,'null' if self._usage is None else self._usage.toString(),'null' if self._type is None else self._type.toString(),self._id))
    @staticmethod
    def byId(identity):
        if identity<0 or identity>=32:raise ArrayIndexOutOfBoundsException()
        return _BY_ID[identity]
    @staticmethod
    def register(*args):raise UnsupportedOperationException('Dynamic vertex registry ownership is not reviewed')
    @staticmethod
    def elementsFromMask(mask):raise UnsupportedOperationException('Stream adapter is not reviewed')
    def setupBufferState(self,*args):raise UnsupportedOperationException('GPU vertex state is not implemented')


_BY_ID=[None]*32
for _name,_identity,_index,_type,_usage,_count in (
        ('POSITION',0,0,_Type.FLOAT,_Usage.POSITION,3),('COLOR',1,0,_Type.UBYTE,_Usage.COLOR,4),('UV0',2,0,_Type.FLOAT,_Usage.UV,2),('UV1',3,1,_Type.SHORT,_Usage.UV,2),('UV2',4,2,_Type.SHORT,_Usage.UV,2),('NORMAL',5,0,_Type.BYTE,_Usage.NORMAL,3)):
    _element=VertexFormatElement(_identity,_index,_type,_usage,_count);_BY_ID[_identity]=_element;setattr(VertexFormatElement,_name,_element)
VertexFormatElement.UV=VertexFormatElement.UV0


class _Builder(object):
    def __init__(self):self._entries=[];self._offset=0
    def add(self,name,element):
        _nonnull(name);_nonnull(element)
        self._entries.append((JavaString(name),element,self._offset));self._offset=Int32.add(self._offset,element.byteSize())
        return self
    def padding(self,count):self._offset=Int32.add(self._offset,count);return self
    def build(self):
        names=[row[0] for row in self._entries]
        if len(set(names))!=len(names):raise IllegalArgumentException('Duplicate vertex attribute name')
        return VertexFormat(self._entries,self._offset,_CONSTRUCTION_KEY)


_CONSTRUCTION_KEY=object()
class VertexFormat(object):
    UNKNOWN_ELEMENT=-1
    Builder=_Builder;Mode=_Mode;IndexType=_IndexType
    def __init__(self,entries=None,size=0,key=None):
        if key is not _CONSTRUCTION_KEY:raise TypeError('VertexFormat requires builder()')
        self._elements=ImmutableList([row[1] for row in entries]);self._names=ImmutableList([row[0] for row in entries]);self._size=Int32.wrap(size);self._mask=0
        for name,element,offset in entries:self._mask=Int32.bitOr(self._mask,element.mask())
        offsets=[]
        for builtin in _BY_ID:
            offsets.append(next((offset for name,element,offset in entries if builtin is not None and builtin.equals(element)),-1))
        self._offsets=JavaArray('int',1,offsets)
    @staticmethod
    def builder():return _Builder()
    def getVertexSize(self):return self._size
    def getElements(self):return self._elements
    def getElementAttributeNames(self):return self._names
    def getOffsetsByElement(self):return self._offsets
    def getOffset(self,element):return self._offsets[_nonnull(element).id()]
    def contains(self,element):return bool(Int32.bitAnd(self._mask,_nonnull(element).mask()))
    def getElementsMask(self):return self._mask
    def getElementName(self,element):
        for index,known in enumerate(self._elements):
            if known.equals(element):return self._names.get(index)
        raise IllegalArgumentException('Vertex element is absent')
    def equals(self,other):return isinstance(other,VertexFormat) and self._mask==other._mask and self._size==other._size and list(self._names)==list(other._names) and list(self._offsets)==list(other._offsets)
    def hashCode(self):
        value=1
        for offset in self._offsets:value=Int32.add(Int32.multiply(value,31),offset)
        return Int32.add(Int32.multiply(self._mask,31),value)
    def toString(self):
        text='Vertex format (%s bytes):\n'%self._size
        for index,element in enumerate(self._elements):text+='%s. %s: %s @ %s\n'%(index,self._names.get(index),element.toString(),self.getOffset(element))
        return JavaString(text)
    def setupBufferState(self):raise UnsupportedOperationException('GPU vertex state is not implemented')
    def clearBufferState(self):raise UnsupportedOperationException('GPU vertex state is not implemented')
    def getImmediateDrawVertexBuffer(self):raise UnsupportedOperationException('GPU vertex buffer is not implemented')


# Layouts transcribed from the pinned 1.21.1 DefaultVertexFormat initializer.
DEFAULT_LAYOUTS = (
 ('BLIT_SCREEN',('Position',)),
 ('BLOCK',('Position','Color','UV0','UV2','Normal',1)),
 ('NEW_ENTITY',('Position','Color','UV0','UV1','UV2','Normal',1)),
 ('PARTICLE',('Position','UV0','Color','UV2')),
 ('POSITION',('Position',)),('POSITION_COLOR',('Position','Color')),
 ('POSITION_COLOR_NORMAL',('Position','Color','Normal',1)),
 ('POSITION_COLOR_LIGHTMAP',('Position','Color','UV2')),
 ('POSITION_TEX',('Position','UV0')),('POSITION_TEX_COLOR',('Position','UV0','Color')),
 ('POSITION_COLOR_TEX_LIGHTMAP',('Position','Color','UV0','UV2')),
 ('POSITION_TEX_LIGHTMAP_COLOR',('Position','UV0','UV2','Color')),
 ('POSITION_TEX_COLOR_NORMAL',('Position','UV0','Color','Normal',1)))
class DefaultVertexFormat(object):
    # Legacy Python helpers only; not exported as Java method signatures.
    @staticmethod
    def of(name):
        if name not in [row[0] for row in DEFAULT_LAYOUTS]:raise IllegalArgumentException('Unknown predefined vertex format')
        return getattr(DefaultVertexFormat,name)
    @staticmethod
    def clear():return None
for _name,_layout in DEFAULT_LAYOUTS:
    _builder=VertexFormat.builder()
    for _part in _layout:
        if isinstance(_part,int):_builder.padding(_part)
        else:_builder.add(_part,getattr(VertexFormatElement,{'Position':'POSITION','Color':'COLOR','Normal':'NORMAL'}.get(_part,_part)))
    setattr(DefaultVertexFormat,_name,_builder.build())

JAVA_MAP = {'com.mojang.blaze3d.vertex.DefaultVertexFormat':DefaultVertexFormat,'com.mojang.blaze3d.vertex.VertexFormat':VertexFormat,'com.mojang.blaze3d.vertex.VertexFormat$Builder':_Builder,'com.mojang.blaze3d.vertex.VertexFormat$Mode':_Mode,'com.mojang.blaze3d.vertex.VertexFormat$IndexType':_IndexType,'com.mojang.blaze3d.vertex.VertexFormatElement':VertexFormatElement,'com.mojang.blaze3d.vertex.VertexFormatElement$Type':_Type,'com.mojang.blaze3d.vertex.VertexFormatElement$Usage':_Usage}
