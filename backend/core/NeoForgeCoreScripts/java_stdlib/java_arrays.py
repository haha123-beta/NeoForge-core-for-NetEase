# -*- coding: utf-8 -*-
"""Fixed-size, reified Java arrays. Helpers retain Java evaluation/check order."""
from __future__ import absolute_import
import struct
from java_stdlib.lang import RuntimeException, NullPointerException, ArrayIndexOutOfBoundsException, IllegalArgumentException, ClassCastException, UnsupportedOperationException
from java_stdlib.primitives import Int32
from java_stdlib.type_relations import PARENTS


try:
    _character = unichr
except NameError:
    _character = chr


class NegativeArraySizeException(RuntimeException):
    pass


class ArrayStoreException(RuntimeException):
    pass


class JavaArray(object):
    def __init__(self, component, rank, values, reference_type=None):
        self.component, self.rank = component, int(rank)
        self.reference_type = reference_type
        self._values = list(values)
    def __len__(self):
        return len(self._values)
    def __iter__(self):
        # Java enhanced-for over an array sees later element writes, not a snapshot.
        for index in range(len(self._values)):
            yield self._values[index]
    def __getitem__(self, index):
        return JavaArrays.get(self,index)
    def __setitem__(self,index,value):
        JavaArrays.set(self,index,value)
    def clone(self):
        return JavaArray(self.component,self.rank,self._values,self.reference_type)


