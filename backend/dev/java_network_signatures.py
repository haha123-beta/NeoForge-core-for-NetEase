"""Reviewed source signatures for real byte buffers and codec values."""
BUFFER='io.netty.buffer.ByteBuf';UNPOOLED='io.netty.buffer.Unpooled';CODEC='net.minecraft.network.codec.StreamCodec';PAYLOAD='net.minecraft.network.protocol.common.custom.CustomPacketPayload';TYPE=PAYLOAD+'.Type'
def resolve(raw,base,name,arity,actual,canonical_generic,generic_arguments,canonical):
    buffers=(BUFFER,'net.minecraft.network.FriendlyByteBuf','net.minecraft.network.RegistryFriendlyByteBuf')
    row=None;static=False
    if base=='net.minecraft.resources.ResourceLocation':
        row={'fromNamespaceAndPath':(base,['java.lang.String','java.lang.String']),'parse':(base,['java.lang.String']),'withDefaultNamespace':(base,['java.lang.String']),'getNamespace':('java.lang.String',[]),'getPath':('java.lang.String',[]),'toString':('java.lang.String',[]),'hashCode':('int',[]),'equals':('boolean',['java.lang.Object'])}.get(name)
        static=name in ('fromNamespaceAndPath','parse','withDefaultNamespace')
    elif base=='net.neoforged.neoforge.network.handling.IPayloadContext':
        row={'enqueueWork':('java.util.concurrent.CompletableFuture<java.lang.Void>',['java.lang.Runnable']),'player':('net.minecraft.world.entity.player.Player',[]),'flow':('net.minecraft.network.protocol.PacketFlow',[])}.get(name)
        if row is None:raise ValueError('Payload context API not reviewed: '+name)
    elif base=='net.minecraft.network.protocol.PacketFlow':
        row={'isClientbound':('boolean',[]),'isServerbound':('boolean',[])}.get(name)
    elif base=='java.util.UUID':
        row={'fromString':('java.util.UUID',['java.lang.String']),'getMostSignificantBits':('long',[]),'getLeastSignificantBits':('long',[]),'hashCode':('int',[]),'equals':('boolean',['java.lang.Object']),'toString':('java.lang.String',[])}.get(name)
        static=name=='fromString'
    elif base=='net.minecraft.core.UUIDUtil':
        row={'uuidToIntArray':('int[]',['java.util.UUID']),'uuidFromIntArray':('java.util.UUID',['int[]'])}.get(name);static=True
        if row is None:raise ValueError('UUIDUtil API not reviewed: '+name)
    elif base==UNPOOLED:
        if name=='buffer' and arity in (0,1,2):row=(BUFFER,['int']*arity);static=True
        else:raise ValueError('Unpooled API not reviewed: '+name)
    elif base=='net.minecraft.network.codec.ByteBufCodecs' and name=='stringUtf8':
        row=(CODEC+'<'+BUFFER+',java.lang.String>',['int']);static=True
    elif base in buffers:
        if base!=BUFFER:raise ValueError('FriendlyByteBuf source operations require a byte-backed adapter; legacy tagged transport is not the native wire format')
        reads={'readInt':'int','readByte':'byte','readUnsignedByte':'short','readShort':'short','readUnsignedShort':'int','readBoolean':'boolean','readLong':'long','readableBytes':'int','writableBytes':'int','capacity':'int','maxCapacity':'int'}
        if name in reads and arity==0:row=(reads[name],[])
        elif name in ('writeByte','writeShort','writeInt','skipBytes') and arity==1:row=(base,['int'])
        elif name=='writeBoolean' and arity==1:row=(base,['boolean'])
        elif name=='writeLong' and arity==1:row=(base,['long'])
        elif name in ('getByte','getShort','getInt','getUnsignedByte') and arity==1:row=({'getByte':'byte','getShort':'short','getInt':'int','getUnsignedByte':'short'}[name],['int'])
        elif name in ('setByte','setShort','setInt') and arity==2:row=(base,['int','int'])
        elif name in ('readerIndex','writerIndex') and arity in (0,1):row=('int' if not arity else base,['int']*arity)
        elif name in ('clear','markReaderIndex','resetReaderIndex','markWriterIndex','resetWriterIndex') and arity==0:row=(base,[])
        elif name=='isReadable' and arity in (0,1):row=('boolean',['int']*arity)
        else:raise ValueError('ByteBuf API not reviewed: '+name)
    elif base in (CODEC,'net.minecraft.network.codec.StreamEncoder','net.minecraft.network.codec.StreamDecoder'):
        args=generic_arguments(raw)
        if name=='unit' and arity==1:
            if actual[0] in ('boolean','byte','short','char','long','float','double'):raise ValueError('StreamCodec.unit primitive boxing is not reviewed')
            kind='java.lang.Integer' if actual[0]=='int' else actual[0] if actual[0] not in (None,'<null>') else 'java.lang.Object'
            row=(CODEC+'<java.lang.Object,'+kind+'>',['java.lang.Object']);static=True
        elif len(args)==2:
            b,v=[canonical_generic(a,canonical) for a in args]
            if name=='decode' and arity==1 and base!='net.minecraft.network.codec.StreamEncoder':row=(v,[b])
            elif name=='encode' and arity==2 and base!='net.minecraft.network.codec.StreamDecoder':row=('void',[b,v])
            elif name=='cast' and arity==0 and base==CODEC:row=(raw,[])
        if row is None:raise ValueError('Codec API requires a reviewed generic signature: '+name)
    elif base==TYPE:
        row={'id':('net.minecraft.resources.ResourceLocation',[]),'equals':('boolean',['java.lang.Object']),'hashCode':('int',[]),'toString':('java.lang.String',[])}.get(name)
        if row is None:raise ValueError('Payload type API not reviewed: '+name)
    if row is None:return None
    target,formals=row
    if len(formals)!=arity:raise ValueError('Network API argument count mismatch: '+name)
    for a,f in zip(actual,formals):
        if a==f or f=='java.lang.Object' or a=='<null>' and f not in ('int','boolean','long'):continue
        if f=='java.lang.Runnable' and a is None:continue
        if base==CODEC and a=='java.lang.Object':continue # erased bridge validated by concrete codec method
        if a in buffers and f in buffers and a!=BUFFER:raise ValueError('FriendlyByteBuf cannot enter a native byte codec before its byte-backed adapter exists')
        raise ValueError('Network API argument type mismatch: '+name+' '+str(a)+' -> '+str(f))
    result={'return_type':target,'parameters':formals,'receiver_kind':'game_api'}
    if base=='net.minecraft.resources.ResourceLocation' and target=='java.lang.String':
        result['native_string_return']=True
    if base==CODEC:result['erased_bridge_arguments']=[i for i,(a,f) in enumerate(zip(actual,formals)) if a=='java.lang.Object' and f!='java.lang.Object']
    if base=='net.neoforged.neoforge.network.handling.IPayloadContext' and name=='enqueueWork':result['statement_only']=True
    if static:result['static_owner']=base
    return result


def resolve_field(owner,name):
    value=None
    if owner=='net.minecraft.core.UUIDUtil':
        if name=='STREAM_CODEC':value=CODEC+'<'+BUFFER+',java.util.UUID>'
        elif name=='UUID_BYTES':value='int'
        else:raise ValueError('UUIDUtil field not reviewed: '+name)
    elif owner=='net.minecraft.network.codec.ByteBufCodecs':
        values={'BOOL':'java.lang.Boolean','INT':'java.lang.Integer','VAR_INT':'java.lang.Integer','STRING_UTF8':'java.lang.String'}
        if name not in values:raise ValueError('ByteBufCodecs field not reviewed: '+name)
        value=CODEC+'<'+BUFFER+','+values[name]+'>'
    elif owner=='net.minecraft.core.BlockPos' and name=='STREAM_CODEC':value=CODEC+'<'+BUFFER+','+owner+'>'
    elif owner=='net.minecraft.resources.ResourceLocation' and name=='STREAM_CODEC':value=CODEC+'<'+BUFFER+','+owner+'>'
    if value:return {'return_type':value,'receiver_kind':'game_api','final':True,'static_owner':owner}
