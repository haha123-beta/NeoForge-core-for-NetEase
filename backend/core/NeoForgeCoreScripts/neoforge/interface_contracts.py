# -*- coding: utf-8 -*-
"""NeoForge 21.1.233 interface obligations, checked against the pinned official sources.

Reuses the real in-memory handler types. These descriptors do not implement
registry-aware serialization, attachment transport, or engine capabilities.
"""
from __future__ import absolute_import
from minecraft.official_interfaces import _declare,method
from neoforge.items import IItemHandler,IItemHandlerModifiable
from neoforge.energy import IEnergyStorage
from neoforge.fluid_handler import IFluidHandler,IFluidHandlerItem,IFluidTank
from neoforge.attachment import INBTSerializable,IAttachmentCopyHandler
from neoforge.capabilities import ICapabilityProvider

INTERFACE_CONTRACTS={}
INTERFACE_TYPES={}
GENERIC_INTERFACES={}
GENERIC_TYPES={}
STACK='net.minecraft.world.item.ItemStack'
FLUID='net.neoforged.neoforge.fluids.FluidStack'
ACTION='net.neoforged.neoforge.fluids.capability.IFluidHandler.FluidAction'
PROVIDER='net.minecraft.core.HolderLookup.Provider'
HOLDER='net.neoforged.neoforge.attachment.IAttachmentHolder'
BUFFER='net.minecraft.network.RegistryFriendlyByteBuf'
_ITEM_ROWS=[('getSlots',[],'int'),('getStackInSlot',['int'],STACK),
    ('insertItem',['int',STACK,'boolean'],STACK),('extractItem',['int','int','boolean'],STACK),
    ('getSlotLimit',['int'],'int'),('isItemValid',['int',STACK],'boolean')]
_FLUID_ROWS=[('getTanks',[],'int'),('getFluidInTank',['int'],FLUID),('getTankCapacity',['int'],'int'),
    ('isFluidValid',['int',FLUID],'boolean'),('fill',[FLUID,ACTION],'int'),
    ('drain',[FLUID,ACTION],FLUID),('drain',['int',ACTION],FLUID)]
_PLAIN=[
 ('net.neoforged.neoforge.items.IItemHandler',IItemHandler,_ITEM_ROWS,[]),
 ('net.neoforged.neoforge.items.IItemHandlerModifiable',IItemHandlerModifiable,_ITEM_ROWS+[('setStackInSlot',['int',STACK],'void')],['net.neoforged.neoforge.items.IItemHandler']),
 ('net.neoforged.neoforge.energy.IEnergyStorage',IEnergyStorage,[
    ('receiveEnergy',['int','boolean'],'int'),('extractEnergy',['int','boolean'],'int'),
    ('getEnergyStored',[],'int'),('getMaxEnergyStored',[],'int'),('canExtract',[],'boolean'),('canReceive',[],'boolean')],[]),
 ('net.neoforged.neoforge.fluids.capability.IFluidHandler',IFluidHandler,_FLUID_ROWS,[]),
 ('net.neoforged.neoforge.fluids.capability.IFluidHandlerItem',IFluidHandlerItem,_FLUID_ROWS+[('getContainer',[],STACK)],['net.neoforged.neoforge.fluids.capability.IFluidHandler']),
 ('net.neoforged.neoforge.fluids.IFluidTank',IFluidTank,[
    ('getFluid',[],FLUID),('getFluidAmount',[],'int'),('getCapacity',[],'int'),('isFluidValid',[FLUID],'boolean'),
    ('fill',[FLUID,ACTION],'int'),('drain',[FLUID,ACTION],FLUID),('drain',['int',ACTION],FLUID)],[])]
for _identity,_type,_methods,_parents in _PLAIN:
    INTERFACE_CONTRACTS[_identity]=dict(abi=1,helper_abi=7,java_name=_identity,
        methods=[method(n,args,result) for n,args,result in _methods],superinterfaces=_parents)
    INTERFACE_TYPES[_identity]=_type

_GENERIC=[
 ('net.neoforged.neoforge.common.util.INBTSerializable',INBTSerializable,['T'],{'T':'net.minecraft.nbt.Tag'},[
    ('serializeNBT',[PROVIDER],'T'),('deserializeNBT',[PROVIDER,'T'],'void')]),
 ('net.neoforged.neoforge.attachment.IAttachmentCopyHandler',IAttachmentCopyHandler,['T'],{},[
    ('copy',['T',HOLDER,PROVIDER],'T')]),
 ('net.neoforged.neoforge.capabilities.ICapabilityProvider',ICapabilityProvider,['O','C','T'],{},[
    ('getCapability',['O','C'],'T')])]
for _identity,_type,_parameters,_bounds,_methods in _GENERIC:
    GENERIC_INTERFACES[_identity]=dict(abi=1,helper_abi=7,java_name=_identity,type_parameters=_parameters,type_bounds=_bounds,
        methods=[method(n,args,result) for n,args,result in _methods])
    GENERIC_TYPES[_identity]=_type

_REGISTRY=(GENERIC_INTERFACES,GENERIC_TYPES)
def _send(self,holder,player,_nc_java_signature=None):return True
AttachmentSyncHandler=_declare('net.neoforged.neoforge.attachment.AttachmentSyncHandler',[
    method('sendToPlayer',[HOLDER,'net.minecraft.server.level.ServerPlayer'],'boolean',True),
    method('write',[BUFFER,'T','boolean'],'void'),method('read',[HOLDER,BUFFER,'T'],'T')],
    parameters=['T'],defaults={'sendToPlayer':_send},registry=_REGISTRY)
IPayloadHandler=_declare('net.neoforged.neoforge.network.handling.IPayloadHandler',[
    method('handle',['T','net.neoforged.neoforge.network.handling.IPayloadContext'],'void')],parameters=['T'],
    bounds={'T':'net.minecraft.network.protocol.common.custom.CustomPacketPayload'},registry=_REGISTRY)
for _contract in GENERIC_INTERFACES.values():_contract['helper_abi']=7
JAVA_MAP=dict(INTERFACE_TYPES,**GENERIC_TYPES)
