# -*- coding: utf-8 -*-
"""Official callbacks and default forwarding. World mutation belongs to implementers."""
from __future__ import absolute_import
from minecraft.official_interfaces import _declare,method,_invoke
from java_stdlib.lang import Enum,JavaString,NullPointerException

INTERFACE_CONTRACTS={}
INTERFACE_TYPES={}
_REGISTRY=(INTERFACE_CONTRACTS,INTERFACE_TYPES)
POS='net.minecraft.core.BlockPos'
STATE='net.minecraft.world.level.block.state.BlockState'
ENTITY='net.minecraft.world.entity.Entity'
WRITER='net.minecraft.world.level.LevelWriter'

def _set(self,*args,**kwargs):
    if len(args)!=3:raise NotImplementedError('Abstract LevelWriter.setBlock with four arguments')
    return _invoke(self,'setBlock',args+(512,),(POS,STATE,'int','int'))

def _destroy(self,*args,**kwargs):
    if len(args)==2:return _invoke(self,'destroyBlock',args+(None,),(POS,'boolean',ENTITY))
    if len(args)==3:return _invoke(self,'destroyBlock',args+(512,),(POS,'boolean',ENTITY,'int'))
    raise NotImplementedError('Abstract LevelWriter.destroyBlock with four arguments')

def _fresh(self,entity,**kwargs):return False

LevelWriter=_declare(WRITER,[
 method('setBlock',[POS,STATE,'int','int'],'boolean'),
 method('setBlock',[POS,STATE,'int'],'boolean',True),
 method('removeBlock',[POS,'boolean'],'boolean'),
 method('destroyBlock',[POS,'boolean'],'boolean',True),
 method('destroyBlock',[POS,'boolean',ENTITY],'boolean',True),
 method('destroyBlock',[POS,'boolean',ENTITY,'int'],'boolean'),
 method('addFreshEntity',[ENTITY],'boolean',True)],
 defaults={'setBlock':_set,'destroyBlock':_destroy,'addFreshEntity':_fresh},registry=_REGISTRY)

ENEMY='net.minecraft.world.entity.monster.Enemy'
Enemy=_declare(ENEMY,[],registry=_REGISTRY)
_REWARDS={'XP_REWARD_NONE':0,'XP_REWARD_SMALL':3,'XP_REWARD_MEDIUM':5,'XP_REWARD_LARGE':10,'XP_REWARD_HUGE':20,'XP_REWARD_BOSS':50}
for _name,_value in _REWARDS.items():setattr(Enemy,_name,_value)
INTERFACE_CONTRACTS[ENEMY]['fields']=[dict(name=n,declared_type='int',static=True,final=True,modifiers=['public','static','final'],line=1) for n in sorted(_REWARDS)]
for _contract in INTERFACE_CONTRACTS.values():_contract['helper_abi']=7
JAVA_MAP=dict(INTERFACE_TYPES)


class _BonemealType(Enum):
    def __init__(self):raise TypeError('BonemealableBlock.Type is an enum')
_bonemeal_values=[]
for _ordinal,_name in enumerate(('NEIGHBOR_SPREADER','GROWER')):
    _value=object.__new__(_BonemealType);_value._ordinal=_ordinal;_value._name=JavaString(_name)
    setattr(_BonemealType,_name,_value);_bonemeal_values.append(_value)
_BonemealType._values=tuple(_bonemeal_values)

def _growth_type(self,**kwargs):return _BonemealType.GROWER

def _particle_pos(self,pos,**kwargs):
    kind=_invoke(self,'getType')
    if kind is None:raise NullPointerException()
    if kind is _BonemealType.GROWER:return pos
    if kind is _BonemealType.NEIGHBOR_SPREADER:
        if pos is None:raise NullPointerException()
        return pos.above()
    raise TypeError('Invalid BonemealableBlock.Type')

BONE='net.minecraft.world.level.block.BonemealableBlock'
BonemealableBlock=_declare(BONE,[
 method('isValidBonemealTarget',['net.minecraft.world.level.LevelReader',POS,STATE],'boolean'),
 method('isBonemealSuccess',['net.minecraft.world.level.Level','net.minecraft.util.RandomSource',POS,STATE],'boolean'),
 method('performBonemeal',['net.minecraft.server.level.ServerLevel','net.minecraft.util.RandomSource',POS,STATE],'void'),
 method('getParticlePos',[POS],POS,True),method('getType',[],BONE+'.Type',True)],
 defaults={'getParticlePos':_particle_pos,'getType':_growth_type},registry=_REGISTRY)
BonemealableBlock.Type=_BonemealType
INTERFACE_CONTRACTS[BONE]['helper_abi']=7
JAVA_MAP.update(INTERFACE_TYPES)
JAVA_MAP[BONE+'$Type']=_BonemealType
