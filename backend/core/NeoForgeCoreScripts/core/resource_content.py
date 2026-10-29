# -*- coding: utf-8 -*-
"""Validated Scripts/resources content registration, without runtime file I/O."""
from __future__ import absolute_import
import copy
import re
from core.runtime_requirements import code_digest, _name, _strings
from neoforge.network import _error_text

PROTOCOL = 1
KIND = 'neocore_resource_content'


def unwrap(pack_id, resource):
    if (not isinstance(resource, dict) or type(resource.get('schema_version')) is not int
            or resource.get('schema_version') != PROTOCOL or resource.get('kind') != KIND):
        raise ValueError('Unsupported resources content schema')
    if (not isinstance(pack_id, _strings) or not re.match(r'^[a-z][a-z0-9_]{1,63}$', pack_id)
            or resource.get('pack_id') != pack_id):
        raise ValueError('Resources content owner does not match registration')
    script = resource.get('script_package')
    if not _name(script) or '.' in script or script == 'NeoCoreSourceScripts':
        raise ValueError('Resources content requires an independent Scripts package')
    root = script + '/resources'
    if resource.get('resource_root') != root or resource.get('format_preview_only') is not False:
        raise ValueError('Resources layout is invalid or still a format preview')
    bundle, index = resource.get('bundle'), resource.get('source_index')
    if (not isinstance(bundle, dict) or bundle.get('kind') != 'neocore_content_sources'
            or type(bundle.get('schema_version')) is not int or bundle.get('schema_version') != 1):
        raise ValueError('Resources content requires a source bundle')
    sources = bundle.get('sources')
    if not isinstance(bundle.get('runtime_requirements'), dict):
        raise ValueError('Resources content requires generated translation requirements')
    if not isinstance(sources, dict) or not sources or not isinstance(index, dict) or set(index) != set(sources):
        raise ValueError('Resources source index is missing or incomplete')
    paths = set()
    for name, row in sources.items():
        if not _name(name) or not isinstance(row, dict) or not isinstance(index[name], dict):
            raise ValueError('Malformed resources module declaration')
        entry = index[name]
        expected = name.replace('.', '/') + ('/__init__.py' if row.get('is_package') else '.py')
        if row.get('origin') != expected or entry.get('path') != root + '/' + expected:
            raise ValueError('Resources source path differs from original module: ' + name)
        if expected.lower() in paths:
            raise ValueError('Resources source paths collide')
        paths.add(expected.lower())
        source = row.get('source')
        if not isinstance(source, _strings):
            raise ValueError('Resources module source is not text')
        if entry.get('text_sha256') != code_digest(source):
            raise ValueError('Resources source checksum mismatch: ' + name)
        raw_hash = row.get('sha256')
        if (entry.get('file_sha256') != raw_hash or
                raw_hash not in (code_digest(source), code_digest(u'\ufeff' + source))):
            raise ValueError('Resources file checksum mismatch: ' + name)
    mods = bundle.get('mods')
    if not isinstance(mods, list) or not mods:
        raise ValueError('Resources content has no mod declarations')
    for mod in mods:
        if not isinstance(mod, dict) or not isinstance(mod.get('entrypoint'), _strings):
            raise ValueError('Resources content entrypoint is missing')
        module, separator, attribute = mod['entrypoint'].partition(':')
        if not separator or module not in sources or not _name(attribute):
            raise ValueError('Resources content entrypoint is unresolved')
    # BundledModSession performs API/helper, dependency and namespace checks before imports.
    return copy.deepcopy(bundle)
