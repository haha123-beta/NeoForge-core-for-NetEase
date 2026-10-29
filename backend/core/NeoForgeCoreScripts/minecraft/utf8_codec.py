# -*- coding: utf-8 -*-
"""Minecraft UTF8 string framing over the real ByteBuf, with Java UTF16 limits."""
from __future__ import absolute_import
from java_stdlib.lang import RuntimeException,NullPointerException,JavaString,_utf16_units,_utf16_text,_CHAR_FROM_CODE

class DecoderException(RuntimeException):pass
class EncoderException(RuntimeException):pass

def encode_units(value):
    units=[ord(c) for c in _utf16_units(value)];result=[];i=0
    while i<len(units):
        n=units[i];i+=1
        if n<128:result.append(n)
        elif n<2048:result.extend((192|(n>>6),128|(n&63)))
        elif 55296<=n<=57343:
            if n>56319 or i==len(units):result.append(63);continue
            second=units[i];i+=1
            if not 56320<=second<=57343:
                result.extend((63,63 if 55296<=second<=56319 else second&255));continue
            n=65536+((n-55296)<<10)+second-56320
            result.extend((240|(n>>18),128|((n>>12)&63),128|((n>>6)&63),128|(n&63)))
        else:result.extend((224|(n>>12),128|((n>>6)&63),128|(n&63)))
    return result

def decode_units(data):
    result=[];i=0
    while i<len(data):
        first=data[i];i+=1
        if first<128:result.append(_CHAR_FROM_CODE(first));continue
        size=2 if 194<=first<=223 else 3 if 224<=first<=239 else 4 if 240<=first<=244 else 0
        if not size:result.append(u'\ufffd');continue
        value=first&((1<<(7-size))-1);valid=True
        for offset in range(1,size):
            if i==len(data):valid=False;break
            b=data[i]
            if b&192!=128 or offset==1 and (first==224 and b<160 or first==240 and b<144 or first==244 and b>=144):valid=False;break
            value=(value<<6)|(b&63);i+=1
        if not valid or 55296<=value<=57343:result.append(u'\ufffd');continue
        if value>65535:
            value-=65536;result.extend((_CHAR_FROM_CODE(55296+(value>>10)),_CHAR_FROM_CODE(56320+(value&1023))))
        else:result.append(_CHAR_FROM_CODE(value))
    return JavaString(_utf16_text(u''.join(result)))

def write(buffer,value,maximum):
    if value is None:raise NullPointerException()
    if len(_utf16_units(value))>maximum:raise EncoderException('String exceeds UTF16 limit')
    data=encode_units(value)
    if len(data)>maximum*3:raise EncoderException('Encoded string exceeds byte limit')
    if buffer is None:raise NullPointerException()
    from minecraft.network_codecs import _var_write
    _var_write(buffer,len(data))
    for b in data:buffer.writeByte(b)

def read(buffer,maximum):
    if buffer is None:raise NullPointerException()
    from minecraft.network_codecs import _var_read
    size=_var_read(buffer).intValue()
    if size<0 or size>maximum*3 or size>buffer.readableBytes():raise DecoderException('Invalid encoded string length')
    value=decode_units([buffer.readUnsignedByte() for i in range(size)])
    if len(_utf16_units(value))>maximum:raise DecoderException('Decoded string exceeds UTF16 limit')
    return value

JAVA_MAP={'io.netty.handler.codec.DecoderException':DecoderException,'io.netty.handler.codec.EncoderException':EncoderException}
