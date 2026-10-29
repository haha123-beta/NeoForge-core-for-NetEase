from __future__ import print_function
import io,json,sys
with io.open(sys.argv[1],'r',encoding='utf-8') as stream:data=json.load(stream)
scope={'__name__':'gui084_loader'}
eval(compile(data['loader_source'].encode('utf-8'),'source_modules.py','exec'),scope)
runtime=scope['SourceModuleLoader'](data['sources']);api=runtime.load('core.java_api');imports=api.JavaApiImports(runtime).install(api.collect_java_api())
try:
    gui=runtime.load('minecraft.gui_navigation');lines=[]
    for c in data['cases']:
        r=gui.ScreenRectangle(*c[:4]);other=gui.ScreenRectangle(*c[4:]);cut=r.intersection(other)
        values=[r.left(),r.top(),r.right(),r.bottom(),r.getCenterInAxis(gui.ScreenAxis.HORIZONTAL),r.getCenterInAxis(gui.ScreenAxis.VERTICAL),r.hashCode()]
        lines.append(','.join(map(str,values))+','+str(r.overlaps(other)).lower()+','+('null' if cut is None else ','.join(map(str,[cut.left(),cut.top(),cut.width(),cut.height()]))))
        for d in gui.ScreenDirection.values():
            border=r.getBorder(d)
            lines.append(','.join(map(str,[r.getBoundInDirection(d),border.left(),border.top(),border.width(),border.height()]))+','+str(d.isAfter(2,1)).lower()+','+str(d.isBefore(2,1)).lower())
    assert lines==data['expected'],repr([(a,b) for a,b in zip(lines,data['expected']) if a!=b][:3])
    assert runtime.load('Run').Run().run()==20
    try:gui.ScreenPosition(1,2)._x=9;raise AssertionError('mutable record')
    except AttributeError:pass
    print(json.dumps({'cases':len(data['cases']),'source_value':20,'python2_executed':True}))
finally:imports.close();runtime.close()
