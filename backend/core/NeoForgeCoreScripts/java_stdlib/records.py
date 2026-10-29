# -*- coding: utf-8 -*-
"""Reviewed record value semantics. Components keep raw storage, never accessor results."""
from __future__ import absolute_import
from java_stdlib.lang import JavaString, System, UnsupportedOperationException
from java_stdlib.primitives import Int32
from java_stdlib.java_arrays import JavaArray

class RecordBase(object):
    def __init__(self):raise TypeError('java.lang.Record is abstract')
    def __setattr__(self,name,value):
        if getattr(self,'_nc_record_sealed',False) and (name=='_nc_record_sealed' or any(name in (n,s) for n,t,s in self._nc_RecordComponents)):
            raise AttributeError('Record components are final')
        object.__setattr__(self,name,value)
    def __delattr__(self,name):
        if name=='_nc_record_sealed' or any(name in (n,s) for n,t,s in self._nc_RecordComponents):raise AttributeError('Record components are final')
        object.__delattr__(self,name)
    def __eq__(self,other):return self.equals(other)
    def __ne__(self,other):return not self.equals(other)
    def __hash__(self):return self.hashCode()
    def __str__(self):return self.toString().encode('utf-8') if str is bytes else self.toString()
    def __unicode__(self):return self.toString()

class JavaRecords(object):
    ABI_VERSION=1
    Base=RecordBase
    @staticmethod
    def narrow(kind,value):
        bits={'byte':8,'short':16,'int':32,'long':64}[kind]
        result=int(value)&((1<<bits)-1)
        return result-(1<<bits) if result&(1<<(bits-1)) else result
    @staticmethod
    def arguments(instance,values):
        if len(values)!=len(instance._nc_RecordComponents):raise TypeError('Record constructor arity mismatch')
        return tuple(JavaRecords.narrow(kind,value) if kind in ('byte','short','int','long') else JavaString(value) if kind=='java.lang.String' and value is not None else value for (name,kind,storage),value in zip(instance._nc_RecordComponents,values))
    @staticmethod
    def equals(value,other):
        if value is other:return True
        if type(value) is not type(other):return False
        for name,kind,storage in value._nc_RecordComponents:
            left,right=getattr(value,storage),getattr(other,storage)
            if kind in ('byte','short','int','long','boolean'):
                if left!=right:return False
            elif left is not right:
                if isinstance(left,(str,type(u''))) and isinstance(right,(str,type(u''))):
                    if not JavaString(left).equals(right):return False
                    continue
                if left is None or not hasattr(left,'equals') or not left.equals(right):return False
        return True
    @staticmethod
    def hashCode(value):
        result=0
        for name,kind,storage in value._nc_RecordComponents:
            item=getattr(value,storage)
            if item is None:part=0
            elif kind=='boolean':part=1231 if item else 1237
            elif kind in ('byte','short','int'):part=Int32.wrap(item)
            elif kind=='long':part=Int32.wrap(item^(item>>32))
            elif isinstance(item,(str,type(u''))):part=JavaString(item).hashCode()
            elif hasattr(item,'hashCode'):part=item.hashCode()
            else:part=System.identityHashCode(item)
            result=Int32.add(Int32.multiply(result,31),part)
        return result
    @staticmethod
    def toString(value):
        parts=[]
        for name,kind,storage in value._nc_RecordComponents:
            item=getattr(value,storage)
            if item is None:text=u'null'
            elif kind=='boolean':text=u'true' if item else u'false'
            elif kind in ('byte','short','int','long'):text=str(item)
            elif isinstance(item,(str,type(u''))):text=JavaString(item)
            elif hasattr(item,'toString'):text=item.toString()
            elif isinstance(item,JavaArray):
                kinds={'int':'I','boolean':'Z','byte':'B','short':'S','long':'J','char':'C','float':'F','double':'D'}
                descriptor='['*item.rank+kinds.get(item.component,'L'+item.component+';')
                text=descriptor+'@'+format(System.identityHashCode(item)&0xffffffff,'x')
            else:
                identity=getattr(item,'_nc_JavaName',None)
                if type(item) is object:identity='java.lang.Object'
                if identity is None:raise UnsupportedOperationException('Record reference toString requires a reviewed Java identity')
                text=identity+'@'+format(System.identityHashCode(item)&0xffffffff,'x')
            parts.append(name+u'='+text)
        return JavaString(value._nc_JavaName.rsplit('.',1)[-1]+u'['+u', '.join(parts)+u']')

JAVA_MAP={'java.lang.Record':RecordBase,'neocore.runtime.JavaRecords':JavaRecords}
