# -*- coding: utf-8 -*-
"""Official vertex ordering over float32 position data. Does not submit draw calls."""
from __future__ import absolute_import
from minecraft.model_math import _float
from minecraft.official_interfaces import _declare,method,_invoke
from java_stdlib.lang import NullPointerException
from java_stdlib.java_arrays import JavaArray

class Vector3f(object):
    def __init__(self,*args):
        if not args:values=(0.0,0.0,0.0)
        elif len(args)==1 and isinstance(args[0],Vector3f):values=(args[0].x,args[0].y,args[0].z)
        elif len(args)==1:values=(args[0],)*3
        elif len(args)==3:values=args
        else:raise TypeError('Unreviewed Vector3f constructor')
        self.x,self.y,self.z=values
    def _get_x(self):return self.x
    def _get_y(self):return self.y
    def _get_z(self):return self.z
    def distanceSquared(self,other):
        if other is None:raise NullPointerException()
        dx=_float(self.x-other.x);dy=_float(self.y-other.y);dz=_float(self.z-other.z)
        # Pinned Minecraft JOML defaults USE_MATH_FMA=false. Preserve the original
        # nested float multiply/add order, rather than Python float64 accumulation.
        return _float(_float(dx*dx)+_float(_float(dy*dy)+_float(dz*dz)))
def _axis(name):
    return property(lambda self:getattr(self,'_'+name),lambda self,value:setattr(self,'_'+name,_float(value)))
for _name in ('x','y','z'):setattr(Vector3f,_name,_axis(_name))

INTERFACE_CONTRACTS={}
INTERFACE_TYPES={}
_REGISTRY=(INTERFACE_CONTRACTS,INTERFACE_TYPES)
SORT='com.mojang.blaze3d.vertex.VertexSorting';FUNCTION=SORT+'.DistanceFunction';VECTOR='org.joml.Vector3f'
VertexSorting=_declare(SORT,[method('sort',[VECTOR+'[]'],'int[]')],registry=_REGISTRY)
DistanceFunction=_declare(FUNCTION,[method('apply',[VECTOR],'float')],registry=_REGISTRY)

def _key(value):
    if value!=value:return (2,0.0,0)
    if value==0.0:
        import math
        return (1,0.0,-1 if math.copysign(1.0,value)<0 else 0)
    return (1,value,0)

class _Sorter(VertexSorting):
    def __init__(self,distance):self._distance=distance
    def sort(self,vertices):
        if vertices is None:raise NullPointerException()
        distances=[]
        for vertex in vertices:
            if self._distance is None:raise NullPointerException()
            distances.append(_float(_invoke(self._distance,'apply',(vertex,),(VECTOR,))))
        indices=sorted(range(len(vertices)),key=lambda index:_key(distances[index]),reverse=True)
        return JavaArray('int',1,indices,int)

class _Distance(DistanceFunction):
    def __init__(self,origin):self._origin=origin
    def apply(self,vertex):return self._origin.distanceSquared(vertex)
class _Z(DistanceFunction):
    def apply(self,vertex):
        if vertex is None:raise NullPointerException()
        return -vertex.z

def _by_vector(origin):
    if origin is None:raise NullPointerException()
    return _Sorter(_Distance(origin))
def _by_function(function):return _Sorter(function)
def _by_xyz(x,y,z):return _by_vector(Vector3f(x,y,z))
def _by_distance(*args):
    if len(args)==3:return _by_xyz(*args)
    if len(args)==1 and isinstance(args[0],Vector3f):return _by_vector(args[0])
    if len(args)==1 and (args[0] is None or isinstance(args[0],DistanceFunction)):return _by_function(args[0])
    raise TypeError('Unreviewed VertexSorting.byDistance signature')
VertexSorting.byDistance=staticmethod(_by_distance)
VertexSorting._by_vector=staticmethod(_by_vector)
VertexSorting._by_function=staticmethod(_by_function)
VertexSorting._by_xyz=staticmethod(_by_xyz)
VertexSorting.DistanceFunction=DistanceFunction
VertexSorting.DISTANCE_TO_ORIGIN=_by_xyz(0.0,0.0,0.0)
VertexSorting.ORTHOGRAPHIC_Z=_Sorter(_Z())
INTERFACE_CONTRACTS[SORT]['fields']=[dict(name=n,declared_type=SORT,static=True,final=True,modifiers=['public','static','final'],line=1) for n in ('DISTANCE_TO_ORIGIN','ORTHOGRAPHIC_Z')]
for _contract in INTERFACE_CONTRACTS.values():_contract['helper_abi']=7
JAVA_MAP=dict(INTERFACE_TYPES)
JAVA_MAP['org.joml.Vector3f']=Vector3f
