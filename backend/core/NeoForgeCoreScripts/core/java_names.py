# -*- coding: utf-8 -*-
"""Original Java attribute names without changing Python's grammar.

Use getattr(value, "is")(...), not value.is(...). Existing safe aliases remain valid.
"""
from __future__ import absolute_import
from core.keyword_renames import METHOD_RENAMES


def _forward(safe_name):
    def call(self, *args, **kwargs):
        return getattr(self, safe_name)(*args, **kwargs)
    return call


def install_java_aliases(java_map):
    installed = []
    for java_class, names in METHOD_RENAMES.items():
        owner = java_map.get(java_class)
        if owner is None or not hasattr(owner, "__mro__"):
            continue
        for original, safe in names.items():
            if original in owner.__dict__:
                continue
            descriptor = None
            for base in owner.__mro__:
                if safe in base.__dict__:
                    descriptor = base.__dict__[safe]
                    break
            if descriptor is None:
                continue
            if isinstance(descriptor, staticmethod):
                alias = descriptor
            elif isinstance(descriptor, classmethod):
                alias = classmethod(_forward(safe))
            else:
                alias = _forward(safe)
            setattr(owner, original, alias)
            installed.append(java_class + "." + original)
    return installed


def bind_java_name(owner, original, implementation):
    """Translator output can bind a legal helper definition under its original name."""
    if original in owner.__dict__:
        raise ValueError("Java attribute already defined: " + original)
    setattr(owner, original, implementation)
