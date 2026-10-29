"""Memoize pure type queries only within one synchronous resolution request.

No cache survives its outer query, lexical environment, generation or file.
Unknown (None) results are cached too; emitted code and runtime evaluation are
never memoized here. Exceptions are not cached.
"""
from functools import wraps

def request_scope():
    state={'depth':0,'values':{}}
    def decorate(function):
        @wraps(function)
        def query(node):
            root=state['depth']==0;state['depth']+=1
            key=(function,id(node))
            try:
                if key not in state['values']:
                    state['values'][key]=(node,function(node))
                # Retain the node while cached so temporary synthetic nodes
                # cannot recycle an id within the same resolution request.
                return state['values'][key][1]
            finally:
                state['depth']-=1
                if root:state['values'].clear()
        return query
    return decorate
