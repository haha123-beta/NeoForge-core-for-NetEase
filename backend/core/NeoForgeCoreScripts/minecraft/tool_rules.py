# -*- coding: utf-8 -*-
"""Original Tool/Tier rule evaluation over registry-backed holder sets.

Tag loading is a separate caller responsibility. Codecs and floating-point
record formatting are deliberately not exported as supported source APIs.
"""
from __future__ import absolute_import
import math,struct
from java_stdlib.lang import NullPointerException,Float,Boolean,UnsupportedOperationException
from java_stdlib.records import RecordBase
from java_stdlib.function import Functional
from java_stdlib.util import Optional,ImmutableList
from java_stdlib.primitives import Int32
from minecraft.official_interfaces import _declare,method,_invoke
from minecraft.holder_sets import HolderSet
from neoforge.registries import BUILT_IN_REGISTRIES

def _float(v):return Functional.float32(v.floatValue() if hasattr(v,'floatValue') else v)
def _bits(v):
    v=_float(v)
    return 0x7fc00000 if math.isnan(v) else struct.unpack('>I',struct.pack('>f',v))[0]
def _boolean(v):return v.booleanValue() if hasattr(v,'booleanValue') else bool(v)
def _opt_equal(a,b,float_value=False):
    if a is b:return True
    if a is None or b is None:return False
    if a.isPresent()!=b.isPresent():return False
    return not a.isPresent() or (_bits(a.get())==_bits(b.get()) if float_value else _boolean(a.get())==_boolean(b.get()))
def _optional_hash(value,float_value=False):
    return 0 if value is None or not value.isPresent() else Int32.wrap(_bits(value.get())) if float_value else 1231 if _boolean(value.get()) else 1237
def _matches(state,holders):
    if state is None:raise NullPointerException()
    if holders is None:raise NullPointerException()
    block=state.getBlock()
    return holders.contains(BUILT_IN_REGISTRIES.BLOCK._holder_for_value(block))

class Rule(RecordBase):
    _nc_JavaName='net.minecraft.world.item.component.Tool$Rule'
    _nc_RecordComponents=(('blocks','net.minecraft.core.HolderSet','_blocks'),('speed','java.util.Optional','_speed'),('correctForDrops','java.util.Optional','_correct'))
    def __init__(self,blocks,speed,correct):
        self._blocks=blocks;self._speed=speed;self._correct=correct
        object.__setattr__(self,'_nc_record_sealed',True)
    def blocks(self):return self._blocks
    def speed(self):return self._speed
    def correctForDrops(self):return self._correct
    @staticmethod
    def _for_tag(tag,speed,correct):return Rule(BUILT_IN_REGISTRIES.BLOCK.getOrCreateTag(tag),speed,correct)
    @staticmethod
    def _for_blocks(blocks,speed,correct):
        if blocks is None:raise NullPointerException()
        holders=[BUILT_IN_REGISTRIES.BLOCK._holder_for_value(b) for b in blocks]
        return Rule(HolderSet._direct_list(holders),speed,correct)
    @staticmethod
    def deniesDrops(tag):return Rule._for_tag(tag,Optional.empty(),Optional.of(Boolean.valueOf(False)))
    @staticmethod
    def minesAndDrops(tag,speed):return Rule._for_tag(tag,Optional.of(Float(_float(speed))),Optional.of(Boolean.valueOf(True)))
    @staticmethod
    def overrideSpeed(tag,speed):return Rule._for_tag(tag,Optional.of(Float(_float(speed))),Optional.empty())
    @staticmethod
    def _mines_blocks(blocks,speed):return Rule._for_blocks(blocks,Optional.of(Float(_float(speed))),Optional.of(Boolean.valueOf(True)))
    @staticmethod
    def _speed_blocks(blocks,speed):return Rule._for_blocks(blocks,Optional.of(Float(_float(speed))),Optional.empty())
    def equals(self,other):return self is other or type(other) is Rule and (self._blocks is other._blocks or self._blocks is not None and self._blocks.equals(other._blocks)) and _opt_equal(self._speed,other._speed,True) and _opt_equal(self._correct,other._correct)
    def hashCode(self):return Int32.add(Int32.multiply(Int32.add(Int32.multiply(0 if self._blocks is None else self._blocks.hashCode(),31),_optional_hash(self._speed,True)),31),_optional_hash(self._correct))
    def __eq__(self,other):return self.equals(other)
    def __ne__(self,other):return not self.equals(other)
    def __hash__(self):return self.hashCode()
    def toString(self):raise UnsupportedOperationException('Tool.Rule record text requires floating-point formatting support')

