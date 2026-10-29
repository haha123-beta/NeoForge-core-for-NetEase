# -*- coding: utf-8 -*-
"""Reviewed runtime superclass adapters, separate from generated-class ABIs."""
from __future__ import absolute_import
import copy
from minecraft.goals import Goal
from minecraft.entity import Entity, _EntityType
from minecraft.level import Level
from java_stdlib.lang import NullPointerException
from minecraft.gui_contracts import INTERFACE_CONTRACTS as GUI_CONTRACTS, INTERFACE_TYPES as GUI_TYPES
from minecraft.network_contracts import INTERFACE_CONTRACTS as NET_CONTRACTS, INTERFACE_TYPES as NET_TYPES, GENERIC_INTERFACES, GENERIC_TYPES, specialize
INTERFACE_CONTRACTS=dict(GUI_CONTRACTS,**NET_CONTRACTS)
INTERFACE_TYPES=dict(GUI_TYPES,**NET_TYPES)
from minecraft.official_interfaces import INTERFACE_CONTRACTS as OFFICIAL_CONTRACTS, INTERFACE_TYPES as OFFICIAL_TYPES
from minecraft.container_contracts import INTERFACE_CONTRACTS as CONTAINER_CONTRACTS, INTERFACE_TYPES as CONTAINER_TYPES
from minecraft.callback_contracts import INTERFACE_CONTRACTS as CALLBACK_CONTRACTS, INTERFACE_TYPES as CALLBACK_TYPES
from minecraft.gui_input_contracts import INTERFACE_CONTRACTS as INPUT_CONTRACTS, INTERFACE_TYPES as INPUT_TYPES
from neoforge.interface_contracts import INTERFACE_CONTRACTS as PLATFORM_CONTRACTS, INTERFACE_TYPES as PLATFORM_TYPES
INTERFACE_CONTRACTS.update(OFFICIAL_CONTRACTS)
INTERFACE_TYPES.update(OFFICIAL_TYPES)
INTERFACE_CONTRACTS.update(CONTAINER_CONTRACTS)
INTERFACE_TYPES.update(CONTAINER_TYPES)
INTERFACE_CONTRACTS.update(CALLBACK_CONTRACTS)
INTERFACE_TYPES.update(CALLBACK_TYPES)
INTERFACE_CONTRACTS.update(INPUT_CONTRACTS)
INTERFACE_TYPES.update(INPUT_TYPES)
from minecraft.world_contracts import INTERFACE_CONTRACTS as WORLD_CONTRACTS, INTERFACE_TYPES as WORLD_TYPES
from minecraft.utility_contracts import INTERFACE_CONTRACTS as UTILITY_CONTRACTS, INTERFACE_TYPES as UTILITY_TYPES
INTERFACE_CONTRACTS.update(UTILITY_CONTRACTS)
INTERFACE_TYPES.update(UTILITY_TYPES)
from minecraft.feature_flags import INTERFACE_CONTRACTS as FEATURE_CONTRACTS, INTERFACE_TYPES as FEATURE_TYPES
INTERFACE_CONTRACTS.update(FEATURE_CONTRACTS)
INTERFACE_TYPES.update(FEATURE_TYPES)
from minecraft.tool_rules import INTERFACE_CONTRACTS as TOOL_CONTRACTS, INTERFACE_TYPES as TOOL_TYPES
INTERFACE_CONTRACTS.update(TOOL_CONTRACTS)
INTERFACE_TYPES.update(TOOL_TYPES)
from minecraft.writer_contracts import INTERFACE_CONTRACTS as WRITER_CONTRACTS, INTERFACE_TYPES as WRITER_TYPES
INTERFACE_CONTRACTS.update(WRITER_CONTRACTS)
INTERFACE_TYPES.update(WRITER_TYPES)
from minecraft.model_math import INTERFACE_CONTRACTS as MODEL_CONTRACTS, INTERFACE_TYPES as MODEL_TYPES
INTERFACE_CONTRACTS.update(MODEL_CONTRACTS)
INTERFACE_TYPES.update(MODEL_TYPES)
from minecraft.vertex_sorting import INTERFACE_CONTRACTS as SORT_CONTRACTS, INTERFACE_TYPES as SORT_TYPES
INTERFACE_CONTRACTS.update(SORT_CONTRACTS)
INTERFACE_TYPES.update(SORT_TYPES)
INTERFACE_CONTRACTS.update(WORLD_CONTRACTS)
INTERFACE_TYPES.update(WORLD_TYPES)
INTERFACE_CONTRACTS.update(PLATFORM_CONTRACTS)
INTERFACE_TYPES.update(PLATFORM_TYPES)


