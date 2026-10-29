# -*- coding: utf-8 -*-
"""Explicit unsupported boundary; importing this module does not enable Sponge Mixin JVM bytecode injection."""
from __future__ import absolute_import

def require_support():
    raise NotImplementedError("Sponge Mixin JVM bytecode injection is unavailable in NetEase Python; an explicit semantic port is required")

SUPPORTED = False
JAVA_MAP = {}
