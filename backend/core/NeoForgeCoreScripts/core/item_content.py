# -*- coding: utf-8 -*-
"""Bind registered Java objects to already-loaded NetEase item definitions.

This does not create engine definitions or certify gameplay. Python 2 compatible.
"""
from __future__ import absolute_import
from minecraft.modsdk_container import NativeItemCodec
from minecraft.item import Item, BlockItem


def describe(value):
    if not isinstance(value, Item):
        raise ValueError('Registered object is not an Item')
    java_name = type(value).__dict__.get('_nc_JavaName')
    if type(value) is Item:
        java_name = 'net.minecraft.world.item.Item'
    if type(value) is BlockItem:
        java_name = 'net.minecraft.world.item.BlockItem'
    if java_name is None:
        from minecraft.runtime_classes import RuntimeClasses
        for name, contract in RuntimeClasses.contracts().items():
            if type(value) is RuntimeClasses.bind(name, contract):
                java_name = name
                break
    if java_name is None:
        raise ValueError('Registered Item has no reviewed Java class identity')
    row = {'java_class':java_name, 'max_stack_size':value.getDefaultMaxStackSize(),
            'unverified_behaviors':([] if java_name == 'net.minecraft.world.item.Item' else
                                     ['Subclass gameplay requires target bridge: ' + java_name])}
    proof = type(value).__dict__.get('_nc_ItemBehaviorBridge')
    if isinstance(proof,dict) and proof.get('abi') == 1 and proof.get('kind') == 'CONSTANT_FUEL_PRIVATE_FIELD':
        ticks = getattr(value,proof['field'])
        try:
            integer_types = (int,long)
        except NameError:
            integer_types = (int,)
        if not isinstance(ticks,integer_types) or isinstance(ticks,bool) or not 0 <= ticks <= 2147483647:
            raise ValueError('Proven fuel field has invalid Java tick value')
        row['fuel'] = {'ticks':ticks,'proof':dict(proof)}
        row['unverified_behaviors'] = []
    # The initial target profile only implements stack size and proven fuel.
    # Never discard other Properties while claiming a plain native item.
    properties = value.properties
    defaults = {'max_damage':0, '_damage_present':False, 'fire_resistant':False,
                '_rarity':'COMMON', '_unbreakable':False, '_food':None,
                '_custom_data':None, '_craft_remainder':None, '_tool_component':None}
    for name, default in defaults.items():
        if getattr(properties,name) != default:
            row['unverified_behaviors'].append('Unsupported item property: ' + name)
    known = set(defaults) | set(('max_stack_size',))
    for name in set(properties.__dict__) - known:
        row['unverified_behaviors'].append('Unknown item property: ' + name)
    return row


def creative_snapshot(contexts, registry, tab='INGREDIENTS'):
    from neoforge.creative import CreativeModeTabs, BuildCreativeModeTabContentsEvent
    event = BuildCreativeModeTabContentsEvent._for_bridge(getattr(CreativeModeTabs,tab))
    for context in contexts.values():
        context.mod_bus.post(event,strict=True)
    names = []
    for stack in event._parent.values:
        matches = [name for name,value in registry.items() if value is stack.getItem()]
        if len(matches) != 1:
            raise ValueError('Creative entry has no unique registered ID')
        names.append(matches[0])
    return names


def bind(contracts, registries, results, api):
    codec = NativeItemCodec()
    expected, namespaces, native_references = {}, set(), set()
    for contract in contracts:
        if contract.get('schema_version') != 1 or contract.get('profile') != 'netease_pc_item_1_10':
            raise ValueError('Unsupported native item binding contract')
        if contract.get('unconverted_content'):
            raise ValueError('Content still contains unconverted assets/data: ' + repr(contract['unconverted_content']))
        owners = contract.get('owners', [])
        if not owners or any(not results.get(owner, {}).get('ready') for owner in owners):
            raise ValueError('Native items require successfully activated original mod owners')
        namespaces.update(owners)
        for name in contract.get('native_items', []):
            if not name.startswith('minecraft:'):
                raise ValueError('Invalid native recipe item reference')
            native_references.add(name)
        for row in contract['items']:
            name = row['identifier']
            if name.split(':')[0] not in owners or name in expected:
                raise ValueError('Duplicate or foreign native item identity: ' + name)
            if row.get('unverified_behaviors'):
                raise ValueError('Required item behavior remains unverified: ' + name + ': ' +
                                 '; '.join(row['unverified_behaviors']))
            expected[name] = row
    actual = registries.get('minecraft:item', {})
    owned = set(name for name in actual if name.split(':')[0] in namespaces)
    if owned != set(expected):
        raise ValueError('Runtime item IDs differ from built definitions; missing=' +
                         repr(sorted(set(expected)-owned)) + '; extra=' + repr(sorted(owned-set(expected))))
    if not expected:
        return codec, {'status':'NO_NATIVE_ITEMS', 'engine_verified':False}
    if api is None:
        raise RuntimeError('NetEase item API unavailable; cannot verify native definitions')
    component = api.GetEngineCompFactory().CreateItem(api.GetLevelId())
    check = getattr(component, 'GetItemBasicInfo', None)
    if not callable(check):
        raise RuntimeError('GetItemBasicInfo unavailable on this target SDK')
    for name in sorted(native_references):
        if not isinstance(check(name,0,False),dict):
            raise ValueError('Native recipe item reference is unavailable: ' + name)
    for name, row in sorted(expected.items()):
        value = actual[name]
        if not isinstance(value, Item):
            raise ValueError('Registered object is not an Item: ' + name)
        actual_row = describe(value)
        if row.get('block'):
            from core.block_content import exact_block_item
            block_name=row['block']
            matched=[block for contract in contracts for block in contract.get('blocks',[]) if block['identifier']==block_name and block['item']==name]
            gap=['Subclass gameplay requires target bridge: net.minecraft.world.item.BlockItem']
            if (len(matched)!=1 or not exact_block_item(value) or value.getBlock() is not registries.get('minecraft:block',{}).get(block_name)
                    or actual_row['unverified_behaviors']!=gap):raise ValueError('BlockItem requires an exact matching ordinary block contract')
            actual_row['unverified_behaviors']=[]
        if actual_row['unverified_behaviors']:
            raise ValueError('Registered subclass behavior has no target adapter: ' + name)
        if (actual_row['java_class'] != row['java_class'] or actual_row['max_stack_size'] != row['max_stack_size']
                or actual_row.get('fuel') != row.get('fuel')):
            raise ValueError('Registered item class/properties differ from content definition: ' + name)
        info = check(name, 0, False)
        if not isinstance(info, dict) or info.get('maxStackSize') != row['max_stack_size']:
            raise ValueError('Native item definition absent or mismatched: ' + name)
        codec.register(value, name, 0)
    return codec, {'status':'NATIVE_IDS_BOUND', 'items':sorted(expected),
                   'definition_query_succeeded':True, 'engine_verified':False,
                   'limits':['Binding does not verify texture, recipes, fuel or persistence.']}
