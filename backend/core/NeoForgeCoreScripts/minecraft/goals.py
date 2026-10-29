# -*- coding: utf-8 -*-
"""Minecraft 1.21.1 Goal/Wrapper/Selector; navigation and Brain are separate."""
from __future__ import absolute_import
from collections import OrderedDict
from java_stdlib._base import IllegalArgumentException, UnsupportedOperationException, JavaIterator, JavaCollection, MISSING
from java_stdlib.lang import NullPointerException, ClassCastException, Enum
from java_stdlib.enum_sets import EnumSet
from java_stdlib.java_arrays import JavaArrays
from java_stdlib.primitives import Int32
from java_stdlib.util import JavaSet
from minecraft.profiling import InactiveProfiler


class Goal(object):
    class Flag(Enum):
        @classmethod
        def values(cls):
            return JavaArrays.initialized('net.minecraft.world.entity.ai.goal.Goal.Flag', 1, cls._values, cls)

    def __init__(self):
        self._flags = EnumSet.noneOf(Goal.Flag)

    def setFlags(self, flags):
        self._flags.clear()
        if flags is None:
            raise NullPointerException()
        self._flags.addAll(flags)

    def getFlags(self):
        return self._flags

    def canUse(self):
        raise UnsupportedOperationException("Abstract Goal.canUse requires a source implementation")

    def canContinueToUse(self):
        return self.canUse()

    def isInterruptable(self):
        return True

    def start(self):
        return None

    def stop(self):
        return None

    def tick(self):
        return None

    def requiresUpdateEveryTick(self):
        return False

    def adjustedTickDelay(self, ticks):
        ticks = Int32.wrap(ticks)
        return ticks if self.requiresUpdateEveryTick() else Goal.reducedTickDelay(ticks)

    @staticmethod
    def reducedTickDelay(ticks):
        # Vanilla Mth.positiveCeilDiv: -Math.floorDiv(-ticks, 2).
        # Both negations are JVM int operations, including MIN_VALUE overflow.
        return Int32.negate(Int32.negate(Int32.wrap(ticks)) // 2)


_flags = []
for _ordinal, _name in enumerate(('MOVE', 'LOOK', 'JUMP', 'TARGET')):
    _flag = Goal.Flag()
    _flag._name, _flag._ordinal = _name, _ordinal
    setattr(Goal.Flag, _name, _flag)
    _flags.append(_flag)
Goal.Flag._values = tuple(_flags)


def _nonnull(value):
    if value is None:raise NullPointerException()
    return value


class WrappedGoal(Goal):
    _nc_GoalSchedulersABI=1
    def __init__(self, priority, goal):
        Goal.__init__(self)
        self._priority = Int32.wrap(priority)
        self._goal = goal
        self._running = False

    def getGoal(self):
        return self._goal

    def getPriority(self):
        return self._priority

    def isRunning(self):
        return self._running

    def start(self):
        if not self._running:
            self._running = True
            _nonnull(self._goal).start()

    def stop(self):
        if self._running:
            self._running = False
            _nonnull(self._goal).stop()

    def canBeReplacedBy(self, other):
        return self.isInterruptable() and _nonnull(other).getPriority() < self.getPriority()

    def canUse(self):return _nonnull(self._goal).canUse()
    def canContinueToUse(self):return _nonnull(self._goal).canContinueToUse()
    def isInterruptable(self):return _nonnull(self._goal).isInterruptable()
    def requiresUpdateEveryTick(self):return _nonnull(self._goal).requiresUpdateEveryTick()
    def adjustedTickDelay(self, ticks):return _nonnull(self._goal).adjustedTickDelay(ticks)
    def tick(self):return _nonnull(self._goal).tick()
    def setFlags(self, flags):return _nonnull(self._goal).setFlags(flags)
    def getFlags(self):return _nonnull(self._goal).getFlags()
    def equals(self, other):
        if self is other:return True
        if type(self) is not type(other):return False
        goal=_nonnull(self._goal)
        return goal.equals(other._goal) if callable(getattr(goal,'equals',None)) else goal is other._goal
    def hashCode(self):
        from java_stdlib.lang import System
        goal=_nonnull(self._goal)
        return goal.hashCode() if callable(getattr(goal,'hashCode',None)) else System.identityHashCode(goal)
    def __eq__(self, other):return self.equals(other)
    def __ne__(self, other):return not self.equals(other)
    def __hash__(self):return self.hashCode()


class _GoalSetIterator(JavaIterator):
    _nc_JavaCollectionsABI=1
    def __init__(self, owner):
        self.owner=owner
        self._next=owner._first
        self._last=None
    def hasNext(self):return self._next is not None
    def next(self):
        from java_stdlib._base import NoSuchElementException
        if not self.hasNext():raise NoSuchElementException()
        node=self._next
        if not node[3]:
            raise UnsupportedOperationException('Goal cursor target was removed externally; fastutil table relocation is not emulated')
        self._last=node;self._next=node[2]
        return node[0]
    def remove(self):
        from java_stdlib._base import IllegalStateException
        if self._last is None:raise IllegalStateException()
        if not self._last[3]:raise UnsupportedOperationException('Goal iterator current entry was removed externally')
        self.owner._remove_identity(self._last[0]);self._last=None


class _GoalSet(JavaSet):
    """Live linked order; unsupported external cursor relocation fails explicitly."""
    _nc_JavaCollectionsABI=3
    def __init__(self):
        self._data=OrderedDict();self._hashes={};self._links={};self._first=self._tail=None
    def size(self):return len(self._data)
    def _iter_raw(self):return list(self)
    def clear(self):
        for node in self._links.values():node[3]=False
        self._data=OrderedDict();self._hashes={};self._links={};self._first=self._tail=None
    def _hash(self,value):
        from java_stdlib.lang import System
        if value is None:return 0
        return value.hashCode() if callable(getattr(value,'hashCode',None)) else System.identityHashCode(value)
    def _find(self,value,digest):
        for key,stored in self._data.items():
            if self._hashes[key]==digest and (value is stored or value is not None and callable(getattr(value,'equals',None)) and value.equals(stored)):
                return key
        return None
    def add(self,value):
        digest=self._hash(value)
        if self._find(value,digest) is not None:return False
        key=id(value);self._data[key]=value;self._hashes[key]=digest
        node=[value,self._tail,None,True];self._links[key]=node
        if self._tail is not None:self._tail[2]=node
        else:self._first=node
        self._tail=node
        return True
    def contains(self,value):return self._find(value,self._hash(value)) is not None
    def remove(self,value):
        key=self._find(value,self._hash(value))
        if key is None:return False
        self._unlink(key)
        return True
    def _remove_identity(self,value):
        key=id(value)
        if key in self._data:self._unlink(key)
    def _unlink(self,key):
        node=self._links.pop(key);node[3]=False
        before,after=node[1],node[2]
        if before is None:self._first=after
        else:before[2]=after
        if after is None:self._tail=before
        else:after[1]=before
        del self._data[key];del self._hashes[key]
    def __iter__(self):return iter(self.iterator())
    def iterator(self):return _GoalSetIterator(self)
    def toArray(self, destination=MISSING):return JavaCollection.toArray(self,destination)


class _NoGoal(WrappedGoal):
    def isRunning(self):return False


class _NeverGoal(Goal):
    def canUse(self):return False


_NO_GOAL=_NoGoal(2147483647,_NeverGoal())


def _wrapped(value):
    value=_nonnull(value)
    if not isinstance(value,WrappedGoal):raise ClassCastException('Expected WrappedGoal')
    return value


class GoalSelector(object):
    _nc_GoalSchedulersABI=1
    def __init__(self, profiler=MISSING):
        # No-arg construction is a NeoCore internal convenience, not a Java signature.
        self._profiler = (lambda:InactiveProfiler.INSTANCE) if profiler is MISSING else profiler
        self._goals = _GoalSet()
        self._disabled = EnumSet.noneOf(Goal.Flag)
        self._locked = {}

    def _profile(self):
        supplier=_nonnull(self._profiler)
        return _nonnull(supplier.get() if callable(getattr(supplier,'get',None)) else supplier())

    def addGoal(self, priority, goal):
        self._goals.add(WrappedGoal(priority, goal))

    def removeAllGoals(self, predicate):
        # Vanilla removes without stopping; null fails only if a goal is visited.
        cursor=self._goals.iterator()
        while cursor.hasNext():
            entry=_wrapped(cursor.next())
            action=_nonnull(predicate)
            if action.test(entry.getGoal()) if callable(getattr(action,'test',None)) else action(entry.getGoal()):
                cursor.remove()

    def removeGoal(self, goal):
        for entry in self._goals:
            entry=_wrapped(entry)
            if entry.getGoal() is goal and entry.isRunning():
                entry.stop()
        cursor=self._goals.iterator()
        while cursor.hasNext():
            if _wrapped(cursor.next()).getGoal() is goal:cursor.remove()

    def getAvailableGoals(self):
        return self._goals

    def getRunningGoals(self):
        return [entry for entry in self._goals if _wrapped(entry).isRunning()]

    def disableControlFlag(self, flag):
        self._disabled.add(flag)

    def enableControlFlag(self, flag):
        self._disabled.remove(flag)

    def setControlFlag(self, flag, enabled):
        if enabled:
            self.enableControlFlag(flag)
        else:
            self.disableControlFlag(flag)

    def stopAll(self):
        for entry in self._goals:
            _wrapped(entry).stop()

    def tick(self):
        profiler=self._profile()
        profiler.push('goalCleanup')
        for entry in self._goals:
            entry=_wrapped(entry)
            if entry.isRunning() and (entry.getFlags() & self._disabled
                                      or not entry.canContinueToUse()):
                entry.stop()
        for flag in Goal.Flag._values:
            owner=self._locked.get(flag)
            if owner is not None and not owner.isRunning():del self._locked[flag]
        profiler.pop()
        profiler.push('goalUpdate')
        for entry in self._goals:
            entry=_wrapped(entry)
            if entry.isRunning():
                continue
            if any(self._disabled.contains(flag) for flag in entry.getFlags()):
                continue
            if any(not self._locked.get(flag,_NO_GOAL).canBeReplacedBy(entry) for flag in entry.getFlags()):
                continue
            if not entry.canUse():
                continue
            for flag in entry.getFlags():
                self._locked.get(flag,_NO_GOAL).stop()
                self._locked[flag]=entry
            entry.start()
        profiler.pop()
        self.tickRunningGoals(True)

    def tickRunningGoals(self, tickAll):
        profiler=self._profile()
        profiler.push('goalTick')
        for entry in self._goals:
            entry=_wrapped(entry)
            if entry.isRunning() and (tickAll or entry.requiresUpdateEveryTick()):
                entry.tick()
        profiler.pop()


class GoalSchedulers(object):
    ABI_VERSION=1
    @staticmethod
    def require(value):
        value=_nonnull(value)
        if not isinstance(value,(GoalSelector,WrappedGoal)) or getattr(value,'_nc_GoalSchedulersABI',0)<1:
            raise UnsupportedOperationException('Goal scheduler lacks the reviewed adapter ABI1')
        return value
    @staticmethod
    def construct(java_name, target, arguments):
        expected={'net.minecraft.world.entity.ai.goal.GoalSelector':(GoalSelector,1),
                  'net.minecraft.world.entity.ai.goal.WrappedGoal':(WrappedGoal,2)}
        pair=expected.get(java_name)
        if pair is None or target is not pair[0] or len(arguments)!=pair[1]:
            raise UnsupportedOperationException('Unreviewed goal scheduler constructor')
        return target(*arguments)


JAVA_MAP = {
    "net.minecraft.world.entity.ai.goal.Goal": Goal,
    "net.minecraft.world.entity.ai.goal.Goal$Flag": Goal.Flag,
    "net.minecraft.world.entity.ai.goal.GoalSelector": GoalSelector,
    "net.minecraft.world.entity.ai.goal.WrappedGoal": WrappedGoal,
    "neocore.runtime.GoalSchedulers": GoalSchedulers,
}
