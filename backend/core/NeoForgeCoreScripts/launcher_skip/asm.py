# -*- coding: utf-8 -*-
"""Explicit unsupported boundary; importing this module does not enable ASM JVM bytecode manipulation."""
from __future__ import absolute_import

def require_support():
    raise NotImplementedError("ASM JVM bytecode manipulation is unavailable in NetEase Python; an explicit semantic port is required")

SUPPORTED = False
JAVA_MAP = {}
