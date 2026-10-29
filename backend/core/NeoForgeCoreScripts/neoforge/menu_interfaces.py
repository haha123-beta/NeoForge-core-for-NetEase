# -*- coding: utf-8 -*-
"""NeoForge public menu factory interfaces and their original null-data default."""
from __future__ import absolute_import
from minecraft.official_interfaces import _declare,method,_invoke
from minecraft.feature_flags import FeatureFlags

MENU='net.minecraft.world.inventory.AbstractContainerMenu'
TYPE='net.minecraft.world.inventory.MenuType'
SUPPLIER=TYPE+'.MenuSupplier'
FACTORY='net.neoforged.neoforge.network.IContainerFactory'
EXTENSION='net.neoforged.neoforge.common.extensions.IMenuTypeExtension'
INVENTORY='net.minecraft.world.entity.player.Inventory'
BUFFER='net.minecraft.network.RegistryFriendlyByteBuf'
GENERIC_INTERFACES={}
GENERIC_TYPES={}
_REGISTRY=(GENERIC_INTERFACES,GENERIC_TYPES)
MenuSupplier=_declare(SUPPLIER,[method('create',['int',INVENTORY],'T')],parameters=['T'],bounds={'T':MENU},registry=_REGISTRY)
def _create(self,*args,**kwargs):
    signature=kwargs.pop('_nc_java_signature',None)
    if kwargs:raise TypeError('Unexpected menu factory keyword')
    if len(args)==2 and (signature is None or tuple(signature)==('int',INVENTORY)):
        return _invoke(self,'create',(args[0],args[1],None),('int',INVENTORY,BUFFER))
    raise NotImplementedError('IContainerFactory requires create(int, Inventory, RegistryFriendlyByteBuf)')
IContainerFactory=_declare(FACTORY,[method('create',['int',INVENTORY],'T',True),method('create',['int',INVENTORY,BUFFER],'T')],parameters=['T'],bounds={'T':MENU},bases=(MenuSupplier,),defaults={'create':_create},registry=_REGISTRY)
GENERIC_INTERFACES[FACTORY]['superinterfaces']=[SUPPLIER]
IMenuTypeExtension=_declare(EXTENSION,[method('create',['int',INVENTORY,BUFFER],'T')],parameters=['T'],registry=_REGISTRY)
def _new_type(factory):
    from minecraft.menu import MenuType
    return MenuType(factory,features=FeatureFlags.DEFAULT_FLAGS)
IMenuTypeExtension._nc_createType=staticmethod(_new_type)
for _contract in GENERIC_INTERFACES.values():_contract['helper_abi']=7
JAVA_MAP=dict(GENERIC_TYPES)
