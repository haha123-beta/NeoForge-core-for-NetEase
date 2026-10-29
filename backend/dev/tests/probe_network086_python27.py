from __future__ import print_function
import io,json,sys
with io.open(sys.argv[1],'r',encoding='utf-8') as f:data=json.load(f)
ns={'__name__':'network086_loader'}
eval(compile(data['loader_source'].encode('utf-8'),'source_modules.py','exec'),ns)
runtime=ns['SourceModuleLoader'](data['sources']);api=runtime.load('core.java_api');scope=api.JavaApiImports(runtime).install(api.collect_java_api())
try:
    assert runtime.import_module('io',None,None,['open'],0).open is io.open
    assert not hasattr(io,'netty')
    bb=runtime.load('java_stdlib.byte_buffer');u=runtime.load('java_stdlib.util');mc=runtime.load('minecraft.core');pkg=runtime.load('demo.Packet');P=pkg.Packet
    p=P(-2147483648,-7,u.UUID.fromString('12345678-1234-5678-9abc-def012345678'),mc.BlockPos(-33554432,-2048,33554431));b=bb.Unpooled.buffer(0)
    P.CODEC.encode(b,p);lines=[','.join(map(str,b._neocore_bytes()))];q=P.CODEC.decode(b)
    lines.append(str(q.equals(p)).lower()+','+str(q.number())+','+str(q.flag())+','+q.id().toString()+','+str(q.pos().asLong())+','+str(q.hashCode())+','+q.type().id().toString()+','+q.type().toString()+','+str(q.type().hashCode()))
    assert lines==data['expected'],repr((lines,data['expected']))
    # Packet handlers use the reviewed statement-only enqueue path and execute at drain, not at enqueue.
    context=runtime.load('neoforge.network');c=context.IPayloadContext(context.PacketFlow.CLIENTBOUND)
    runtime.load('demo.Handlers').Handlers.handle(q,c)
    sink=runtime.load('demo.Sink').Sink
    assert sink.count==0 and c.pending()==1
    c.drainWork();assert sink.count==-7
    assert isinstance(q,context.CustomPacketPayload)
    try:q._nc_record_0=1;raise AssertionError('Mutable record')
    except AttributeError:pass
    print(json.dumps({'wire_bytes':b.writerIndex(),'python2_executed':True,'queued_handler_value':sink.count}))
finally:scope.close();runtime.close()
