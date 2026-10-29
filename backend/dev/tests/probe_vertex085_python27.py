from __future__ import print_function
import io,json,sys
with io.open(sys.argv[1],'r',encoding='utf-8') as stream:data=json.load(stream)
scope={'__name__':'vertex085_loader'}
eval(compile(data['loader_source'].encode('utf-8'),'source_modules.py','exec'),scope)
runtime=scope['SourceModuleLoader'](data['sources']);api=runtime.load('core.java_api');imports=api.JavaApiImports(runtime).install(api.collect_java_api())
try:
    v=runtime.load('minecraft.vertex_format');F=v.VertexFormat;E=v.VertexFormatElement;lines=[]
    for mode in F.Mode.values():
        lines.append(','.join(map(str,[mode.name(),mode.asGLMode,mode.primitiveLength,mode.primitiveStride,str(mode.connectedPrimitives).lower()])))
        for count in data['counts']:lines.append(str(mode.indexCount(count)))
    for count in data['counts']:lines.append(str(F.IndexType.least(count).name()))
    for t in E.Type.values():lines.append(str(t.name())+','+str(t.size())+','+str(t.glType())+','+str(t.toString()))
    for name,unused in v.DEFAULT_LAYOUTS:
        f=getattr(v.DefaultVertexFormat,name)
        lines.append(str(f.getVertexSize())+','+str(f.getElementsMask())+','+str(f.hashCode())+','+','.join(map(str,f.getOffsetsByElement())))
        lines.extend(str(f.toString()).splitlines())
    for padding in data['padding']:
        f=F.builder().add('Position',E.POSITION).add('Color',E.COLOR).padding(padding).add('Normal',E.NORMAL).padding(1).build()
        lines.append(','.join(map(str,[f.getVertexSize(),f.getOffset(E.COLOR),f.getOffset(E.NORMAL),f.getElementsMask(),f.hashCode()])))
        f.getOffsetsByElement()[0]=99
        lines.append(','.join(map(str,[f.getOffset(E.POSITION),f.getElementsMask(),f.hashCode()])))
    assert lines==data['expected'],repr([(i,a,b) for i,(a,b) in enumerate(zip(lines,data['expected'])) if a!=b][:6])+str((len(lines),len(data['expected'])))
    assert runtime.load('Run').Run().run()==85
    print(json.dumps({'rows':len(lines),'python2_executed':True,'source_value':85}))
finally:imports.close();runtime.close()
