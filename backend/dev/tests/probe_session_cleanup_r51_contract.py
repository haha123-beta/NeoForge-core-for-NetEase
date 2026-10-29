# -*- coding: utf-8 -*-
from __future__ import print_function


def trace(load):
    module = load('core.bundled_mods')
    calls = []
    class Failing(object):
        def __init__(self, name): self.name = name
        def close(self):
            calls.append(self.name)
            raise ValueError(u'中文内部清理失败')
    # Isolate the close boundary without relying on a failing game's internals.
    session = module.BundledModSession.__new__(module.BundledModSession)
    session.loader = Failing('loader')
    session.api_scope = Failing('api_scope')
    session.runtime = Failing('runtime')
    session._owns_runtime = True
    session._closed = False
    session._close_errors = []
    error_type, message = None, None
    try: session.close()
    except Exception as error:
        error_type = type(error).__name__
        message = load('neoforge.network')._error_text(error)
    return {'calls': calls, 'type': error_type, 'message': message, 'errors': list(session._close_errors)}


def run(load):
    result = trace(load)
    assert result['calls'] == ['loader', 'api_scope', 'runtime'], result
    assert result['type'] == 'RuntimeError', result
    assert len(result['errors']) == 3 and u'中文内部清理失败' in result['message'], result
    return result
