# -*- coding: utf-8 -*-
"""Reviewed public 1.21.1 interfaces. Abstract methods never imply an implementation.

Static factories and unrelated renderer/world APIs are deliberately outside these
instance contracts. Signatures are checked against the pinned official client jar.
"""
from __future__ import absolute_import

INTERFACE_CONTRACTS = {}
INTERFACE_TYPES = {}
GENERIC_INTERFACES = {}
GENERIC_TYPES = {}


def method(name, args, result, default=False):
    return dict(name=name, parameters=args, return_type=result, static=False,
                abstract=not default, visibility='public')


def _abstract(name):
    def call(self, *args, **kwargs):
        raise NotImplementedError('Abstract official interface method: ' + name)
    return call


def _declare(identity, methods, parameters=None, bases=(), defaults=None, bounds=None, registry=None):
    attrs = {'__module__': __name__}
    for row in methods:
        attrs[row['name']] = (defaults or {}).get(row['name'], _abstract(row['name']))
    cls = type(str(identity.rsplit('.', 1)[-1]), bases or (object,), attrs)
    def init(self):
        if type(self) is cls:
            raise TypeError(identity + ' is an interface')
    cls.__init__ = init
    contract = dict(abi=1, helper_abi=6, java_name=identity, methods=methods)
    if parameters:
        contract['type_parameters'] = parameters
        if bounds: contract['type_bounds'] = bounds
        contracts,types=registry or (GENERIC_INTERFACES,GENERIC_TYPES)
    else:
        contracts,types=registry or (INTERFACE_CONTRACTS,INTERFACE_TYPES)
    contracts[identity]=contract
    types[identity]=cls
    return cls


def _invoke(value, name, args=(), signature=()):
    fn = getattr(value, name)
    if getattr(type(value), '_nc_JavaMethodsABI', 0) == 1:
        return fn(*args, **{'_nc_java_signature': signature})
    return fn(*args)


STACK = 'net.minecraft.world.item.ItemStack'
COMPONENT = 'net.minecraft.network.chat.Component'
MENU = 'net.minecraft.world.inventory.AbstractContainerMenu'
PLAYER = 'net.minecraft.world.entity.player.Player'
INVENTORY = 'net.minecraft.world.entity.player.Inventory'
STATE = 'net.minecraft.world.level.block.state.BlockState'
POS = 'net.minecraft.core.BlockPos'

Clearable = _declare('net.minecraft.world.Clearable', [method('clearContent', [], 'void')])
ContainerData = _declare('net.minecraft.world.inventory.ContainerData', [
    method('get', ['int'], 'int'), method('set', ['int', 'int'], 'void'), method('getCount', [], 'int')])
ContainerListener = _declare('net.minecraft.world.inventory.ContainerListener', [
    method('slotChanged', [MENU, 'int', STACK], 'void'), method('dataChanged', [MENU, 'int', 'int'], 'void')])
ContainerSynchronizer = _declare('net.minecraft.world.inventory.ContainerSynchronizer', [
    method('sendInitialData', [MENU, 'net.minecraft.core.NonNullList<'+STACK+'>', STACK, 'int[]'], 'void'),
    method('sendSlotChange', [MENU, 'int', STACK], 'void'), method('sendCarriedChange', [MENU, STACK], 'void'),
    method('sendDataChange', [MENU, 'int', 'int'], 'void')])
_MENU_METHOD = method('createMenu', ['int', INVENTORY, PLAYER], MENU)
MenuConstructor = _declare('net.minecraft.world.inventory.MenuConstructor', [_MENU_METHOD])
# MenuProvider extends MenuConstructor; retain both requirements and native identity.
MenuProvider = _declare('net.minecraft.world.MenuProvider', [
    _MENU_METHOD, method('getDisplayName', [], COMPONENT)], bases=(MenuConstructor,))
INTERFACE_CONTRACTS['net.minecraft.world.MenuProvider']['superinterfaces'] = ['net.minecraft.world.inventory.MenuConstructor']
ItemLike = _declare('net.minecraft.world.level.ItemLike', [method('asItem', [], 'net.minecraft.world.item.Item')])
Position = _declare('net.minecraft.core.Position', [method(k, [], 'double') for k in ('x', 'y', 'z')])
OnPress = _declare('net.minecraft.client.gui.components.Button.OnPress', [
    method('onPress', ['net.minecraft.client.gui.components.Button'], 'void')])
CreateNarration = _declare('net.minecraft.client.gui.components.Button.CreateNarration', [
    method('createNarrationMessage', ['java.util.function.Supplier<net.minecraft.network.chat.MutableComponent>'],
           'net.minecraft.network.chat.MutableComponent')])
