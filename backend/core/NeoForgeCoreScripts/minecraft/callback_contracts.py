# -*- coding: utf-8 -*-
"""Official abstract callbacks: declaring an interface never supplies its behavior.

All instance methods below are abstract in the pinned 1.21.1 client. Static
factories and world/renderer implementations are separate reviewed capabilities.
"""
from __future__ import absolute_import
from minecraft.official_interfaces import _declare, method

INTERFACE_CONTRACTS={}
INTERFACE_TYPES={}
_REGISTRY=(INTERFACE_CONTRACTS,INTERFACE_TYPES)
STACK='net.minecraft.world.item.ItemStack'
ENTITY='net.minecraft.world.entity.Entity'
LIVING='net.minecraft.world.entity.LivingEntity'
POS='net.minecraft.core.BlockPos'
STATE='net.minecraft.world.level.block.state.BlockState'
LEVEL='net.minecraft.world.level.LevelAccessor'
FLUID='net.minecraft.world.level.material.FluidState'
PLAYER='net.minecraft.world.entity.player.Player'
REASON=ENTITY+'.RemovalReason'

_ROWS={
 'com.mojang.blaze3d.platform.WindowEventHandler':[
    ('setWindowActive',['boolean'],'void'),('resizeDisplay',[],'void'),('cursorEntered',[],'void')],
 'com.mojang.blaze3d.shaders.Shader':[
    ('getId',[],'int'),('markDirty',[],'void'),('getVertexProgram',[],'com.mojang.blaze3d.shaders.Program'),
    ('getFragmentProgram',[],'com.mojang.blaze3d.shaders.Program'),('attachToProgram',[],'void')],
 'net.minecraft.client.gui.screens.recipebook.RecipeShownListener':[
    ('recipesShown',['java.util.List<net.minecraft.world.item.crafting.RecipeHolder<?>>'],'void')],
 'net.minecraft.client.model.ArmedModel':[
    ('translateToHand',['net.minecraft.world.entity.HumanoidArm','com.mojang.blaze3d.vertex.PoseStack'],'void')],
 'net.minecraft.client.model.HeadedModel':[('getHead',[],'net.minecraft.client.model.geom.ModelPart')],
 'net.minecraft.client.renderer.MultiBufferSource':[
    ('getBuffer',['net.minecraft.client.renderer.RenderType'],'com.mojang.blaze3d.vertex.VertexConsumer')],
 'net.minecraft.client.renderer.item.ItemPropertyFunction':[
    ('call',[STACK,'net.minecraft.client.multiplayer.ClientLevel',LIVING,'int'],'float')],
 'net.minecraft.client.renderer.texture.Tickable':[('tick',[],'void')],
 'net.minecraft.core.particles.ParticleOptions':[('getType',[],'net.minecraft.core.particles.ParticleType<?>')],
 'net.minecraft.data.DataProvider':[
    ('run',['net.minecraft.data.CachedOutput'],'java.util.concurrent.CompletableFuture<?>'),('getName',[],'java.lang.String')],
 'net.minecraft.data.loot.LootTableSubProvider':[
    ('generate',['java.util.function.BiConsumer<net.minecraft.resources.ResourceKey<net.minecraft.world.level.storage.loot.LootTable>,net.minecraft.world.level.storage.loot.LootTable.Builder>'],'void')],
 'net.minecraft.world.entity.Attackable':[('getLastAttacker',[],LIVING)],
 'net.minecraft.world.entity.TraceableEntity':[('getOwner',[],ENTITY)],
 'net.minecraft.world.inventory.StackedContentsCompatible':[
    ('fillStackedContents',['net.minecraft.world.entity.player.StackedContents'],'void')],
 'net.minecraft.world.level.block.BucketPickup':[
    ('pickupBlock',[PLAYER,LEVEL,POS,STATE],STACK),('getPickupSound',[],'java.util.Optional<net.minecraft.sounds.SoundEvent>')],
 'net.minecraft.world.level.block.LiquidBlockContainer':[
    ('canPlaceLiquid',[PLAYER,'net.minecraft.world.level.BlockGetter',POS,STATE,'net.minecraft.world.level.material.Fluid'],'boolean'),
    ('placeLiquid',[LEVEL,POS,STATE,FLUID],'boolean')],
 'net.minecraft.world.level.entity.EntityAccess':[
    ('getId',[],'int'),('getUUID',[],'java.util.UUID'),('blockPosition',[],POS),('getBoundingBox',[],'net.minecraft.world.phys.AABB'),
    ('setLevelCallback',['net.minecraft.world.level.entity.EntityInLevelCallback'],'void'),
    ('getSelfAndPassengers',[],'java.util.stream.Stream<? extends net.minecraft.world.level.entity.EntityAccess>'),
    ('getPassengersAndSelf',[],'java.util.stream.Stream<? extends net.minecraft.world.level.entity.EntityAccess>'),
    ('setRemoved',[REASON],'void'),('shouldBeSaved',[],'boolean'),('isAlwaysTicking',[],'boolean')],
 'net.minecraft.world.level.entity.EntityInLevelCallback':[
    ('onMove',[],'void'),('onRemove',[REASON],'void')],
 'net.minecraft.world.phys.shapes.CollisionContext':[
    ('isDescending',[],'boolean'),('isAbove',['net.minecraft.world.phys.shapes.VoxelShape',POS,'boolean'],'boolean'),
    ('isHoldingItem',['net.minecraft.world.item.Item'],'boolean'),('canStandOnFluid',[FLUID,FLUID],'boolean')],
 'net.minecraft.world.entity.npc.VillagerTrades.ItemListing':[
    ('getOffer',[ENTITY,'net.minecraft.util.RandomSource'],'net.minecraft.world.item.trading.MerchantOffer')]
}
for _identity,_methods in _ROWS.items():
    _declare(_identity,[method(n,args,result) for n,args,result in _methods],registry=_REGISTRY)
    INTERFACE_CONTRACTS[_identity]['helper_abi']=7


