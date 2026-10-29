# -*- coding: utf-8 -*-
"""Minecraft 1.21.1 GUI navigation geometry. No screen or drawing implementation."""
from __future__ import absolute_import
from java_stdlib.lang import Enum, JavaString, NullPointerException, UnsupportedOperationException
from java_stdlib.primitives import Int32


class ScreenAxis(Enum):
    def __init__(self):raise TypeError('ScreenAxis is an enum')
    def orthogonal(self):return ScreenAxis.VERTICAL if self is ScreenAxis.HORIZONTAL else ScreenAxis.HORIZONTAL
    def getPositive(self):return ScreenDirection.RIGHT if self is ScreenAxis.HORIZONTAL else ScreenDirection.DOWN
    def getNegative(self):return ScreenDirection.LEFT if self is ScreenAxis.HORIZONTAL else ScreenDirection.UP
    def getDirection(self,positive):return self.getPositive() if positive else self.getNegative()


class ScreenDirection(Enum):
    def __init__(self):raise TypeError('ScreenDirection is an enum')
    def getAxis(self):return ScreenAxis.VERTICAL if self in (ScreenDirection.UP,ScreenDirection.DOWN) else ScreenAxis.HORIZONTAL
    def getOpposite(self):return (ScreenDirection.DOWN,ScreenDirection.UP,ScreenDirection.RIGHT,ScreenDirection.LEFT)[self.ordinal()]
    def isPositive(self):return self in (ScreenDirection.DOWN,ScreenDirection.RIGHT)
    def isAfter(self,left,right):return left>right if self.isPositive() else left<right
    def isBefore(self,left,right):return left<right if self.isPositive() else left>right
    def coordinateValueComparator(self):raise UnsupportedOperationException('IntComparator adapter is not reviewed')


def _enum(cls,names):
    values=[]
    for index,name in enumerate(names):
        value=object.__new__(cls);value._name=JavaString(name);value._ordinal=index
        setattr(cls,name,value);values.append(value)
    cls._values=tuple(values)
_enum(ScreenAxis,('HORIZONTAL','VERTICAL'))
_enum(ScreenDirection,('UP','DOWN','LEFT','RIGHT'))


def _not_null(value):
    if value is None:raise NullPointerException()
    return value


class ScreenPosition(object):
    __slots__=('_x','_y')
    def __init__(self,x,y):
        object.__setattr__(self,'_x',Int32.wrap(x));object.__setattr__(self,'_y',Int32.wrap(y))
    def __setattr__(self,name,value):raise AttributeError('ScreenPosition record is immutable')
    def x(self):return self._x
    def y(self):return self._y
    @staticmethod
    def of(axis,primary,secondary):return ScreenPosition(primary,secondary) if _not_null(axis) is ScreenAxis.HORIZONTAL else ScreenPosition(secondary,primary)
    def step(self,direction):
        axis=_not_null(direction).getAxis();delta=1 if direction.isPositive() else -1
        return ScreenPosition(Int32.add(self._x,delta) if axis is ScreenAxis.HORIZONTAL else self._x,Int32.add(self._y,delta) if axis is ScreenAxis.VERTICAL else self._y)
    def getCoordinate(self,axis):return self._x if _not_null(axis) is ScreenAxis.HORIZONTAL else self._y
    def equals(self,other):return type(other) is ScreenPosition and self._x==other._x and self._y==other._y
    def hashCode(self):return Int32.add(Int32.multiply(self._x,31),self._y)
    def toString(self):return JavaString('ScreenPosition[x=%s, y=%s]'%(self._x,self._y))


class ScreenRectangle(object):
    __slots__=('_position','_width','_height')
    def __init__(self,*args):
        if len(args)==4:position=ScreenPosition(args[0],args[1]);width,height=args[2:]
        elif len(args)==3:position,width,height=args
        else:raise TypeError('ScreenRectangle requires four ints or ScreenPosition and two ints')
        object.__setattr__(self,'_position',position);object.__setattr__(self,'_width',Int32.wrap(width));object.__setattr__(self,'_height',Int32.wrap(height))
    def __setattr__(self,name,value):raise AttributeError('ScreenRectangle record is immutable')
    def position(self):return self._position
    def width(self):return self._width
    def height(self):return self._height
    @staticmethod
    def empty():return _EMPTY
    @staticmethod
    def of(axis,primary,secondary,length,other_length):
        if _not_null(axis) is ScreenAxis.HORIZONTAL:return ScreenRectangle(primary,secondary,length,other_length)
        return ScreenRectangle(secondary,primary,other_length,length)
    def step(self,direction):return ScreenRectangle(_not_null(self._position).step(direction),self._width,self._height)
    def getLength(self,axis):return self._width if _not_null(axis) is ScreenAxis.HORIZONTAL else self._height
    def getBoundInDirection(self,direction):
        axis=_not_null(direction).getAxis();value=_not_null(self._position).getCoordinate(axis)
        return Int32.subtract(Int32.add(value,self.getLength(axis)),1) if direction.isPositive() else value
    def getBorder(self,direction):
        axis=_not_null(direction).getAxis();orthogonal=axis.orthogonal()
        return ScreenRectangle.of(axis,self.getBoundInDirection(direction),self.getBoundInDirection(orthogonal.getNegative()),1,self.getLength(orthogonal)).step(direction)
    def overlapsInAxis(self,other,axis):
        negative=_not_null(axis).getNegative();positive=axis.getPositive();_not_null(other)
        return max(self.getBoundInDirection(negative),other.getBoundInDirection(negative))<=min(self.getBoundInDirection(positive),other.getBoundInDirection(positive))
    def overlaps(self,other):return self.overlapsInAxis(other,ScreenAxis.HORIZONTAL) and self.overlapsInAxis(other,ScreenAxis.VERTICAL)
    def getCenterInAxis(self,axis):
        value=Int32.add(self.getBoundInDirection(_not_null(axis).getPositive()),self.getBoundInDirection(axis.getNegative()))
        return Int32.divide(value,2)
    def left(self):return _not_null(self._position).x()
    def top(self):return _not_null(self._position).y()
    def right(self):return Int32.add(self.left(),self._width)
    def bottom(self):return Int32.add(self.top(),self._height)
    def containsPoint(self,x,y):return self.left()<=x<self.right() and self.top()<=y<self.bottom()
    def intersection(self,other):
        _not_null(other);left=max(self.left(),other.left());top=max(self.top(),other.top());right=min(self.right(),other.right());bottom=min(self.bottom(),other.bottom())
        return ScreenRectangle(left,top,Int32.subtract(right,left),Int32.subtract(bottom,top)) if left<right and top<bottom else None
    def equals(self,other):return type(other) is ScreenRectangle and (self._position is other._position or self._position is not None and self._position.equals(other._position)) and self._width==other._width and self._height==other._height
    def hashCode(self):return Int32.add(Int32.multiply(Int32.add(Int32.multiply(0 if self._position is None else self._position.hashCode(),31),self._width),31),self._height)
    def toString(self):return JavaString('ScreenRectangle[position=%s, width=%s, height=%s]'%('null' if self._position is None else self._position.toString(),self._width,self._height))


_EMPTY=ScreenRectangle(0,0,0,0)
JAVA_MAP = {'net.minecraft.client.gui.navigation.ScreenAxis':ScreenAxis,'net.minecraft.client.gui.navigation.ScreenDirection':ScreenDirection,'net.minecraft.client.gui.navigation.ScreenPosition':ScreenPosition,'net.minecraft.client.gui.navigation.ScreenRectangle':ScreenRectangle}
