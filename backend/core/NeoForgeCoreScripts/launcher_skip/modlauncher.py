# -*- coding: utf-8 -*-
"""Explicit unsupported boundary; importing this module does not enable ModLauncher JVM launch transformation."""
from __future__ import absolute_import

def require_support():
    raise NotImplementedError("ModLauncher JVM launch transformation is unavailable in NetEase Python; an explicit semantic port is required")

SUPPORTED = False
JAVA_MAP = {}
