# -*- coding: utf-8 -*-
from __future__ import absolute_import
from java_stdlib._base import UnsupportedOperationException

class JavaAutoCloseable(object):
    ABI_VERSION = 1
    def close(self):
        raise UnsupportedOperationException("AutoCloseable.close implementation is missing")

class JavaCloseable(JavaAutoCloseable):
    pass

JAVA_MAP={'java.lang.AutoCloseable':JavaAutoCloseable,'java.io.Closeable':JavaCloseable}