TooltipProvider = _declare('net.minecraft.world.item.component.TooltipProvider', [
    method('addToTooltip', ['net.minecraft.world.item.Item.TooltipContext',
           'java.util.function.Consumer<'+COMPONENT+'>', 'net.minecraft.world.item.TooltipFlag'], 'void')])
StringRepresentable = _declare('net.minecraft.util.StringRepresentable', [method('getSerializedName', [], 'java.lang.String')])
BakedModel = _declare('net.minecraft.client.resources.model.BakedModel', [
    method('getQuads', [STATE, 'net.minecraft.core.Direction', 'net.minecraft.util.RandomSource'],
           'java.util.List<net.minecraft.client.renderer.block.model.BakedQuad>'),
    method('useAmbientOcclusion', [], 'boolean'), method('isGui3d', [], 'boolean'),
    method('usesBlockLight', [], 'boolean'), method('isCustomRenderer', [], 'boolean'),
    method('getParticleIcon', [], 'net.minecraft.client.renderer.texture.TextureAtlasSprite'),
    method('getTransforms', [], 'net.minecraft.client.renderer.block.model.ItemTransforms'),
    method('getOverrides', [], 'net.minecraft.client.renderer.block.model.ItemOverrides')])


def _has_custom(self, _nc_java_signature=None):
    return _invoke(self, 'getCustomName') is not None


def _display_name(self, _nc_java_signature=None):
    return _invoke(self, 'getName')


def _custom_name(self, _nc_java_signature=None):
    return None


Nameable = _declare('net.minecraft.world.Nameable', [method('getName', [], COMPONENT),
    method('hasCustomName', [], 'boolean', True), method('getDisplayName', [], COMPONENT, True),
    method('getCustomName', [], COMPONENT, True)], defaults={
    'hasCustomName': _has_custom, 'getDisplayName': _display_name, 'getCustomName': _custom_name})


def _recipe_empty(self, _nc_java_signature=None):
    for index in range(_invoke(self, 'size')):
        stack = _invoke(self, 'getItem', (index,), ('int',))
        if stack is None:
            from java_stdlib.lang import NullPointerException
            raise NullPointerException()
        if not stack.isEmpty(): return False
    return True


RecipeInput = _declare('net.minecraft.world.item.crafting.RecipeInput', [
    method('getItem', ['int'], STACK), method('size', [], 'int'), method('isEmpty', [], 'boolean', True)],
    defaults={'isEmpty': _recipe_empty})
BlockEntityTicker = _declare('net.minecraft.world.level.block.entity.BlockEntityTicker', [
    method('tick', ['net.minecraft.world.level.Level', POS, STATE, 'T'], 'void')], ['T'],
    bounds={'T': 'net.minecraft.world.level.block.entity.BlockEntity'})
StreamEncoder = _declare('net.minecraft.network.codec.StreamEncoder', [method('encode', ['O', 'T'], 'void')], ['O', 'T'])
StreamDecoder = _declare('net.minecraft.network.codec.StreamDecoder', [method('decode', ['I'], 'T')], ['I', 'T'])

Renderable = _declare('net.minecraft.client.gui.components.Renderable', [
    method('render', ['net.minecraft.client.gui.GuiGraphics', 'int', 'int', 'float'], 'void')])
NarrationSupplier = _declare('net.minecraft.client.gui.narration.NarrationSupplier', [
    method('updateNarration', ['net.minecraft.client.gui.narration.NarrationElementOutput'], 'void')])


def _tab_order(self, _nc_java_signature=None): return 0
def _active(self, _nc_java_signature=None): return True


_TAB_METHOD = method('getTabOrderGroup', [], 'int', True)
TabOrderedElement = _declare('net.minecraft.client.gui.components.TabOrderedElement', [_TAB_METHOD],
    defaults={'getTabOrderGroup': _tab_order})
NarratableEntry = _declare('net.minecraft.client.gui.narration.NarratableEntry', [
    method('narrationPriority', [], 'net.minecraft.client.gui.narration.NarratableEntry.NarrationPriority'),
    method('updateNarration', ['net.minecraft.client.gui.narration.NarrationElementOutput'], 'void'),
    _TAB_METHOD, method('isActive', [], 'boolean', True)], bases=(TabOrderedElement, NarrationSupplier),
    defaults={'getTabOrderGroup': _tab_order, 'isActive': _active})
INTERFACE_CONTRACTS['net.minecraft.client.gui.narration.NarratableEntry']['superinterfaces'] = [
    'net.minecraft.client.gui.components.TabOrderedElement', 'net.minecraft.client.gui.narration.NarrationSupplier']

JAVA_MAP = dict(INTERFACE_TYPES, **GENERIC_TYPES)
