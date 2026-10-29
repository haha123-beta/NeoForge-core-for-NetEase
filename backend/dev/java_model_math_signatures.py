"""Pinned original matrix storage API; unsupported math and codec calls stay in review."""
MATRIX='org.joml.Matrix4f'
TRANSFORM='com.mojang.math.Transformation'
TYPES={MATRIX,TRANSFORM}
CONTEXT='net.minecraft.world.item.ItemDisplayContext'
VECTOR='org.joml.Vector3f';SORT='com.mojang.blaze3d.vertex.VertexSorting';DISTANCE=SORT+'.DistanceFunction'
TYPES.add(VECTOR)

def constructor(owner,actual):
    if owner==VECTOR:
        if not actual:return []
        if actual==[VECTOR]:return ['org.joml.Vector3fc']
        if len(actual) in (1,3) and all(a=='float' for a in actual):return ['float']*len(actual)
    if owner==MATRIX:
        if not actual:return []
        if actual==[MATRIX]:return ['org.joml.Matrix4fc']
        if len(actual)==16 and all(a=='float' for a in actual):return ['float']*16
    elif owner==TRANSFORM and len(actual)==1 and actual[0] in (MATRIX,'<null>'):return [MATRIX]
    raise ValueError('Unreviewed model math constructor: '+owner)

def resolve(base,name,arity,actual):
    if base==SORT and name=='byDistance':
        if actual==['float']*3:formal=actual;call='_by_xyz'
        elif actual==[VECTOR]:formal=actual;call='_by_vector'
        elif arity==1 and actual[0] in (None,DISTANCE):formal=[DISTANCE];call='_by_function'
        else:raise ValueError('VertexSorting.byDistance requires reviewed vector/floats/functional input')
        return {'return_type':SORT,'parameters':formal,'receiver_kind':'game_api','static_owner':SORT,'call_name':call}
    if base not in TYPES and base!=CONTEXT:return None
    row=None
    if base==MATRIX:
        if len(name)==3 and name[0]=='m' and name[1] in '0123' and name[2] in '0123':
            if arity==0:row=('float',[])
            elif arity==1:row=(MATRIX,['float'])
        else:row={'identity':(MATRIX,[]),'zero':(MATRIX,[]),'equals':('boolean',['java.lang.Object']),'hashCode':('int',[])}.get(name)
    elif base==VECTOR:
        row={'x':('float',[]),'y':('float',[]),'z':('float',[]),'distanceSquared':('float',['org.joml.Vector3fc'])}.get(name)
    elif base==TRANSFORM:row={'identity':(TRANSFORM,[]),'getMatrix':(MATRIX,[]),'equals':('boolean',['java.lang.Object']),'hashCode':('int',[])}.get(name)
    else:
        if name in ('values','valueOf','name','ordinal','compareTo','getDeclaringClass','toString','hashCode','equals'):return None
        row={'getId':('byte',[]),'getSerializedName':('java.lang.String',[]),'firstPerson':('boolean',[])}.get(name)
    if row is None:raise ValueError('Model math API requires review (decomposition/codecs/GPU are not supplied): '+name)
    result,formal=row
    if arity!=len(formal) or any(a!=f and a!='<null>' and f!='java.lang.Object' and not (a==VECTOR and f=='org.joml.Vector3fc') for a,f in zip(actual,formal)):raise ValueError('Model math argument signature mismatch: '+name)
    data={'return_type':result,'parameters':formal,'receiver_kind':'game_api'}
    if base==VECTOR and name in ('x','y','z'):data['call_name']='_get_'+name
    if base==TRANSFORM and name=='identity':data['static_owner']=TRANSFORM
    return data

def resolve_field(base,name):
    if base==SORT and name in ('DISTANCE_TO_ORIGIN','ORTHOGRAPHIC_Z'):return {'return_type':SORT,'receiver_kind':'game_api','static_owner':SORT,'final':True}
    if base==SORT:raise ValueError('Unknown VertexSorting field: '+name)
    if base==VECTOR and name in ('x','y','z'):return {'return_type':'float','receiver_kind':'game_api','final':False}
    if base in TYPES:raise ValueError('Model math field requires review (package fields/codecs are not public data): '+name)
