# -*- coding: utf-8 -*-
"""Reviewed heap ByteBuf subset: real bytes, big-endian primitives and independent indices."""
from __future__ import absolute_import
from java_stdlib.lang import IndexOutOfBoundsException, IllegalArgumentException, NullPointerException, UnsupportedOperationException

class ByteBuf(object):
    def __init__(self,initial=256,maximum=2147483647):
        if initial<0 or initial>maximum:raise IllegalArgumentException('Invalid byte buffer capacity')
        self._bytes=bytearray(initial);self._maximum=maximum;self._reader=0;self._writer=0;self._mark_reader=0;self._mark_writer=0
    def _range(self,index,size,limit):
        if index<0 or size<0 or index+size>limit:raise IndexOutOfBoundsException('Byte buffer index outside bounds')
    def _ensure(self,size):
        if size<0 or self._writer+size>self._maximum:raise IndexOutOfBoundsException('Byte buffer maximum capacity exceeded')
        required=self._writer+size
        if required>len(self._bytes):
            threshold=4194304
            if required>threshold:
                capacity=(required//threshold)*threshold
                capacity=self._maximum if capacity>self._maximum-threshold else capacity+threshold
            else:capacity=64 if required<64 else 1<<(required-1).bit_length()
            capacity=min(self._maximum,capacity)
            self._bytes.extend(bytearray(capacity-len(self._bytes)))
    def _get(self,index,size,signed=True):
        self._range(index,size,len(self._bytes));value=0
        for i in range(size):value=(value<<8)|self._bytes[index+i]
        return value-(1<<(size*8)) if signed and value&(1<<(size*8-1)) else value
    def _set(self,index,size,value):
        self._range(index,size,len(self._bytes))
        for i in range(size):self._bytes[index+i]=(value>>((size-i-1)*8))&255
        return self
    def _write(self,size,value):
        self._ensure(size);self._set(self._writer,size,value);self._writer+=size;return self
    def _read(self,size,signed=True):
        self._range(self._reader,size,self._writer);value=self._get(self._reader,size,signed);self._reader+=size;return value
    def writeByte(self,value):return self._write(1,value)
    def writeBoolean(self,value):return self.writeByte(1 if value else 0)
    def writeShort(self,value):return self._write(2,value)
    def writeInt(self,value):return self._write(4,value)
    def writeLong(self,value):return self._write(8,value)
    def readByte(self):return self._read(1)
    def readUnsignedByte(self):return self._read(1,False)
    def readBoolean(self):return self.readByte()!=0
    def readShort(self):return self._read(2)
    def readUnsignedShort(self):return self._read(2,False)
    def readInt(self):return self._read(4)
    def readLong(self):return self._read(8)
    def getByte(self,index):return self._get(index,1)
    def getUnsignedByte(self,index):return self._get(index,1,False)
    def getShort(self,index):return self._get(index,2)
    def getInt(self,index):return self._get(index,4)
    def setByte(self,index,value):return self._set(index,1,value)
    def setShort(self,index,value):return self._set(index,2,value)
    def setInt(self,index,value):return self._set(index,4,value)
    def readerIndex(self,*args):
        if not args:return self._reader
        if len(args)!=1:raise TypeError('readerIndex requires zero or one argument')
        self._range(args[0],0,self._writer);self._reader=args[0];return self
    def writerIndex(self,*args):
        if not args:return self._writer
        if len(args)!=1:raise TypeError('writerIndex requires zero or one argument')
        self._range(args[0],0,len(self._bytes))
        if args[0]<self._reader:raise IndexOutOfBoundsException('Writer precedes reader')
        self._writer=args[0];return self
    def readableBytes(self):return self._writer-self._reader
    def writableBytes(self):return len(self._bytes)-self._writer
    def capacity(self,*args):
        if not args:return len(self._bytes)
        raise UnsupportedOperationException('Explicit capacity resizing is not reviewed')
    def maxCapacity(self):return self._maximum
    def isReadable(self,size=1):return self.readableBytes()>=size
    def clear(self):self._reader=self._writer=0;return self
    def markReaderIndex(self):self._mark_reader=self._reader;return self
    def resetReaderIndex(self):return self.readerIndex(self._mark_reader)
    def markWriterIndex(self):self._mark_writer=self._writer;return self
    def resetWriterIndex(self):return self.writerIndex(self._mark_writer)
    def skipBytes(self,size):self._range(self._reader,size,self._writer);self._reader+=size;return self
    def _neocore_bytes(self):return list(self._bytes[:self._writer])

class Unpooled(object):
    @staticmethod
    def buffer(*args):
        if len(args)>2:raise TypeError('Unpooled.buffer requires zero, one or two arguments')
        return ByteBuf(*args)

JAVA_MAP={'io.netty.buffer.ByteBuf':ByteBuf,'io.netty.buffer.Unpooled':Unpooled}