_GOAL = 'net.minecraft.world.entity.ai.goal.Goal'
_METHODS = [dict(name=name, parameters=[], return_type=kind, static=False,
    abstract=(name == 'canUse'), visibility='public') for name, kind in (
        ('canUse', 'boolean'), ('canContinueToUse', 'boolean'),
        ('isInterruptable', 'boolean'), ('requiresUpdateEveryTick', 'boolean'),
        ('start', 'void'), ('stop', 'void'), ('tick', 'void'))]
_METHODS.extend([
    dict(name='setFlags', parameters=['java.util.EnumSet'], return_type='void',
         static=False, abstract=False, visibility='public'),
    dict(name='getFlags', parameters=[], return_type='java.util.EnumSet<net.minecraft.world.entity.ai.goal.Goal.Flag>',
         static=False, abstract=False, visibility='public'),
    dict(name='adjustedTickDelay', parameters=['int'], return_type='int',
         static=False, abstract=False, visibility='protected'),
    dict(name='reducedTickDelay', parameters=['int'], return_type='int',
         static=True, abstract=False, visibility='protected')])
_CONTRACTS = {_GOAL: dict(abi=1, java_name=_GOAL, abstract=True, constructors=[[]], constructor_visibility='public',
    methods=_METHODS, reserved_members=['_flags', '_nc_RuntimeSuperclassABI'])}


class _GoalRuntimeBase(Goal):
    _nc_RuntimeSuperclassABI = 1

    def __init__(self, *args, **kwargs):
        signature = kwargs.pop('_nc_java_constructor', ())
        if args or kwargs or tuple(signature) != ():
            raise TypeError('Goal runtime constructor requires the reviewed empty signature')
        Goal.__init__(self)


def _method_adapter(entry, base_type=Goal):
    name, signature = entry['name'], tuple(entry['parameters'])
    original = getattr(base_type, name)
    def check(args, kwargs):
        selected = kwargs.pop('_nc_java_signature', signature)
        if kwargs or (selected is not None and tuple(selected) != signature) or len(args) != len(signature):
            raise TypeError(base_type.__name__ + ' runtime method signature mismatch: ' + name)
    if entry['static']:
        def invoke(*args, **kwargs):
            check(args, kwargs)
            return original(*args)
        return staticmethod(invoke)
    def invoke(self, *args, **kwargs):
        check(args, kwargs)
        return original(self, *args)
    return invoke


for _entry in _METHODS:
    setattr(_GoalRuntimeBase, _entry['name'], _method_adapter(_entry))

_ADAPTERS = {_GOAL: _GoalRuntimeBase}
_BASE_TYPES = {_GOAL: Goal}



_ENTITY = 'net.minecraft.world.entity.Entity'
_ENTITY_CONSTRUCTOR = ('net.minecraft.world.entity.EntityType', 'net.minecraft.world.level.Level')
_ENTITY_METHODS = [
    dict(name='defineSynchedData', parameters=['net.minecraft.network.syncher.SynchedEntityData.Builder'], return_type='void', static=False, abstract=True, visibility='protected'),
    dict(name='readAdditionalSaveData', parameters=['net.minecraft.nbt.CompoundTag'], return_type='void', static=False, abstract=True, visibility='protected'),
    dict(name='addAdditionalSaveData', parameters=['net.minecraft.nbt.CompoundTag'], return_type='void', static=False, abstract=True, visibility='protected')]
