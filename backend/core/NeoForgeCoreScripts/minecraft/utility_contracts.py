# -*- coding: utf-8 -*-
"""Official callback/default contracts independent of audio and reload drivers."""
from __future__ import absolute_import
import math
from minecraft.official_interfaces import _declare,method,_invoke
from minecraft.core import Component
from java_stdlib.lang import NullPointerException,JavaString,_to_java_float
from java_stdlib.util import JavaSet

INTERFACE_CONTRACTS={}
INTERFACE_TYPES={}
_REGISTRY=(INTERFACE_CONTRACTS,INTERFACE_TYPES)
def _false(self,*args,**kwargs):return False
def _true(self,*args,**kwargs):return True
def _nothing(self,*args,**kwargs):return None
def _fields(identity,values):
    INTERFACE_CONTRACTS[identity]['fields']=[dict(name=n,declared_type=t,static=True,final=True,modifiers=['public','static','final'],line=1) for n,t in values]

DELTA='net.minecraft.client.DeltaTracker'
DeltaTracker=_declare(DELTA,[method('getGameTimeDeltaTicks',[],'float'),method('getGameTimeDeltaPartialTick',['boolean'],'float'),method('getRealtimeDeltaTicks',[],'float')],registry=_REGISTRY)
class _Delta(DeltaTracker):
    def __init__(self,value):self.value=value
    def getGameTimeDeltaTicks(self):return self.value
    def getGameTimeDeltaPartialTick(self,paused):return self.value
    def getRealtimeDeltaTicks(self):return self.value
DeltaTracker.ZERO=_Delta(0.0);DeltaTracker.ONE=_Delta(1.0)
_fields(DELTA,[('ZERO',DELTA),('ONE',DELTA)])

SOUND='net.minecraft.client.resources.sounds.SoundInstance'
_SOUND_ROWS=[('getLocation',[],'net.minecraft.resources.ResourceLocation'),
 ('resolve',['net.minecraft.client.sounds.SoundManager'],'net.minecraft.client.sounds.WeighedSoundEvents'),
 ('getSound',[],'net.minecraft.client.resources.sounds.Sound'),('getSource',[],'net.minecraft.sounds.SoundSource'),
 ('isLooping',[],'boolean'),('isRelative',[],'boolean'),('getDelay',[],'int'),('getVolume',[],'float'),('getPitch',[],'float'),
 ('getX',[],'double'),('getY',[],'double'),('getZ',[],'double'),('getAttenuation',[],SOUND+'.Attenuation')]
SoundInstance=_declare(SOUND,[method(n,args,result) for n,args,result in _SOUND_ROWS]+
 [method('canStartSilent',[],'boolean',True),method('canPlaySound',[],'boolean',True)],
 defaults={'canStartSilent':_false,'canPlaySound':_true},registry=_REGISTRY)

COMMAND='net.minecraft.commands.CommandSource'
CommandSource=_declare(COMMAND,[method('sendSystemMessage',['net.minecraft.network.chat.Component'],'void')]+
 [method(n,[],'boolean') for n in ('acceptsSuccess','acceptsFailure','shouldInformAdmins')]+[method('alwaysAccepts',[],'boolean',True)],
 defaults={'alwaysAccepts':_false},registry=_REGISTRY)
class _NullCommand(CommandSource):
    sendSystemMessage=_nothing
    acceptsSuccess=_false
    acceptsFailure=_false
    shouldInformAdmins=_false
CommandSource.NULL=_NullCommand()
_fields(COMMAND,[('NULL',COMMAND)])

RELOAD='net.minecraft.server.packs.resources.PreparableReloadListener'
def _simple_name(self,**kwargs):
    return JavaString(getattr(type(self),'_nc_JavaName',type(self).__name__).rsplit('.',1)[-1])
PreparableReloadListener=_declare(RELOAD,[method('reload',[RELOAD+'.PreparationBarrier','net.minecraft.server.packs.resources.ResourceManager',
 'net.minecraft.util.profiling.ProfilerFiller','net.minecraft.util.profiling.ProfilerFiller','java.util.concurrent.Executor','java.util.concurrent.Executor'],
 'java.util.concurrent.CompletableFuture<java.lang.Void>'),method('getName',[],'java.lang.String',True)],defaults={'getName':_simple_name},registry=_REGISTRY)

OPTION='net.minecraft.util.OptionEnum'
def _caption(self,**kwargs):return Component.translatable(_invoke(self,'getKey'))
OptionEnum=_declare(OPTION,[method('getId',[],'int'),method('getKey',[],'java.lang.String'),method('getCaption',[],'net.minecraft.network.chat.Component',True)],defaults={'getCaption':_caption},registry=_REGISTRY)

LOOT='net.minecraft.world.level.storage.loot.LootContextUser'
def _parameters(self,**kwargs):
    return JavaSet.of()
def _validate(self,context,**kwargs):
    if context is None:raise NullPointerException()
    return _invoke(context,'validateContextUsage',(self,),(LOOT,))
LootContextUser=_declare(LOOT,[method('getReferencedContextParams',[],'java.util.Set<net.minecraft.world.level.storage.loot.parameters.LootContextParam<?>>',True),
 method('validate',['net.minecraft.world.level.storage.loot.ValidationContext'],'void',True)],
 defaults={'getReferencedContextParams':_parameters,'validate':_validate},registry=_REGISTRY)

NUMBER='net.minecraft.world.level.storage.loot.providers.number.NumberProvider'
def _rounded(self,context,**kwargs):
    from java_stdlib.function import Functional
    value=Functional.float32(_to_java_float(_invoke(self,'getFloat',(context,),('net.minecraft.world.level.storage.loot.LootContext',))))
    if math.isnan(value):return 0
    if value>=2147483647:return 2147483647
    if value<=-2147483648:return -2147483648
    return int(math.floor(value+0.5))
NumberProvider=_declare(NUMBER,INTERFACE_CONTRACTS[LOOT]['methods']+[
 method('getFloat',['net.minecraft.world.level.storage.loot.LootContext'],'float'),
 method('getInt',['net.minecraft.world.level.storage.loot.LootContext'],'int',True),
 method('getType',[],'net.minecraft.world.level.storage.loot.providers.number.LootNumberProviderType')],bases=(LootContextUser,),defaults={'getReferencedContextParams':_parameters,'validate':_validate,'getInt':_rounded},registry=_REGISTRY)
INTERFACE_CONTRACTS[NUMBER]['superinterfaces']=[LOOT]
for _contract in INTERFACE_CONTRACTS.values():_contract['helper_abi']=7
JAVA_MAP=dict(INTERFACE_TYPES)
