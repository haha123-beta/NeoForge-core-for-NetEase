# -*- coding: utf-8 -*-
"""Reviewed Minecraft 1.21.1 inactive profiler and interface defaults.

Inactive methods deliberately do nothing in vanilla. ActiveProfiler's timing,
sampling and file output are not replaced by fabricated results.
"""
from __future__ import absolute_import
from java_stdlib.lang import JavaString, NullPointerException, Enum
from java_stdlib._base import JavaCollection, JavaIterator, MISSING, NoSuchElementException, UnsupportedOperationException
from java_stdlib.util import JavaSet, Collections
from java_stdlib.java_arrays import JavaArrays
from java_stdlib.primitives import Int32

PREFIX='net.minecraft.util.profiling.'

def _require(value):
    if value is None:raise NullPointerException()
    return value

class _EmptyIterator(JavaIterator):
    _nc_JavaCollectionsABI=1
    def __init__(self):JavaIterator.__init__(self,[])
    def next(self):raise NoSuchElementException()
    def remove(self):raise UnsupportedOperationException('Immutable set iterator')

class _ImmutableEmptySet(JavaSet):
    _nc_JavaCollectionsABI=3
    def __init__(self):self._data={}
    def size(self):return 0
    def contains(self,value):return False
    def _iter_raw(self):return []
    def _immutable(self,*args):raise UnsupportedOperationException('Immutable profiler chart set')
    add=addAll=remove=removeAll=retainAll=removeIf=clear=_immutable
    def iterator(self):return _EmptyIterator()
    def toArray(self,destination=MISSING):return JavaCollection.toArray(self,destination)

_EMPTY_CHARTS=_ImmutableEmptySet()

class ProfilerFiller(object):
    _nc_ProfilersABI=1
    ROOT=JavaString('root')
    def _abstract(self,*args):raise UnsupportedOperationException('Abstract ProfilerFiller method requires an implementation')
    startTick=endTick=push=pop=popPush=markForCharting=_abstract
    def incrementCounter(self,name,count=MISSING):
        if count is MISSING:return self.incrementCounter(name,1)
        raise UnsupportedOperationException('Abstract ProfilerFiller.incrementCounter requires an implementation')
    @staticmethod
    def tee(first,second):
        if first is InactiveProfiler.INSTANCE:return second
        if second is InactiveProfiler.INSTANCE:return first
        return _TeeProfiler(first,second)

class _TeeProfiler(ProfilerFiller):
    def __init__(self,first,second):self.first,self.second=first,second
    def _both(self,name,*args):
        getattr(_require(self.first),name)(*args)
        getattr(_require(self.second),name)(*args)
    def startTick(self):self._both('startTick')
    def endTick(self):self._both('endTick')
    def push(self,label):self._both('push',label)
    def pop(self):self._both('pop')
    def popPush(self,label):self._both('popPush',label)
    def markForCharting(self,category):self._both('markForCharting',category)
    def incrementCounter(self,label,count=MISSING):
        self._both('incrementCounter',label,1 if count is MISSING else count)

class ProfileCollector(ProfilerFiller):
    getResults=getEntry=getChartedPaths=ProfilerFiller._abstract

class ProfileResults(object):
    _nc_ProfilersABI=1
    PATH_SEPARATOR=JavaString('\x1e')
    def _abstract(self,*args):raise UnsupportedOperationException('Abstract ProfileResults method requires an implementation')
    getTimes=saveResults=getStartTimeNano=getStartTimeTicks=getEndTimeNano=getEndTimeTicks=getProfilerResults=_abstract
    def getNanoDuration(self):
        value=self.getEndTimeNano()-self.getStartTimeNano()
        return ((value+9223372036854775808)%18446744073709551616)-9223372036854775808
    def getTickDuration(self):return Int32.subtract(self.getEndTimeTicks(),self.getStartTimeTicks())
    @staticmethod
    def demanglePath(path):return JavaString(_require(path).replace('\x1e','.'))