for _name, _parameters, _return, _final in (
        ('tick', [], 'void', False),
        ('level', [], 'net.minecraft.world.level.Level', False),
        ('getType', [], 'net.minecraft.world.entity.EntityType', False),
        ('isRemoved', [], 'boolean', True),
        ('discard', [], 'void', True),
        ('saveWithoutId', ['net.minecraft.nbt.CompoundTag'], 'net.minecraft.nbt.CompoundTag', False),
        ('save', ['net.minecraft.nbt.CompoundTag'], 'boolean', False),
        ('load', ['net.minecraft.nbt.CompoundTag'], 'void', False)):
    _ENTITY_METHODS.append(dict(name=_name, parameters=_parameters, return_type=_return,
        static=False, abstract=False, visibility='public', final=_final))
_CONTRACTS[_ENTITY] = dict(abi=1, helper_abi=3, java_name=_ENTITY, abstract=True,
    constructors=[list(_ENTITY_CONSTRUCTOR)], constructor_visibility='public',
    methods=_ENTITY_METHODS, reserved_members=['__eq__', '__hash__', '__init__', '__ne__', '__repr__', '__str__', '_entity_data', '_entity_type', '_id', '_identifier', '_level_access', '_nc_RuntimeSuperclassABI', '_nc_attachments', '_persistent_data', '_position', '_removed', '_uuid', '_x_rot', '_y_rot', 'blockPosition', 'copyAttachmentsFrom', 'distanceTo', 'distanceToSqr', 'equals', 'getBoundingBox', 'getCapability', 'getEntityData', 'getEyeHeight', 'getEyePosition', 'getHeight', 'getId', 'getIdentifier', 'getLevel', 'getLevelAccess', 'getPersistentData', 'getUUID', 'getViewVector', 'getWidth', 'getX', 'getXRot', 'getY', 'getYRot', 'getZ', 'hashCode', 'isAlive', 'onSyncedDataUpdated', 'position', 'remove', 'setIdentifier', 'setLevelAccess', 'setPos', 'setUUID', 'setXRot', 'setYRot', 'tickCount', '_invoke_entity_hook'])


_CONTRACTS[_ENTITY]['reserved_members'].extend(['_level_wrapper', '_neocore_attachments', '_attachment_types', '_registry_provider', '_event_bus'])


class _EntityRuntimeBase(Entity):
    _nc_RuntimeSuperclassABI = 1

    def __init__(self, *args, **kwargs):
        selected = kwargs.pop('_nc_java_constructor', _ENTITY_CONSTRUCTOR)
        if kwargs or tuple(selected) != _ENTITY_CONSTRUCTOR or len(args) != 2:
            raise TypeError('Entity requires the reviewed EntityType/Level constructor')
        if args[0] is None or args[1] is None:
            raise NullPointerException()
        if not isinstance(args[0], _EntityType) or not isinstance(args[1], Level):
            raise TypeError('Entity constructor arguments must be EntityType and Level')
        Entity.__init__(self, args[0], args[1])


for _entry in _ENTITY_METHODS:
    setattr(_EntityRuntimeBase, _entry['name'], _method_adapter(_entry, Entity))
_ADAPTERS[_ENTITY] = _EntityRuntimeBase
_BASE_TYPES[_ENTITY] = Entity