class JavaArrays(object):
    ABI_VERSION = 3
    PRIMITIVES = ('boolean','byte','short','char','int','long','float','double')
    @staticmethod
    def cast(value,component,rank,reference_type=None):
        if value is None:return None
        if not isinstance(value,JavaArray):raise ClassCastException('Reference is not a Java array')
        rank=int(rank)
        if rank<1:raise TypeError('Invalid array cast rank')
        if value.rank>rank:
            if component in ('java.lang.Object','java.lang.Cloneable','java.io.Serializable'):return value
            raise ClassCastException('Incompatible array rank')
        if value.rank!=rank:raise ClassCastException('Incompatible array rank')
        if value.component==component:return value
        if value.component in JavaArrays.PRIMITIVES or component in JavaArrays.PRIMITIVES:
            raise ClassCastException('Incompatible primitive array')
        if component=='java.lang.Object':return value
        if value.component in PARENTS:
            pending=[value.component];visited=set()
            while pending:
                identity=pending.pop()
                if identity==component:return value
                if identity in visited:continue
                visited.add(identity);pending.extend(PARENTS.get(identity,[]))
            raise ClassCastException('Incompatible declared array component')
        if value.reference_type is not None and reference_type is not None:
            if value.reference_type is reference_type:
                raise UnsupportedOperationException('Unreviewed array component aliases')
            if issubclass(value.reference_type,reference_type):return value
        raise ClassCastException('Incompatible reference array component')
    @staticmethod
    def _array(value):
        if value is None:
            raise NullPointerException("Array reference is null")
        if not isinstance(value,JavaArray):
            raise TypeError("Expected JavaArray")
        return value
    @staticmethod
    def length(array):
        return len(JavaArrays._array(array))
    @staticmethod
    def _index(array,index):
        index=int(index)
        if index<0 or index>=len(array):
            raise ArrayIndexOutOfBoundsException("Array index out of bounds: "+str(index))
        return index
    @staticmethod
    def get(array,index):
        array=JavaArrays._array(array)
        return array._values[JavaArrays._index(array,index)]
    @staticmethod
    def _convert(array,value):
        if array.rank>1:
            if value is None:return None
            if not isinstance(value,JavaArray) or value.rank!=array.rank-1:
                raise ArrayStoreException("Incompatible subarray")
            if array.component in JavaArrays.PRIMITIVES or value.component in JavaArrays.PRIMITIVES:
                if value.component!=array.component:raise ArrayStoreException("Incompatible primitive subarray")
            elif array.component!='java.lang.Object' and array.reference_type is not None:
                try:JavaArrays.cast(value,array.component,array.rank-1,array.reference_type)
                except ClassCastException:raise ArrayStoreException("Incompatible reference subarray")
            return value
        kind=array.component
        if kind not in JavaArrays.PRIMITIVES:
            if value is not None and array.reference_type is not None:
                from java_stdlib._boxing import cast_reference
                try:cast_reference(value,array.reference_type)
                except ClassCastException:raise ArrayStoreException("Incompatible reference element")
            return value
        if kind=='boolean':
            if not isinstance(value,bool):raise TypeError("Expected boolean element")
            return value
        if value is None:raise NullPointerException("Primitive array element is null")
        if kind=='int':return Int32.wrap(value)
        if kind in ('byte','short','long'):
            width={'byte':8,'short':16,'long':64}[kind]
            return (int(value)+(1<<(width-1)))%(1<<width)-(1<<(width-1))
        if kind=='char':
            return value if isinstance(value,(str,type(u""))) and len(value)==1 else _character(int(value)&65535)
        if kind=='float':
            from java_stdlib.function import Functional
            return Functional.float32(value)
        return float(value)
    @staticmethod
    def set(array,index,value):
        # Caller evaluates array/index/RHS before this check for simple assignment.
        array=JavaArrays._array(array);index=JavaArrays._index(array,index)
        array._values[index]=JavaArrays._convert(array,value)
        return value
    @staticmethod
    def create(component,dimensions,reference_type=None):
        dimensions=tuple(dimensions)
        if not dimensions or dimensions[0] is None:raise TypeError("Missing allocated array dimension")
        for size in dimensions:
            if size is not None and int(size)<0:raise NegativeArraySizeException(str(size))
        def allocate(depth):
            size=dimensions[depth]
            if size is None:return None
            remaining=len(dimensions)-depth
            if remaining>1:
                values=[allocate(depth+1) for index in range(int(size))]
            else:
                default=False if component=='boolean' else u'\x00' if component=='char' else 0.0 if component in ('float','double') else 0 if component in JavaArrays.PRIMITIVES else None
                values=[default for index in range(int(size))]
            return JavaArray(component,remaining,values,reference_type)
        return allocate(0)
    @staticmethod
    def initialized(component,rank,values,reference_type=None):
        array=JavaArray(component,rank,[],reference_type)
        for value in values:array._values.append(JavaArrays._convert(array,value))
        return array
    @staticmethod
    def copy(array,length):
        array=JavaArrays._array(array)
        result=JavaArrays.create(array.component,(int(length),)+(None,)*(array.rank-1),array.reference_type)
        for index in range(min(len(array),int(length))):result._values[index]=array._values[index]
        return result
    @staticmethod
    def copyRange(array,start,end):
        array=JavaArrays._array(array);start,end=int(start),int(end)
        if end<start:raise IllegalArgumentException("Array range end precedes start")
        if start<0 or start>len(array):raise ArrayIndexOutOfBoundsException("Array range start invalid")
        result=JavaArrays.create(array.component,(end-start,)+(None,)*(array.rank-1),array.reference_type)
        result._values[:]=[JavaArrays.get(array,start+i) if start+i<len(array) else result._values[i] for i in range(end-start)]
        return result
    @staticmethod
    def arraycopy(source,source_pos,destination,dest_pos,length):
        if source is None or destination is None:
            raise NullPointerException("Array copy operand is null")
        if not isinstance(source,JavaArray) or not isinstance(destination,JavaArray):
            raise ArrayStoreException("Array copy operand is not an array")
        source_pos,dest_pos,length=int(source_pos),int(dest_pos),int(length)
        source_primitive=source.rank==1 and source.component in JavaArrays.PRIMITIVES
        dest_primitive=destination.rank==1 and destination.component in JavaArrays.PRIMITIVES
        if source_primitive or dest_primitive:
            if not (source_primitive and dest_primitive and source.component==destination.component):
                raise ArrayStoreException("Array copy primitive components differ")
        if source_pos<0 or dest_pos<0 or length<0 or source_pos+length>len(source) or dest_pos+length>len(destination):
            raise ArrayIndexOutOfBoundsException("Array copy range invalid")
        values=list(source._values[source_pos:source_pos+length])
        for offset,value in enumerate(values):JavaArrays.set(destination,dest_pos+offset,value)
    @staticmethod
    def iterate(value):
        if value is None:raise NullPointerException("Iteration target is null")
        iterator=getattr(value,'iterator',None)
        if callable(iterator):
            current=iterator()
            while current.hasNext():yield current.next()
        else:
            for item in value:yield item


JAVA_MAP={'neocore.runtime.JavaArrays':JavaArrays,
          'java.lang.NegativeArraySizeException':NegativeArraySizeException,
          'java.lang.ArrayStoreException':ArrayStoreException}