class VillagerTrades(object):
    """Official nested-type host only; trade registries are not supplied here."""
    ItemListing=INTERFACE_TYPES['net.minecraft.world.entity.npc.VillagerTrades.ItemListing']
    def __init__(self):raise TypeError('VillagerTrades registry host is not constructible')


JAVA_MAP=dict(INTERFACE_TYPES)
JAVA_MAP['net.minecraft.world.entity.npc.VillagerTrades']=VillagerTrades
GENERIC_INTERFACES={}
GENERIC_TYPES={}
_GENERIC_REGISTRY=(GENERIC_INTERFACES,GENERIC_TYPES)
_GENERIC_ROWS=[
 ('net.minecraft.client.gui.screens.inventory.MenuAccess',['T'],{'T':'net.minecraft.world.inventory.AbstractContainerMenu'},[
    ('getMenu',[],'T')]),
 ('net.minecraft.client.renderer.blockentity.BlockEntityRendererProvider',['T'],{'T':'net.minecraft.world.level.block.entity.BlockEntity'},[
    ('create',['net.minecraft.client.renderer.blockentity.BlockEntityRendererProvider.Context'],'net.minecraft.client.renderer.blockentity.BlockEntityRenderer<T>')]),
 ('net.minecraft.client.renderer.entity.EntityRendererProvider',['T'],{'T':ENTITY},[
    ('create',['net.minecraft.client.renderer.entity.EntityRendererProvider.Context'],'net.minecraft.client.renderer.entity.EntityRenderer<T>')]),
 ('net.minecraft.world.level.entity.EntityTypeTest',['B','T'],{'T':'B'},[
    ('tryCast',['B'],'T'),('getBaseClass',[],'java.lang.Class<? extends B>')])]
for _identity,_parameters,_bounds,_methods in _GENERIC_ROWS:
    _declare(_identity,[method(n,args,result) for n,args,result in _methods],parameters=_parameters,bounds=_bounds,registry=_GENERIC_REGISTRY)
    GENERIC_INTERFACES[_identity]['helper_abi']=7
JAVA_MAP.update(GENERIC_TYPES)
