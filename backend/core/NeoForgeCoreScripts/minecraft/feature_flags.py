# -*- coding: utf-8 -*-
"""Official feature-set data and FeatureElement's subset default; no world driver."""
from __future__ import absolute_import
from java_stdlib.lang import NullPointerException,IllegalArgumentException,IllegalStateException
from minecraft.official_interfaces import _declare,method,_invoke

class _Universe(object):
    def __init__(self,name):self.name=name

class FeatureFlag(object):
    def __init__(self,universe,index):self._universe=universe;self._mask=(1<<(index&63))&0xffffffffffffffff

class FeatureFlagSet(object):
    MAX_CONTAINER_SIZE=64
    def __init__(self,universe,mask):self._universe=universe;self._mask=mask&0xffffffffffffffff
    @staticmethod
    def of(*flags):
        if not flags:return _EMPTY
        if flags[0] is None:raise NullPointerException()
        universe=flags[0]._universe;mask=0
        for flag in flags:
            if flag is None:raise NullPointerException()
            if flag._universe is not universe:raise IllegalStateException('Mismatched feature universes')
            mask|=flag._mask
        return FeatureFlagSet(universe,mask)
    @staticmethod
    def _of_array(first,remaining):
        if remaining is None:raise NullPointerException()
        return FeatureFlagSet.of(first,*list(remaining))
    def contains(self,flag):
        if flag is None:raise NullPointerException()
        return self._universe is flag._universe and bool(self._mask&flag._mask)
    def isEmpty(self):return self.equals(_EMPTY)
    def isSubsetOf(self,other):
        if self._universe is None:return True
        if other is None:raise NullPointerException()
        return self._universe is other._universe and self._mask&~other._mask==0
    def intersects(self,other):
        if self._universe is None:return False
        if other is None:raise NullPointerException()
        return other._universe is not None and self._universe is other._universe and bool(self._mask&other._mask)
    def join(self,other):
        if self._universe is None:return other
        if other is None:raise NullPointerException()
        if other._universe is None:return self
        if self._universe is not other._universe:raise IllegalArgumentException('Mismatched feature universes')
        return FeatureFlagSet(self._universe,self._mask|other._mask)
    def subtract(self,other):
        if self._universe is None:return self
        if other is None:raise NullPointerException()
        if other._universe is None:return self
        if self._universe is not other._universe:raise IllegalArgumentException('Mismatched feature universes')
        mask=self._mask&~other._mask
        return FeatureFlagSet(self._universe,mask) if mask else _EMPTY
    def equals(self,other):return isinstance(other,FeatureFlagSet) and self._universe is other._universe and self._mask==other._mask
    def hashCode(self):
        value=(self._mask*0x9e3779b97f4a7c15)&0xffffffffffffffff
        value^=value>>32;value^=value>>16;value&=0xffffffff
        return value-(1<<32) if value&(1<<31) else value
    def __eq__(self,other):return self.equals(other)
    def __ne__(self,other):return not self.equals(other)
    def __hash__(self):return self.hashCode()

_EMPTY=FeatureFlagSet(None,0)
_MAIN=_Universe('main')
class FeatureFlags(object):
    VANILLA=FeatureFlag(_MAIN,0)
    BUNDLE=FeatureFlag(_MAIN,1)
    TRADE_REBALANCE=FeatureFlag(_MAIN,2)
    VANILLA_SET=FeatureFlagSet.of(VANILLA)
    DEFAULT_FLAGS=VANILLA_SET
    @staticmethod
    def isExperimental(features):
        if features is None:raise NullPointerException()
        return not features.isSubsetOf(FeatureFlags.VANILLA_SET)

FEATURE='net.minecraft.world.flag.FeatureElement'
SET='net.minecraft.world.flag.FeatureFlagSet'
INTERFACE_CONTRACTS={}
INTERFACE_TYPES={}
def _enabled(self,features,_nc_java_signature=None):
    required=_invoke(self,'requiredFeatures')
    if required is None:raise NullPointerException()
    return required.isSubsetOf(features)
FeatureElement=_declare(FEATURE,[method('requiredFeatures',[],SET),method('isEnabled',[SET],'boolean',True)],defaults={'isEnabled':_enabled},registry=(INTERFACE_CONTRACTS,INTERFACE_TYPES))
INTERFACE_CONTRACTS[FEATURE]['helper_abi']=7
JAVA_MAP=dict(INTERFACE_TYPES)
JAVA_MAP.update({'net.minecraft.world.flag.FeatureFlag':FeatureFlag,SET:FeatureFlagSet,'net.minecraft.world.flag.FeatureFlags':FeatureFlags})
