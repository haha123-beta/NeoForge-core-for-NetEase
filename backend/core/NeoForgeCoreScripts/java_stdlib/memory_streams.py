# -*- coding: utf-8 -*-
"""Java memory streams. bytearray stores unsigned bytes; list reads are signed.
No filesystem, JVM serialization or thread synchronization is provided.
"""
from __future__ import absolute_import
from java_stdlib.java_auto_closeable import JavaCloseable
from java_stdlib._base import IllegalArgumentException, JavaException
from java_stdlib.java_arrays import JavaArrays
_NONE = object()


def _byte(value):
    return (ord(value) if isinstance(value, str) else int(value)) & 255


def _bounds(buffer, offset, length):
    if buffer is None:
        raise TypeError("Null byte array")
    if offset < 0 or length < 0 or offset > len(buffer) - length:
        raise IndexError("Byte array range out of bounds")


class ByteArrayInputStream(JavaCloseable):
    def __init__(self, buffer, offset=0, length=None):
        if buffer is None:
            raise TypeError("Null byte array")
        length = len(buffer) - offset if length is None else length
        if offset < 0 or offset > len(buffer) or length < 0:
            raise IndexError("Invalid byte stream range")
        self.buf, self.pos, self._mark = buffer, offset, offset
        self.count = min(len(buffer), offset + length)

    def read(self, buffer=_NONE, offset=0, length=None):
        if buffer is _NONE:
            if self.pos >= self.count:
                return -1
            value = _byte(self.buf[self.pos])
            self.pos += 1
            return value
        if buffer is None:
            raise TypeError("Null byte array")
        length = len(buffer) - offset if length is None else length
        _bounds(buffer, offset, length)
        if self.pos >= self.count:
            return -1
        size = min(length, self.count - self.pos)
        values = [_byte(self.buf[self.pos + i]) for i in range(size)]
        for index, value in enumerate(values):
            buffer[offset + index] = value if isinstance(buffer, bytearray) or value < 128 else value - 256
        self.pos += size
        return size

    def skip(self, count):
        size = min(max(0, int(count)), self.count - self.pos)
        self.pos += size
        return size

    def available(self):
        return self.count - self.pos

    def mark(self, readAheadLimit=0):
        self._mark = self.pos

    def reset(self):
        self.pos = self._mark

    def markSupported(self):
        return True

    def close(self):
        return None


class ByteArrayOutputStream(JavaCloseable):
    def __init__(self, size=32):
        if size < 0:
            raise IllegalArgumentException("Negative initial size")
        self.buf = bytearray()

    def write(self, value, offset=None, length=None):
        if offset is None and length is None and isinstance(value, int):
            self.buf.append(value & 255)
            return
        if value is None:
            raise TypeError("Null byte array")
        offset = 0 if offset is None else offset
        length = len(value) - offset if length is None else length
        _bounds(value, offset, length)
        self.buf.extend([_byte(value[i]) for i in range(offset, offset + length)])

    def writeTo(self, stream):
        stream.write(self.buf, 0, len(self.buf))

    def reset(self):
        del self.buf[:]

    def size(self):
        return len(self.buf)

    def toByteArray(self):
        return JavaArrays.initialized('byte',1,list(self.buf))

    def toString(self, charset=None):
        if charset is None:
            raise NotImplementedError("Specify charset; JVM platform default is unavailable")
        return self.buf.decode(charset, 'replace')

    def flush(self):
        return None

    def close(self):
        return None


class IOException(JavaException):
    _nc_java_name='java.io.IOException'


JAVA_MAP = {"java.io.IOException": IOException, "java.io.ByteArrayInputStream": ByteArrayInputStream,
            "java.io.ByteArrayOutputStream": ByteArrayOutputStream}
