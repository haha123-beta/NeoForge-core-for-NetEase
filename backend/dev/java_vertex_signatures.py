"""Reviewed vertex data API. GPU and dynamic registration methods are rejected."""
P='com.mojang.blaze3d.vertex.';FORMAT=P+'VertexFormat';BUILDER=FORMAT+'.Builder';MODE=FORMAT+'.Mode';INDEX=FORMAT+'.IndexType';ELEMENT=P+'VertexFormatElement';TYPE=ELEMENT+'.Type';USAGE=ELEMENT+'.Usage'
DEFAULT=P+'DefaultVertexFormat'
TYPES={DEFAULT,FORMAT,BUILDER,MODE,INDEX,ELEMENT,TYPE,USAGE}
TABLE={DEFAULT:{},FORMAT:{'builder':(BUILDER,[]),'getVertexSize':('int',[]),'getElements':('java.util.List<'+ELEMENT+'>',[]),'getElementAttributeNames':('java.util.List<java.lang.String>',[]),'getOffsetsByElement':('int[]',[]),'getOffset':('int',[ELEMENT]),'contains':('boolean',[ELEMENT]),'getElementsMask':('int',[]),'getElementName':('java.lang.String',[ELEMENT]),'equals':('boolean',['java.lang.Object']),'hashCode':('int',[]),'toString':('java.lang.String',[])},
 BUILDER:{'add':(BUILDER,['java.lang.String',ELEMENT]),'padding':(BUILDER,['int']),'build':(FORMAT,[])},
 ELEMENT:{'byId':(ELEMENT,['int']),'id':('int',[]),'index':('int',[]),'type':(TYPE,[]),'usage':(USAGE,[]),'count':('int',[]),'mask':('int',[]),'byteSize':('int',[]),'hashCode':('int',[]),'equals':('boolean',['java.lang.Object']),'toString':('java.lang.String',[])},
 MODE:{'indexCount':('int',['int'])},INDEX:{'least':(INDEX,['int'])},TYPE:{'size':('int',[]),'glType':('int',[])},USAGE:{}}
STATIC={(FORMAT,'builder'),(ELEMENT,'byId'),(INDEX,'least')}
FIELDS={DEFAULT:{n:FORMAT for n in ('BLIT_SCREEN','BLOCK','NEW_ENTITY','PARTICLE','POSITION','POSITION_COLOR','POSITION_COLOR_NORMAL','POSITION_COLOR_LIGHTMAP','POSITION_TEX','POSITION_TEX_COLOR','POSITION_COLOR_TEX_LIGHTMAP','POSITION_TEX_LIGHTMAP_COLOR','POSITION_TEX_COLOR_NORMAL')},FORMAT:{'UNKNOWN_ELEMENT':'int'},ELEMENT:dict([(n,ELEMENT) for n in ('POSITION','COLOR','UV0','UV','UV1','UV2','NORMAL')]+[('MAX_COUNT','int')]),MODE:{'asGLMode':'int','primitiveLength':'int','primitiveStride':'int','connectedPrimitives':'boolean'},INDEX:{'asGLType':'int','bytes':'int'}}
def constructor(owner,actual):
    formal=['int','int',TYPE,USAGE,'int']
    if owner!=ELEMENT or len(actual)!=5 or any(a!=f and not(a=='<null>' and f not in ('int','boolean')) for a,f in zip(actual,formal)):
        raise ValueError('Vertex construction is not reviewed: '+owner)
    return formal
def resolve(owner,name,arity,actual):
    if owner not in TYPES:return None
    if owner in (TYPE,USAGE,MODE,INDEX) and name in ('values','valueOf','name','ordinal','compareTo','getDeclaringClass','toString','hashCode','equals'):return None
    row=TABLE[owner].get(name)
    if row is None:raise ValueError('Vertex API not reviewed (GPU/streams/registration remain unsupported): '+name)
    target,formal=row
    if arity!=len(formal) or any(a!=f and not(a=='<null>' and f not in ('int','boolean')) and f!='java.lang.Object' for a,f in zip(actual,formal)):raise ValueError('Vertex argument signature mismatch: '+name)
    result={'return_type':target,'parameters':formal,'receiver_kind':'game_api'}
    if (owner,name) in STATIC:result['static_owner']=owner
    return result
def resolve_field(owner,name):
    if owner not in TYPES:return None
    target=FIELDS.get(owner,{}).get(name)
    if target is None:return None
    result={'return_type':target,'receiver_kind':'game_api','final':True}
    if owner in (DEFAULT,FORMAT,ELEMENT):result['static_owner']=owner
    return result