# Minecraft 1.21.1: official mappings and original AbstractContainerMenu javap.
from minecraft.menu import AbstractContainerMenu, MenuType
_MENU = 'net.minecraft.world.inventory.AbstractContainerMenu'
_MENU_TYPE = 'net.minecraft.world.inventory.MenuType'
_PLAYER = 'net.minecraft.world.entity.player.Player'
_STACK = 'net.minecraft.world.item.ItemStack'
_MENU_CTOR = (_MENU_TYPE, 'int')
_MENU_METHODS = []
for _name, _args, _result, _visibility, _abstract in (
        ('quickMoveStack', [_PLAYER, 'int'], _STACK, 'public', True),
        ('stillValid', [_PLAYER], 'boolean', 'public', True),
        ('getType', [], _MENU_TYPE+'<?>', 'public', False),
        ('getStateId', [], 'int', 'public', False),
        ('incrementStateId', [], 'int', 'public', False),
        ('isValidSlotIndex', ['int'], 'boolean', 'public', False),
        ('getItems', [], 'net.minecraft.core.NonNullList<'+_STACK+'>', 'public', False),
        ('setItem', ['int','int',_STACK], 'void', 'public', False),
        ('initializeContents', ['int','java.util.List<'+_STACK+'>',_STACK], 'void', 'public', False),
        ('setRemoteSlot', ['int',_STACK], 'void', 'public', False),
        ('setRemoteSlotNoCopy', ['int',_STACK], 'void', 'public', False),
        ('setRemoteCarried', [_STACK], 'void', 'public', False),
        ('sendAllDataToRemote', [], 'void', 'public', False),
        ('broadcastFullState', [], 'void', 'public', False),
        ('suppressRemoteUpdates', [], 'void', 'public', False),
        ('resumeRemoteUpdates', [], 'void', 'public', False),
        ('getSlot', ['int'], 'net.minecraft.world.inventory.Slot', 'public', False),
        ('addSlot', ['net.minecraft.world.inventory.Slot'], 'net.minecraft.world.inventory.Slot', 'protected', False),
        ('addDataSlot', ['net.minecraft.world.inventory.DataSlot'], 'net.minecraft.world.inventory.DataSlot', 'protected', False),
        ('getCarried', [], _STACK, 'public', False),
        ('setCarried', [_STACK], 'void', 'public', False),
        ('removed', [_PLAYER], 'void', 'public', False),
        ('broadcastChanges', [], 'void', 'public', False),
        ('moveItemStackTo', [_STACK,'int','int','boolean'], 'boolean', 'protected', False)):
    _MENU_METHODS.append(dict(name=_name, parameters=_args, return_type=_result,
        static=False, abstract=_abstract, visibility=_visibility))
_MENU_RESERVED = [name for name in AbstractContainerMenu.__dict__ if name not in
    ('__doc__','__module__','__dict__','__weakref__') and name not in [row['name'] for row in _MENU_METHODS]]
_MENU_RESERVED.extend(['_container_id','_menu_type','menuType','containerId','_container','_inventory','_title',
    'slots','_data_slots','_removed','_quick_move_calls','_synchronizer','_listeners','_last_slots','_remote_slots',
    '_remote_data','_suppress_remote_updates','_carried','_remote_carried','_flat_data_slots','_state_id','_nc_RuntimeSuperclassABI'])
_CONTRACTS[_MENU] = dict(abi=1,helper_abi=4,java_name=_MENU,abstract=True,
    constructors=[list(_MENU_CTOR)],constructor_visibility='protected',methods=_MENU_METHODS,
    fields=[dict(name='containerId',declared_type='int',static=False,final=True,modifiers=['public','final'],line=1)],
    reserved_members=sorted(set(_MENU_RESERVED)))

class _MenuRuntimeBase(AbstractContainerMenu):
    _nc_RuntimeSuperclassABI = 1
    def __init__(self,*args,**kwargs):
        selected=kwargs.pop('_nc_java_constructor',_MENU_CTOR)
        if kwargs or tuple(selected)!=_MENU_CTOR or len(args)!=2:
            raise TypeError('AbstractContainerMenu requires MenuType/int constructor')
        if args[0] is not None and not isinstance(args[0],MenuType):
            raise TypeError('Menu constructor requires MenuType or null')
        if type(args[1]) is not int:
            raise TypeError('Menu constructor requires int window id')
        AbstractContainerMenu.__init__(self,args[0],args[1])

for _entry in _MENU_METHODS:
    setattr(_MenuRuntimeBase,_entry['name'],_method_adapter(_entry,AbstractContainerMenu))
_ADAPTERS[_MENU]=_MenuRuntimeBase
_BASE_TYPES[_MENU]=AbstractContainerMenu


# Item data constructors and reviewed non-world methods (official 1.21.1).
from minecraft.item import Item, ItemProperties, BlockItem
from minecraft.block import Block
from java_stdlib.lang import IllegalStateException
_ITEM='net.minecraft.world.item.Item';_PROPERTIES=_ITEM+'.Properties';_BLOCK_ITEM='net.minecraft.world.item.BlockItem'
_ITEM_METHODS=[dict(name=n,parameters=[],return_type=t,static=False,abstract=False,visibility='public') for n,t in (
 ('asItem',_ITEM),('getDefaultMaxStackSize','int'),('getCraftingRemainingItem',_ITEM),('getDefaultInstance','net.minecraft.world.item.ItemStack'),('getEnchantmentValue','int'))]
