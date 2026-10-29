# -*- coding: utf-8 -*-
"""Exact ordinary Block/BlockItem receipt; native placement uses block definitions.

Java BlockItem.place remains a separate unsupported Java-call boundary.
"""
from __future__ import absolute_import
from minecraft.block import Block, BlockProperties, SoundType
from minecraft.item import BlockItem

def exact_block_item(value):
    if type(value) is BlockItem:return True
    from minecraft.runtime_classes import RuntimeClasses
    name='net.minecraft.world.item.BlockItem'
    return type(value) is RuntimeClasses.bind(name,RuntimeClasses.contracts()[name])

def describe(value,registry):
    if type(value) is not Block:raise ValueError('Only exact ordinary Block supports the cube target profile')
    if value.getStateDefinition() or value._air:raise ValueError('Stateful/air block requires a reviewed target adapter')
    shape=value.getShape()
    if tuple(getattr(shape,key,None) for key in ('minX','minY','minZ','maxX','maxY','maxZ'))!=(0,0,0,1,1,1):raise ValueError('Non-cube collision requires a reviewed target adapter')
    defaults=BlockProperties().__dict__
    for key in set(defaults)|set(value.properties.__dict__):
        if key not in ('_destroy_time','_explosion_resistance','_sound') and value.properties.__dict__.get(key)!=defaults.get(key):
            raise ValueError('Unsupported ordinary block property: '+key)
    sound=value.properties._sound
    if sound is not SoundType.GRAVEL:raise ValueError('Block sound requires a reviewed target mapping')
    matches=[name for name,item in registry.items() if exact_block_item(item) and item.getBlock() is value and value.asItem() is item]
    if len(matches)!=1:raise ValueError('Ordinary block requires one registered linked exact BlockItem')
    return {'java_class':'net.minecraft.world.level.block.Block','item':matches[0],
            'destroy_time':value.properties._destroy_time,'explosion_resistance':value.properties._explosion_resistance,
            'sound':'gravel','shape':'cube','states':{}}

def validate(contracts,registries,api,server=True):
    expected={}
    for contract in contracts:
        for row in contract.get('blocks',[]):
            name=row['identifier']
            if name in expected or name.split(':')[0] not in contract['owners']:raise ValueError('Duplicate/foreign block ID')
            expected[name]=row
    if not expected:return {'status':'NOT_REQUESTED','engine_verified':False}
    blocks=registries.get('minecraft:block',{});items=registries.get('minecraft:item',{})
    namespaces=set(name.split(':')[0] for name in expected)
    if set(name for name in blocks if name.split(':')[0] in namespaces)!=set(expected):raise ValueError('Runtime block IDs differ from content receipt')
    comp=api.GetEngineCompFactory().CreateBlockInfo(api.GetLevelId()) if server and api is not None else None
    if server and not callable(getattr(comp,'GetBlockBasicInfo',None)):raise RuntimeError('GetBlockBasicInfo unavailable; native block definitions cannot be verified')
    for name,row in expected.items():
        actual=describe(blocks[name],items)
        if dict(actual,identifier=name)!=dict((k,v) for k,v in row.items() if k not in ('target','loot')):raise ValueError('Registered block properties differ: '+name)
        if server:
            info=comp.GetBlockBasicInfo(name)
            if not isinstance(info,dict):raise ValueError('Native block definition missing: '+name)
            for key,source in (('destroyTime','destroy_time'),('explosionResistance','explosion_resistance')):
                if key not in info or abs(info[key]-row['target'][source])>0.00001:raise ValueError('Native block property differs: '+name+':'+key)
    return {'status':'NATIVE_BLOCK_DEFINITIONS_QUERIED' if server else 'BLOCK_RECEIPT_CHECKED_CLIENT',
            'blocks':sorted(expected),'engine_verified':False,'gameplay_verification':'PENDING_REAL_ENGINE'}
