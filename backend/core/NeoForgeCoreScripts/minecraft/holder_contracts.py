# -*- coding: utf-8 -*-
"""Official generic holder lookup defaults; implementations supply both lookups."""
from __future__ import absolute_import
from minecraft.official_interfaces import _declare,method,_invoke
from java_stdlib.lang import NullPointerException,IllegalStateException,java_to_string

GENERIC_INTERFACES={}
GENERIC_TYPES={}
GETTER='net.minecraft.core.HolderGetter'
KEY='net.minecraft.resources.ResourceKey<T>'
TAG='net.minecraft.tags.TagKey<T>'
REFERENCE='net.minecraft.core.Holder.Reference<T>'
NAMED='net.minecraft.core.HolderSet.Named<T>'

def _get_or_throw(self,key,_nc_java_signature=None):
    signature=tuple(_nc_java_signature or ())
    if not signature:
        from minecraft.registries import TagKey
        signature=(TAG if isinstance(key,TagKey) else KEY,)
    result=_invoke(self,'get',(key,),signature)
    if result is None:raise NullPointerException()
    if result.isPresent():return result.get()
    prefix='Missing tag ' if signature[0].split('<',1)[0]=='net.minecraft.tags.TagKey' else 'Missing element '
    raise IllegalStateException(prefix+java_to_string(key))

HolderGetter=_declare(GETTER,[
 method('get',[KEY],'java.util.Optional<'+REFERENCE+'>'),
 method('getOrThrow',[KEY],REFERENCE,True),
 method('get',[TAG],'java.util.Optional<'+NAMED+'>'),
 method('getOrThrow',[TAG],NAMED,True)],parameters=['T'],
 defaults={'getOrThrow':_get_or_throw},registry=(GENERIC_INTERFACES,GENERIC_TYPES))
GENERIC_INTERFACES[GETTER]['helper_abi']=7
JAVA_MAP=dict(GENERIC_TYPES)
