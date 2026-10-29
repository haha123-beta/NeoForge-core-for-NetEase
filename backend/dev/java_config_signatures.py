"""NeoForge 21.1.233 typed config getters backed by the native config adapter.

get() has a boxed Java return value although the native store uses primitives.
Normalize this ABI boundary, rather than weakening general reference casts.
"""
PREFIX='net.neoforged.neoforge.common.ModConfigSpec.'

def resolve(base,name,arity,actual):
    if base==PREFIX+'Builder' and name=='defineInRange':
        from java_value_types import widens
        if arity!=4 or len(actual)!=4 or actual[0] not in ('String','java.lang.String'):
            raise ValueError('Reviewed config range requires String path and three primitive bounds')
        target=next((k for k in ('int','long','double') if all(widens(t,k) for t in actual[1:])),None)
        if target is None:raise ValueError('Unreviewed config range overload')
        leaf={'int':'IntValue','long':'LongValue','double':'DoubleValue'}[target]
        row={'return_type':PREFIX+leaf,'parameters':['java.lang.String']+[target]*3,'receiver_kind':'game_api'}
        if target=='long':row['call_name']='_defineLongRange'
        return row
    kinds={'BooleanValue':('boolean','java.lang.Boolean','getAsBoolean'),
           'IntValue':('int','java.lang.Integer','getAsInt'),
           'LongValue':('long','java.lang.Long','getAsLong'),
           'DoubleValue':('double','java.lang.Double','getAsDouble')}
    row=kinds.get(base[len(PREFIX):]) if base.startswith(PREFIX) else None
    if row is None or name not in ('get',row[2]):return None
    if arity!=0 or actual:raise ValueError('Config getter requires zero arguments: '+name)
    primitive,boxed,getter=row
    result={'return_type':boxed if name=='get' else primitive,'parameters':[],'receiver_kind':'game_api'}
    if name=='get':result['boxed_native_return']=primitive
    return result