class Tool(RecordBase):
    _nc_JavaName='net.minecraft.world.item.component.Tool'
    _nc_RecordComponents=(('rules','java.util.List','_rules'),('defaultMiningSpeed','float','_speed'),('damagePerBlock','int','_damage'))
    def __init__(self,rules,speed,damage):
        self._rules=rules;self._speed=_float(speed);self._damage=Int32.wrap(damage)
        object.__setattr__(self,'_nc_record_sealed',True)
    def rules(self):return self._rules
    def defaultMiningSpeed(self):return self._speed
    def damagePerBlock(self):return self._damage
    def getMiningSpeed(self,state):
        if self._rules is None:raise NullPointerException()
        for rule in self._rules:
            if rule is None:raise NullPointerException()
            if rule.speed().isPresent() and _matches(state,rule.blocks()):return _float(rule.speed().get())
        return self._speed
    def isCorrectForDrops(self,state):
        if self._rules is None:raise NullPointerException()
        for rule in self._rules:
            if rule is None:raise NullPointerException()
            if rule.correctForDrops().isPresent() and _matches(state,rule.blocks()):return _boolean(rule.correctForDrops().get())
        return False
    def equals(self,other):
        if type(other) is not Tool or _bits(self._speed)!=_bits(other._speed) or self._damage!=other._damage:return False
        if self._rules is other._rules:return True
        return self._rules is not None and other._rules is not None and len(self._rules)==len(other._rules) and all(a is b or a is not None and a.equals(b) for a,b in zip(self._rules,other._rules))
    def hashCode(self):
        part=0
        if self._rules is not None:
            part=1
            for rule in self._rules:part=Int32.add(Int32.multiply(part,31),0 if rule is None else rule.hashCode())
        return Int32.add(Int32.multiply(Int32.add(Int32.multiply(part,31),Int32.wrap(_bits(self._speed))),31),self._damage)
    def __eq__(self,other):return self.equals(other)
    def __ne__(self,other):return not self.equals(other)
    def __hash__(self):return self.hashCode()
    def toString(self):raise UnsupportedOperationException('Tool record text requires floating-point formatting support')

Tool.Rule=Rule
TIER='net.minecraft.world.item.Tier'
TAG='net.minecraft.tags.TagKey<net.minecraft.world.level.block.Block>'
def _properties(self,tag,_nc_java_signature=None):
    first=Rule.deniesDrops(_invoke(self,'getIncorrectBlocksForDrops'))
    second=Rule.minesAndDrops(tag,_invoke(self,'getSpeed'))
    return Tool(ImmutableList([first,second],reject_null=True),1.0,1)
INTERFACE_CONTRACTS={}
INTERFACE_TYPES={}
Tier=_declare(TIER,[method('getUses',[],'int'),method('getSpeed',[],'float'),method('getAttackDamageBonus',[],'float'),
 method('getIncorrectBlocksForDrops',[],TAG),method('getEnchantmentValue',[],'int'),method('getRepairIngredient',[],'net.minecraft.world.item.crafting.Ingredient'),
 method('createToolProperties',[TAG],'net.minecraft.world.item.component.Tool',True)],defaults={'createToolProperties':_properties},registry=(INTERFACE_CONTRACTS,INTERFACE_TYPES))
INTERFACE_CONTRACTS[TIER]['helper_abi']=7
JAVA_MAP=dict(INTERFACE_TYPES)
JAVA_MAP.update({'net.minecraft.world.item.component.Tool':Tool,'net.minecraft.world.item.component.Tool$Rule':Rule})