_ITEM_METHODS.append(dict(name='isValidRepairItem',parameters=[_STACK,_STACK],return_type='boolean',static=False,abstract=False,visibility='public'))
def _item_properties(properties):
    if properties is None:raise NullPointerException()
    if not isinstance(properties,ItemProperties):raise TypeError('Item requires Item.Properties')
    if properties._damage_present and properties.max_stack_size>1:raise IllegalStateException('Item cannot have both durability and be stackable')
    return copy.copy(properties)
class _ItemRuntimeBase(Item):
    _nc_RuntimeSuperclassABI=1
    def __init__(self,*args,**kwargs):
        selected=kwargs.pop('_nc_java_constructor',(_PROPERTIES,))
        if kwargs or tuple(selected)!=(_PROPERTIES,) or len(args)!=1:raise TypeError('Item constructor signature mismatch')
        Item.__init__(self,_item_properties(args[0]))
for _entry in _ITEM_METHODS:setattr(_ItemRuntimeBase,_entry['name'],_method_adapter(_entry,Item))
_ITEM_RESERVED=[n for cls in (Item,Item.__bases__[0]) for n in cls.__dict__ if n not in [m['name'] for m in _ITEM_METHODS]+['getDescriptionId','equals','hashCode']]+['properties','_identifier','_id','_registry_name','_nc_RuntimeSuperclassABI']
_CONTRACTS[_ITEM]=dict(abi=1,helper_abi=6,java_name=_ITEM,abstract=False,constructors=[[_PROPERTIES]],constructor_visibility='public',methods=_ITEM_METHODS,reserved_members=sorted(set(_ITEM_RESERVED)))
_ADAPTERS[_ITEM]=_ItemRuntimeBase;_BASE_TYPES[_ITEM]=Item
_BLOCK_ITEM_METHODS=_ITEM_METHODS+[dict(name='getBlock',parameters=[],return_type='net.minecraft.world.level.block.Block',static=False,abstract=False,visibility='public')]
_BLOCK_ITEM_METHODS.append(dict(name='updatePlacementContext',parameters=['net.minecraft.world.item.context.BlockPlaceContext'],return_type='net.minecraft.world.item.context.BlockPlaceContext',static=False,abstract=False,visibility='public'))
class _BlockItemRuntimeBase(BlockItem,_ItemRuntimeBase):
    _nc_RuntimeSuperclassABI=1
    def __init__(self,*args,**kwargs):
        selected=kwargs.pop('_nc_java_constructor',('net.minecraft.world.level.block.Block',_PROPERTIES))
        if kwargs or tuple(selected)!=('net.minecraft.world.level.block.Block',_PROPERTIES) or len(args)!=2:raise TypeError('BlockItem constructor signature mismatch')
        if args[0] is not None and not isinstance(args[0],Block):raise TypeError('BlockItem requires a Block')
        BlockItem.__init__(self,args[0],_item_properties(args[1]))
for _entry in _BLOCK_ITEM_METHODS:setattr(_BlockItemRuntimeBase,_entry['name'],_method_adapter(_entry,BlockItem))
_CONTRACTS[_BLOCK_ITEM]=dict(abi=1,helper_abi=6,java_name=_BLOCK_ITEM,abstract=False,constructors=[['net.minecraft.world.level.block.Block',_PROPERTIES]],constructor_visibility='public',methods=_BLOCK_ITEM_METHODS,reserved_members=sorted(set(_ITEM_RESERVED+['_block'])))
_ADAPTERS[_BLOCK_ITEM]=_BlockItemRuntimeBase;_BASE_TYPES[_BLOCK_ITEM]=BlockItem

