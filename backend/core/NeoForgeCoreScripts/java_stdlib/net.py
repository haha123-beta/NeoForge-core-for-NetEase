# -*- coding: utf-8 -*-
"""Form URL decoding used by the real sample; no network access."""
from __future__ import absolute_import
from java_stdlib._base import IllegalArgumentException, JavaException
from java_stdlib.lang import java_to_string, NullPointerException

_UNSET = object()


class UnsupportedEncodingException(JavaException):
    pass


class IllegalCharsetNameException(IllegalArgumentException):
    def getCharsetName(self):
        return self.args[0]


class UnsupportedCharsetException(IllegalArgumentException):
    def getCharsetName(self):
        return self.args[0]


class Charset(object):
    def __init__(self, name, codec=None):
        self._name = name
        self._codec = codec or name

    def name(self):
        return self._name

    def toString(self):
        return self._name

    @staticmethod
    def forName(name):
        if name is None:
            raise IllegalArgumentException("Charset name is null")
        name = java_to_string(name)
        letters = u"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        if not name or name[0] not in letters or any(c not in letters + u"-+.:_" for c in name):
            raise IllegalCharsetNameException(name)
        try:
            codec = _codec_name(name)
        except LookupError:
            raise UnsupportedCharsetException(name)
        for charset in _STANDARD_CHARSETS:
            if codec == charset._codec:
                return charset
        # Python codec availability alone does not establish Java compatibility.
        raise UnsupportedCharsetException(name)

    @staticmethod
    def isSupported(name):
        try:
            Charset.forName(name)
            return True
        except UnsupportedCharsetException:
            return False



class StandardCharsets(object):
    UTF_8 = Charset("UTF-8", "utf-8")
    US_ASCII = Charset("US-ASCII", "ascii")
    ISO_8859_1 = Charset("ISO-8859-1", "iso8859-1")
    UTF_16 = Charset("UTF-16", "utf-16")
    UTF_16BE = Charset("UTF-16BE", "utf-16-be")
    UTF_16LE = Charset("UTF-16LE", "utf-16-le")


_STANDARD_CHARSETS = (StandardCharsets.UTF_8, StandardCharsets.US_ASCII,
    StandardCharsets.ISO_8859_1, StandardCharsets.UTF_16,
    StandardCharsets.UTF_16BE, StandardCharsets.UTF_16LE)


def _codec_name(name):
    key = name.lower().replace('_', '-').replace('-', '')
    aliases = {'utf8': 'utf-8', 'ascii': 'ascii', 'usascii': 'ascii',
        'iso646us': 'ascii', 'iso88591': 'iso8859-1', 'latin1': 'iso8859-1',
        'isolatin1': 'iso8859-1', 'utf16': 'utf-16',
        'utf16be': 'utf-16-be', 'utf16le': 'utf-16-le'}
    if key not in aliases:
        raise LookupError(name)
    return aliases[key]


class URLDecoder(object):
    @staticmethod
    def decode(value, charset=_UNSET):
        if charset is _UNSET:
            raise NotImplementedError("Specify charset; JVM platform default is unavailable")
        if value is None or charset is None:
            raise NullPointerException("URLDecoder input/charset is null")
        codec = charset._codec if isinstance(charset, Charset) else java_to_string(charset)
        if not codec:
            raise UnsupportedEncodingException("Empty encoding name")
        source = java_to_string(value)
        result, index = [], 0
        while index < len(source):
            character = source[index]
            if character == u"+":
                result.append(u" ")
                index += 1
            elif character == u"%":
                data = bytearray()
                while index < len(source) and source[index] == u"%":
                    digits = source[index + 1:index + 3]
                    if len(digits) != 2 or any(digit not in u"0123456789abcdefABCDEF" for digit in digits):
                        raise IllegalArgumentException("Malformed URL escape at " + str(index))
                    data.append(int(digits, 16))
                    index += 3
                try:
                    actual_codec = _codec_name(codec)
                    if actual_codec == "utf-16" and data[:2] not in (bytearray([254, 255]), bytearray([255, 254])):
                        actual_codec = "utf-16-be"
                    result.append(data.decode(actual_codec, "replace"))
                except LookupError:
                    raise UnsupportedEncodingException(codec)
            else:
                result.append(character)
                index += 1
        return u"".join(result)


JAVA_MAP = {
    "java.nio.charset.IllegalCharsetNameException": IllegalCharsetNameException,
    "java.nio.charset.UnsupportedCharsetException": UnsupportedCharsetException,
    "java.net.URLDecoder": URLDecoder,
    "java.nio.charset.Charset": Charset,
    "java.nio.charset.StandardCharsets": StandardCharsets,
    "java.io.UnsupportedEncodingException": UnsupportedEncodingException,
}