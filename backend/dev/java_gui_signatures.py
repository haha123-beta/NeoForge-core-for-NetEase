"""Reviewed 1.21.1 GUI navigation signatures; no drawing adapters."""
P='net.minecraft.client.gui.navigation.'
POS=P+'ScreenPosition';RECT=P+'ScreenRectangle';AXIS=P+'ScreenAxis';DIRECTION=P+'ScreenDirection'
TYPES={POS,RECT,AXIS,DIRECTION}
METHODS={POS:{'of':(POS,[AXIS,'int','int']),'step':(POS,[DIRECTION]),'getCoordinate':('int',[AXIS]),'x':('int',[]),'y':('int',[])},
 RECT:{'empty':(RECT,[]),'of':(RECT,[AXIS,'int','int','int','int']),'step':(RECT,[DIRECTION]),'getLength':('int',[AXIS]),'getBoundInDirection':('int',[DIRECTION]),'getBorder':(RECT,[DIRECTION]),'overlaps':('boolean',[RECT]),'overlapsInAxis':('boolean',[RECT,AXIS]),'getCenterInAxis':('int',[AXIS]),'intersection':(RECT,[RECT]),'containsPoint':('boolean',['int','int']),'position':(POS,[]),'width':('int',[]),'height':('int',[]),'left':('int',[]),'top':('int',[]),'right':('int',[]),'bottom':('int',[])},
 AXIS:{'orthogonal':(AXIS,[]),'getPositive':(DIRECTION,[]),'getNegative':(DIRECTION,[]),'getDirection':(DIRECTION,['boolean'])},
 DIRECTION:{'getAxis':(AXIS,[]),'getOpposite':(DIRECTION,[]),'isPositive':('boolean',[]),'isAfter':('boolean',['int','int']),'isBefore':('boolean',['int','int'])}}
def constructor(owner,actual):
    choices={POS:[['int','int']],RECT:[['int']*4,[POS,'int','int']]}.get(owner,[])
    for formal in choices:
        if len(formal)==len(actual) and all(a==f or a=='<null>' and f not in ('int','boolean') for a,f in zip(actual,formal)):return formal
    raise ValueError('GUI navigation constructor is not reviewed: '+owner)
def resolve(owner,name,arity,actual):
    if owner not in TYPES:return None
    if name in ('equals','hashCode','toString'):return None
    if owner in (AXIS,DIRECTION) and name in ('values','valueOf','name','ordinal','compareTo','getDeclaringClass'):return None
    row=METHODS[owner].get(name)
    if row is None:raise ValueError('GUI navigation method is not reviewed: '+name)
    target,formal=row
    if arity!=len(formal) or any(a!=f and not(a=='<null>' and f not in ('int','boolean')) for a,f in zip(actual,formal)):raise ValueError('GUI navigation argument signature mismatch: '+name)
    result={'return_type':target,'parameters':formal,'receiver_kind':'game_api'}
    if owner==POS and name=='of' or owner==RECT and name in ('of','empty'):result['static_owner']=owner
    return result