from minecraft.tiered_item import TieredItem
_TIERED='net.minecraft.world.item.TieredItem';_TIER='net.minecraft.world.item.Tier'
_TIERED_METHODS=_ITEM_METHODS+[dict(name='getTier',parameters=[],return_type=_TIER,static=False,abstract=False,visibility='public')]
class _TieredItemRuntimeBase(TieredItem,_ItemRuntimeBase):
    _nc_RuntimeSuperclassABI=1
    def __init__(self,*args,**kwargs):
        selected=kwargs.pop('_nc_java_constructor',(_TIER,_PROPERTIES))
        if kwargs or tuple(selected)!=(_TIER,_PROPERTIES) or len(args)!=2:raise TypeError('TieredItem constructor signature mismatch')
        if args[0] is None or args[1] is None:raise NullPointerException()
        if not isinstance(args[0],TOOL_TYPES[_TIER]):raise TypeError('TieredItem requires Tier')
        # Vanilla mutates the caller's builder before Item snapshots its data.
        # Validate the stack/damage invariant after that mutation.
        TieredItem.__init__(self,args[0],args[1])
        self.properties=_item_properties(self.properties)
for _entry in _TIERED_METHODS:setattr(_TieredItemRuntimeBase,_entry['name'],_method_adapter(_entry,TieredItem))
_CONTRACTS[_TIERED]=dict(abi=1,helper_abi=7,java_name=_TIERED,abstract=False,superclass=_ITEM,constructors=[[_TIER,_PROPERTIES]],constructor_visibility='public',methods=_TIERED_METHODS,reserved_members=sorted(set(_ITEM_RESERVED+['_tier'])))
_ADAPTERS[_TIERED]=_TieredItemRuntimeBase;_BASE_TYPES[_TIERED]=TieredItem

from minecraft.tiered_item import DiggerItem
from minecraft.registries import TagKey
_DIGGER='net.minecraft.world.item.DiggerItem';_DIGGER_TAG='net.minecraft.tags.TagKey<net.minecraft.world.level.block.Block>'
_DIGGER_METHODS=_TIERED_METHODS+[dict(name='hurtEnemy',parameters=[_STACK,'net.minecraft.world.entity.LivingEntity','net.minecraft.world.entity.LivingEntity'],return_type='boolean',static=False,abstract=False,visibility='public')]
class _DiggerItemRuntimeBase(DiggerItem,_TieredItemRuntimeBase):
    _nc_RuntimeSuperclassABI=1
    def __init__(self,*args,**kwargs):
        selected=kwargs.pop('_nc_java_constructor',(_TIER,_DIGGER_TAG,_PROPERTIES))
        if kwargs or tuple(selected)!=(_TIER,_DIGGER_TAG,_PROPERTIES) or len(args)!=3:raise TypeError('DiggerItem constructor signature mismatch')
        if args[0] is None or args[2] is None:raise NullPointerException()
        if not isinstance(args[0],TOOL_TYPES[_TIER]) or not isinstance(args[2],ItemProperties):raise TypeError('DiggerItem requires Tier and Item.Properties')
        if args[1] is not None and not isinstance(args[1],TagKey):raise TypeError('DiggerItem requires a block tag')
        DiggerItem.__init__(self,*args)
        self.properties=_item_properties(self.properties)
for _entry in _DIGGER_METHODS:setattr(_DiggerItemRuntimeBase,_entry['name'],_method_adapter(_entry,DiggerItem))
_CONTRACTS[_DIGGER]=dict(abi=1,helper_abi=7,java_name=_DIGGER,abstract=False,superclass=_TIERED,constructors=[[_TIER,_DIGGER_TAG,_PROPERTIES]],constructor_visibility='protected',methods=_DIGGER_METHODS,reserved_members=sorted(set(_ITEM_RESERVED+['_tier'])))
_ADAPTERS[_DIGGER]=_DiggerItemRuntimeBase;_BASE_TYPES[_DIGGER]=DiggerItem

from minecraft.tiered_item import SwordItem
_SWORD='net.minecraft.world.item.SwordItem'
class _SwordItemRuntimeBase(SwordItem,_TieredItemRuntimeBase):
    _nc_RuntimeSuperclassABI=1
    def __init__(self,*args,**kwargs):
        selected=kwargs.pop('_nc_java_constructor',(_TIER,_PROPERTIES))
        if kwargs or tuple(selected)!=(_TIER,_PROPERTIES) or len(args)!=2:raise TypeError('SwordItem constructor signature mismatch')
        if args[0] is None or args[1] is None:raise NullPointerException()
        if not isinstance(args[0],TOOL_TYPES[_TIER]) or not isinstance(args[1],ItemProperties):raise TypeError('SwordItem requires Tier and Item.Properties')
        SwordItem.__init__(self,*args)
        self.properties=_item_properties(self.properties)
