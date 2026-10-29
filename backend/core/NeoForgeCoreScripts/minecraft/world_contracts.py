# -*- coding: utf-8 -*-
"""Official height and callback contracts; no world generation or GPU driver."""
from __future__ import absolute_import
from minecraft.official_interfaces import _declare,method,_invoke
from java_stdlib.lang import NullPointerException
try:_integers=(int,long)
except NameError:_integers=(int,)

INTERFACE_CONTRACTS={}
INTERFACE_TYPES={}
GENERIC_INTERFACES={}
GENERIC_TYPES={}
_REGISTRY=(INTERFACE_CONTRACTS,INTERFACE_TYPES)
HEIGHT='net.minecraft.world.level.LevelHeightAccessor'
POS='net.minecraft.core.BlockPos'

def _int(value):return ((int(value)+2147483648)&4294967295)-2147483648
def _max(self,**kwargs):return _int(_invoke(self,'getMinBuildHeight')+_invoke(self,'getHeight'))
def _count(self,**kwargs):return _int(_invoke(self,'getMaxSection')-_invoke(self,'getMinSection'))
def _min_section(self,**kwargs):return _invoke(self,'getMinBuildHeight')>>4
def _max_section(self,**kwargs):return _int((_int(_invoke(self,'getMaxBuildHeight')-1)>>4)+1)
def _outside(self,y,_nc_java_signature=None):
    signature=tuple(_nc_java_signature or ())
    if signature==(POS,) or (not signature and not isinstance(y,_integers)):
        if y is None:raise NullPointerException()
        return _invoke(self,'isOutsideBuildHeight',(y.getY(),),('int',))
    return y<_invoke(self,'getMinBuildHeight') or y>=_invoke(self,'getMaxBuildHeight')
def _index(self,y,**kwargs):return _invoke(self,'getSectionIndexFromSectionY',(y>>4,),('int',))
def _from_y(self,y,**kwargs):return _int(y-_invoke(self,'getMinSection'))
def _from_index(self,index,**kwargs):return _int(index+_invoke(self,'getMinSection'))

_DEFAULTS=[('getMaxBuildHeight',[],'int',_max),('getSectionsCount',[],'int',_count),
 ('getMinSection',[],'int',_min_section),('getMaxSection',[],'int',_max_section),
 ('isOutsideBuildHeight',[POS],'boolean',_outside),('isOutsideBuildHeight',['int'],'boolean',_outside),
 ('getSectionIndex',['int'],'int',_index),('getSectionIndexFromSectionY',['int'],'int',_from_y),
 ('getSectionYFromSectionIndex',['int'],'int',_from_index)]
LevelHeightAccessor=_declare(HEIGHT,[method('getHeight',[],'int'),method('getMinBuildHeight',[],'int')]+
 [method(n,args,result,True) for n,args,result,fn in _DEFAULTS],
 defaults={n:fn for n,args,result,fn in _DEFAULTS},registry=_REGISTRY)

class _Height(LevelHeightAccessor):
    def __init__(self,minimum,height):self.minimum=_int(minimum);self.height=_int(height)
    def getHeight(self):return self.height
    def getMinBuildHeight(self):return self.minimum

LevelHeightAccessor.create=staticmethod(lambda minimum,height:_Height(minimum,height))

_declare('net.minecraft.client.renderer.texture.Dumpable',[
 method('dumpContents',['net.minecraft.resources.ResourceLocation','java.nio.file.Path'],'void')],registry=_REGISTRY)
_declare('net.minecraft.network.syncher.SyncedDataHolder',[
 method('onSyncedDataUpdated',['net.minecraft.network.syncher.EntityDataAccessor<?>'],'void'),
 method('onSyncedDataUpdated',['java.util.List<net.minecraft.network.syncher.SynchedEntityData.DataValue<?>>'],'void')],registry=_REGISTRY)
_declare('net.minecraft.world.level.biome.BiomeManager.NoiseBiomeSource',[
 method('getNoiseBiome',['int','int','int'],'net.minecraft.core.Holder<net.minecraft.world.level.biome.Biome>')],registry=_REGISTRY)

def _offscreen(self,entity,**kwargs):return False
def _view_distance(self,**kwargs):return 64
def _should_render(self,entity,position,**kwargs):
    if entity is None or position is None:raise NullPointerException()
    p=entity.getBlockPos()
    if p is None:raise NullPointerException()
    dx=p.getX()+0.5-position.x;dy=p.getY()+0.5-position.y;dz=p.getZ()+0.5-position.z
    distance=_invoke(self,'getViewDistance')
    return dx*dx+dy*dy+dz*dz<float(distance)*float(distance)

RENDERER='net.minecraft.client.renderer.blockentity.BlockEntityRenderer'
BlockEntityRenderer=_declare(RENDERER,[
 method('render',['T','float','com.mojang.blaze3d.vertex.PoseStack','net.minecraft.client.renderer.MultiBufferSource','int','int'],'void'),
 method('shouldRenderOffScreen',['T'],'boolean',True),method('getViewDistance',[],'int',True),
 method('shouldRender',['T','net.minecraft.world.phys.Vec3'],'boolean',True)],
 parameters=['T'],bounds={'T':'net.minecraft.world.level.block.entity.BlockEntity'},
 defaults={'shouldRenderOffScreen':_offscreen,'getViewDistance':_view_distance,'shouldRender':_should_render},
 registry=(GENERIC_INTERFACES,GENERIC_TYPES))
for _contract in list(INTERFACE_CONTRACTS.values())+list(GENERIC_INTERFACES.values()):_contract['helper_abi']=7
JAVA_MAP=dict(INTERFACE_TYPES,**GENERIC_TYPES)
