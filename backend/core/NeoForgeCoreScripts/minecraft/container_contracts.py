# -*- coding: utf-8 -*-
"""Official Container and WorldlyContainer instance contracts and real defaults."""
from __future__ import absolute_import
from minecraft.official_interfaces import _declare, method, _invoke, Clearable
from java_stdlib.lang import NullPointerException
from java_stdlib.primitives import Int32

CONTAINER='net.minecraft.world.Container'
STACK='net.minecraft.world.item.ItemStack'
ITEM='net.minecraft.world.item.Item'
PLAYER='net.minecraft.world.entity.player.Player'
DIRECTION='net.minecraft.core.Direction'
INTERFACE_CONTRACTS={}
INTERFACE_TYPES={}
_REGISTRY=(INTERFACE_CONTRACTS,INTERFACE_TYPES)


def _max_stack(self,*args,**kwargs):
    if len(args)==0:return 99
    if len(args)!=1:raise TypeError('Container.getMaxStackSize arity')
    if args[0] is None:raise NullPointerException()
    return min(_invoke(self,'getMaxStackSize'),args[0].getMaxStackSize())


def _open(self,player,_nc_java_signature=None):return None
def _place(self,index,stack,_nc_java_signature=None):return True
def _take(self,source,index,stack,_nc_java_signature=None):return True


def _count(self,item,_nc_java_signature=None):
    count=0
    for index in range(_invoke(self,'getContainerSize')):
        stack=_invoke(self,'getItem',(index,),('int',))
        if stack is None:raise NullPointerException()
        found=stack.getItem()
        equal=found.equals(item) if found is not None and hasattr(found,'equals') else found is item
        if equal:count=Int32.add(count,stack.getCount())
    return count


def _matching(self,predicate,_nc_java_signature=None):
    for index in range(_invoke(self,'getContainerSize')):
        stack=_invoke(self,'getItem',(index,),('int',))
        if predicate is None:raise NullPointerException()
        if predicate.test(stack) if hasattr(predicate,'test') else predicate(stack):return True
    return False


def _any_of(self,items,_nc_java_signature=None):
    def test(stack):
        if stack is None:raise NullPointerException()
        if stack.isEmpty():return False
        if items is None:raise NullPointerException()
        return items.contains(stack.getItem())
    return _invoke(self,'hasAnyMatching',(test,),('java.util.function.Predicate<'+STACK+'>',))


_METHODS=[method('clearContent',[],'void'),method('getContainerSize',[],'int'),
    method('isEmpty',[],'boolean'),method('getItem',['int'],STACK),
    method('removeItem',['int','int'],STACK),method('removeItemNoUpdate',['int'],STACK),
    method('setItem',['int',STACK],'void'),method('setChanged',[],'void'),method('stillValid',[PLAYER],'boolean'),
    method('getMaxStackSize',[],'int',True),method('getMaxStackSize',[STACK],'int',True),
    method('startOpen',[PLAYER],'void',True),method('stopOpen',[PLAYER],'void',True),
    method('canPlaceItem',['int',STACK],'boolean',True),method('canTakeItem',[CONTAINER,'int',STACK],'boolean',True),
    method('countItem',[ITEM],'int',True),method('hasAnyOf',['java.util.Set<'+ITEM+'>'],'boolean',True),
    method('hasAnyMatching',['java.util.function.Predicate<'+STACK+'>'],'boolean',True)]
_DEFAULTS={'getMaxStackSize':_max_stack,'startOpen':_open,'stopOpen':_open,
    'canPlaceItem':_place,'canTakeItem':_take,'countItem':_count,'hasAnyOf':_any_of,'hasAnyMatching':_matching}
Container=_declare(CONTAINER,_METHODS,bases=(Clearable,),defaults=_DEFAULTS,registry=_REGISTRY)
WorldlyContainer=_declare('net.minecraft.world.WorldlyContainer',_METHODS+[
    method('getSlotsForFace',[DIRECTION],'int[]'),
    method('canPlaceItemThroughFace',['int',STACK,DIRECTION],'boolean'),
    method('canTakeItemThroughFace',['int',STACK,DIRECTION],'boolean')],bases=(Container,),defaults=_DEFAULTS,registry=_REGISTRY)
Container.DEFAULT_DISTANCE_BUFFER=4.0
WorldlyContainer.DEFAULT_DISTANCE_BUFFER=4.0

for _name,_contract in INTERFACE_CONTRACTS.items():
    _contract['helper_abi']=7
    _contract['superinterfaces']=['net.minecraft.world.Clearable']+([CONTAINER] if _name!=CONTAINER else [])
JAVA_MAP=dict(INTERFACE_TYPES)