for _entry in _DIGGER_METHODS:setattr(_SwordItemRuntimeBase,_entry['name'],_method_adapter(_entry,SwordItem))
_CONTRACTS[_SWORD]=dict(abi=1,helper_abi=7,java_name=_SWORD,abstract=False,superclass=_TIERED,constructors=[[_TIER,_PROPERTIES]],constructor_visibility='public',methods=_DIGGER_METHODS,reserved_members=sorted(set(_ITEM_RESERVED+['_tier'])))
_ADAPTERS[_SWORD]=_SwordItemRuntimeBase;_BASE_TYPES[_SWORD]=SwordItem


# BlockEntity state/lifecycle data only. Saving component codecs, world dirty
# notifications and protected field access need their own reviewed adapters.
from minecraft.block_entity import BlockEntity
from minecraft.core import BlockPos
from minecraft.official_interfaces import _invoke as _interface_invoke
_BE='net.minecraft.world.level.block.entity.BlockEntity'
_BE_TYPE=_BE+'Type'
_STATE='net.minecraft.world.level.block.state.BlockState'
_POS='net.minecraft.core.BlockPos'
_LEVEL='net.minecraft.world.level.Level'
_PROVIDER='net.minecraft.core.HolderLookup.Provider'
_TAG='net.minecraft.nbt.CompoundTag'
_BE_ROWS=[('getBlockPos',[],_POS,'public'),('getBlockState',[],_STATE,'public'),('getType',[],_BE_TYPE,'public'),
 ('getLevel',[],_LEVEL,'public'),('setLevel',[_LEVEL],'void','public'),('hasLevel',[],'boolean','public'),
 ('isValidBlockState',[_STATE],'boolean','public'),('setBlockState',[_STATE],'void','public'),
 ('isRemoved',[],'boolean','public'),('setRemoved',[],'void','public'),('clearRemoved',[],'void','public'),
 ('loadAdditional',[_TAG,_PROVIDER],'void','protected'),('saveAdditional',[_TAG,_PROVIDER],'void','protected'),
 ('getUpdateTag',[_PROVIDER],_TAG,'public'),('triggerEvent',['int','int'],'boolean','public'),('onlyOpCanSetNbt',[],'boolean','public')]
_BE_METHODS=[dict(name=n,parameters=args,return_type=result,visibility=visibility,static=False,abstract=False) for n,args,result,visibility in _BE_ROWS]
class _BlockEntityRuntimeBase(BlockEntity):
    _nc_RuntimeSuperclassABI=1
    def __init__(self,*args,**kwargs):
        signature=kwargs.pop('_nc_java_constructor',(_BE_TYPE,_POS,_STATE))
        if kwargs or tuple(signature)!=(_BE_TYPE,_POS,_STATE) or len(args)!=3:raise TypeError('BlockEntity constructor signature mismatch')
        if args[1] is None:raise NullPointerException()
        BlockEntity.__init__(self,args[0],args[1],None)
        if not _interface_invoke(self,'isValidBlockState',(args[2],),(_STATE,)):raise IllegalStateException('Invalid block entity state')
        self._block_state=args[2]
for _entry in _BE_METHODS:setattr(_BlockEntityRuntimeBase,_entry['name'],_method_adapter(_entry,BlockEntity))
_BE_NAMES=[m['name'] for m in _BE_METHODS]
_BE_RESERVED=[n for n in BlockEntity.__dict__ if n not in _BE_NAMES]+['_type','_pos','_block_state','_level','_removed','_nc_RuntimeSuperclassABI']
_CONTRACTS[_BE]=dict(abi=1,helper_abi=7,java_name=_BE,abstract=True,constructors=[[_BE_TYPE,_POS,_STATE]],constructor_visibility='public',methods=_BE_METHODS,reserved_members=sorted(set(_BE_RESERVED)))
_ADAPTERS[_BE]=_BlockEntityRuntimeBase;_BASE_TYPES[_BE]=BlockEntity


