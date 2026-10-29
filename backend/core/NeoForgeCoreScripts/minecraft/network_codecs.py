# -*- coding: utf-8 -*-
"""Original UUID/BlockPos codecs and reviewed primitive codec constants."""
from __future__ import absolute_import
from java_stdlib.lang import Integer, Boolean, NullPointerException, RuntimeException
from java_stdlib.util import UUID
from java_stdlib.java_arrays import JavaArray
from neoforge.network import StreamCodec
from minecraft.core import BlockPos
from minecraft.utf8_codec import read as _utf_read,write as _utf_write
from neoforge.registries import ResourceLocation

def _uuid_encode(buffer,value):
    if value is None:raise NullPointerException()
    buffer.writeLong(value.getMostSignificantBits());buffer.writeLong(value.getLeastSignificantBits())
def _uuid_decode(buffer):return UUID(buffer.readLong(),buffer.readLong())
class UUIDUtil(object):
    UUID_BYTES=16
    STREAM_CODEC=StreamCodec(_uuid_encode,_uuid_decode)
    @staticmethod
    def uuidToIntArray(value):
        if value is None:raise NullPointerException()
        m=value.getMostSignificantBits();l=value.getLeastSignificantBits()
        def signed(n):n&=0xffffffff;return n-(1<<32) if n&(1<<31) else n
        return JavaArray('int',1,[signed(m>>32),signed(m),signed(l>>32),signed(l)])
    @staticmethod
    def uuidFromIntArray(value):
        if value is None:raise NullPointerException()
        return UUID((value[0]<<32)|(value[1]&0xffffffff),(value[2]<<32)|(value[3]&0xffffffff))
def _block_decode(buffer):
    value=buffer.readLong()
    def signed(n,bits):n&=(1<<bits)-1;return n-(1<<bits) if n&(1<<(bits-1)) else n
    return BlockPos(signed(value>>38,26),signed(value,12),signed(value>>12,26))
BlockPos.STREAM_CODEC=StreamCodec(lambda buffer,value:buffer.writeLong(value.asLong()),_block_decode)
def _int(value):return value.intValue() if hasattr(value,'intValue') else int(value)
def _var_write(buffer,value):
    value=_int(value)&0xffffffff
    while value&~127:buffer.writeByte((value&127)|128);value>>=7
    buffer.writeByte(value)
def _var_read(buffer):
    value=0
    for index in range(5):
        n=buffer.readUnsignedByte();value|=(n&127)<<(7*index)
        if not n&128:
            value&=0xffffffff;return Integer.valueOf(value-(1<<32) if value&(1<<31) else value)
    raise RuntimeException('VarInt too big')
class ByteBufCodecs(object):
    BOOL=StreamCodec(lambda b,v:b.writeBoolean(v.booleanValue() if hasattr(v,'booleanValue') else v),lambda b:Boolean.valueOf(b.readBoolean()))
    INT=StreamCodec(lambda b,v:b.writeInt(_int(v)),lambda b:Integer.valueOf(b.readInt()))
    VAR_INT=StreamCodec(_var_write,_var_read)
    @staticmethod
    def stringUtf8(maximum):return StreamCodec(lambda b,v:_utf_write(b,v,maximum),lambda b:_utf_read(b,maximum))
    STRING_UTF8=StreamCodec(lambda b,v:_utf_write(b,v,32767),lambda b:_utf_read(b,32767))

def _resource_encode(buffer,value):
    if value is None:raise NullPointerException()
    ByteBufCodecs.STRING_UTF8.encode(buffer,value.toString())
ResourceLocation.STREAM_CODEC=StreamCodec(_resource_encode,lambda b:ResourceLocation.parse(ByteBufCodecs.STRING_UTF8.decode(b)))
JAVA_MAP={'net.minecraft.core.UUIDUtil':UUIDUtil,'net.minecraft.network.codec.ByteBufCodecs':ByteBufCodecs}