class EmptyProfileResults(ProfileResults):
    def __init__(self):raise UnsupportedOperationException('EmptyProfileResults constructor is private')
    def getTimes(self,path):return Collections.emptyList()
    def saveResults(self,path):return False
    def getStartTimeNano(self):return 0
    def getEndTimeNano(self):return 0
    def getStartTimeTicks(self):return 0
    def getEndTimeTicks(self):return 0
    def getProfilerResults(self):return JavaString('')

EmptyProfileResults.EMPTY=object.__new__(EmptyProfileResults)

class InactiveProfiler(ProfileCollector):
    def __init__(self):raise UnsupportedOperationException('InactiveProfiler constructor is private')
    def _inactive(self,*args):return None
    startTick=endTick=push=pop=popPush=markForCharting=incrementCounter=_inactive
    def getResults(self):return EmptyProfileResults.EMPTY
    def getEntry(self,path):return None
    def getChartedPaths(self):return _EMPTY_CHARTS

InactiveProfiler.INSTANCE=object.__new__(InactiveProfiler)

class MetricCategory(Enum):
    @classmethod
    def values(cls):return JavaArrays.initialized(PREFIX+'metrics.MetricCategory',1,cls._values,cls)
    def getDescription(self):return self._description

_categories=[]
for _ordinal,(_name,_description) in enumerate((('PATH_FINDING','pathfinding'),('EVENT_LOOPS','event-loops'),
    ('MAIL_BOXES','mailboxes'),('TICK_LOOP','ticking'),('JVM','jvm'),('CHUNK_RENDERING','chunk rendering'),
    ('CHUNK_RENDERING_DISPATCHING','chunk rendering dispatching'),('CPU','cpu'),('GPU','gpu'))):
    _category=MetricCategory();_category._name,_category._ordinal=_name,_ordinal
    _category._description=JavaString(_description);setattr(MetricCategory,_name,_category);_categories.append(_category)
MetricCategory._values=tuple(_categories)

class Profilers(object):
    ABI_VERSION=1
    @staticmethod
    def require(value):
        value=_require(value)
        if not isinstance(value,(ProfilerFiller,ProfileResults)) or getattr(value,'_nc_ProfilersABI',0)<1:
            raise UnsupportedOperationException('Profiler adapter ABI1 required')
        return value
    @staticmethod
    def field(java_name,target,name):
        classes={PREFIX+'ProfilerFiller':ProfilerFiller,PREFIX+'ProfileCollector':ProfileCollector,PREFIX+'InactiveProfiler':InactiveProfiler,
                 PREFIX+'EmptyProfileResults':EmptyProfileResults,PREFIX+'ProfileResults':ProfileResults}
        allowed={(PREFIX+'ProfilerFiller','ROOT'),(PREFIX+'InactiveProfiler','INSTANCE'),
                 (PREFIX+'EmptyProfileResults','EMPTY'),(PREFIX+'ProfileResults','PATH_SEPARATOR')}
        allowed.update((PREFIX+name,'ROOT') for name in ('ProfileCollector','InactiveProfiler'))
        allowed.add((PREFIX+'EmptyProfileResults','PATH_SEPARATOR'))
        if (java_name,name) not in allowed or classes.get(java_name) is not target:
            raise UnsupportedOperationException('Unreviewed profiler static field')
        return getattr(target,name)
    @staticmethod
    def invoke(value,name,signature,args):
        value=Profilers.require(value)
        if name=='incrementCounter' and len(signature)==1:
            return value.incrementCounter(args[0],1)
        return getattr(value,name)(*args)

JAVA_MAP={PREFIX+'ProfilerFiller':ProfilerFiller,PREFIX+'ProfileCollector':ProfileCollector,
          PREFIX+'InactiveProfiler':InactiveProfiler,PREFIX+'ProfileResults':ProfileResults,
          PREFIX+'EmptyProfileResults':EmptyProfileResults,PREFIX+'metrics.MetricCategory':MetricCategory,
          'neocore.runtime.Profilers':Profilers}