class RuntimeClasses(object):
    ABI_VERSION = 7

    @staticmethod
    def genericInterfaces():return copy.deepcopy(GENERIC_INTERFACES)
    @staticmethod
    def bindGenericInterface(java_name,arguments,expected):
        actual=specialize(java_name,arguments)
        if actual!=expected:raise RuntimeError('Generic runtime interface contract mismatch')
        return GENERIC_TYPES[java_name]
    @staticmethod
    def interfaceContracts():
        return copy.deepcopy(INTERFACE_CONTRACTS)

    @staticmethod
    def invokeInterface(contract, receiver, name, signature, arguments):
        binding=contract.get('generic_binding')
        base=(RuntimeClasses.bindGenericInterface(binding['java_name'],binding['arguments'],contract)
              if binding else RuntimeClasses.bindInterface(contract['java_name'],contract))
        if receiver is None:raise NullPointerException()
        selected=next((row for row in contract['methods'] if row['name']==name and tuple(row['parameters'])==tuple(signature)),None)
        if selected is None or len(arguments)!=len(signature) or not isinstance(receiver,base):
            raise TypeError('Unreviewed runtime interface invocation: '+name)
        target=getattr(receiver,name)
        if getattr(type(receiver),'_nc_JavaMethodsABI',0)==1:
            return target(*arguments,**{'_nc_java_signature':tuple(signature)})
        return target(*arguments)

    @staticmethod
    def bindInterface(java_name, expected):
        if java_name not in INTERFACE_CONTRACTS or expected != INTERFACE_CONTRACTS[java_name]:
            raise RuntimeError('Unreviewed NeoCore runtime interface: ' + java_name)
        return INTERFACE_TYPES[java_name]

    @staticmethod
    def contracts():
        return copy.deepcopy(_CONTRACTS)

    @staticmethod
    def bind(java_name, expected):
        actual = _CONTRACTS.get(java_name)
        if (actual is None or expected.get('abi') != 1 or expected.get('java_name') != java_name or
                expected.get('superclass') != actual.get('superclass') or
                expected.get('abstract') != actual['abstract'] or expected.get('fields',[]) != actual.get('fields',[])):
            raise RuntimeError('Unreviewed NeoCore runtime superclass: ' + java_name)
        if (not all(row in actual['methods'] for row in expected.get('methods', [])) or
                not all(row in expected.get('methods', []) for row in actual['methods'] if row['abstract']) or
                not all(row in actual['constructors'] for row in expected.get('constructors', [])) or
                not set(actual['reserved_members']).issubset(set(expected.get('reserved_members', [])))):
            raise RuntimeError('NeoCore runtime superclass contract changed: ' + java_name)
        return _ADAPTERS[java_name]

    @staticmethod
    def invoke(java_name, receiver, name, signature, arguments):
        if receiver is None:
            raise NullPointerException()
        contract = _CONTRACTS.get(java_name)
        selected = next((row for row in contract['methods'] if row['name'] == name and
            tuple(row['parameters']) == tuple(signature)), None) if contract else None
        if selected is None or selected['static'] or len(arguments) != len(signature) or not isinstance(receiver, _BASE_TYPES[java_name]):
            raise TypeError('Unreviewed runtime superclass invocation: ' + name)
        method = getattr(receiver, name)
        if isinstance(receiver, _ADAPTERS[java_name]) or getattr(type(receiver), '_nc_JavaMethodsABI', 0) == 1:
            return method(*arguments, **{'_nc_java_signature': tuple(signature)})
        return method(*arguments)


    @staticmethod
    def invokeStatic(java_name, name, signature, arguments):
        contract = _CONTRACTS.get(java_name)
        selected = next((row for row in contract['methods'] if row['name'] == name and
            tuple(row['parameters']) == tuple(signature)), None) if contract else None
        if selected is None or not selected['static'] or len(arguments) != len(signature):
            raise TypeError('Unreviewed runtime superclass static invocation: ' + name)
        return getattr(_ADAPTERS[java_name], name)(*arguments,
            **{'_nc_java_signature': tuple(signature)})


JAVA_MAP = {'neocore.runtime.RuntimeClasses': RuntimeClasses}
