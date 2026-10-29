"""Reviewed FML4.0.42 event annotations; retain original handler names/signatures."""
import json
from java_method_overloads import canonical,signature
from java_mod_metadata import constant_strings
from java_event_bus_facts import MOD_BUS_TYPES,GAME_BUS_TYPES,ABSTRACT_EVENT_TYPES

def plan(ir,symbols,annotations,project_types,error_type):
    data=ir['source_utf8'].encode('utf-8')
    def text(node):return data[node['span'][0]:node['span'][1]].decode('utf-8') if node else ''
    def field(node,key):return next((c for c in node.get('children',[]) if c.get('field')==key),None)
    def walk(node,ancestors=()):
        yield node,ancestors
        for child in node.get('children',[]):yield from walk(child,ancestors+(node,))
    nodes=list(walk(ir['tree']));unit=dict(ir,_classes=symbols['classes'],_project_types=project_types)
    handlers={};subscribers=[];annotation_owners=set()
    def arguments(node):
        args=field(node,'arguments')
        result={}
        for child in args.get('children',[]) if args else []:
            if child['kind'] in ('(',')',','):continue
            if child['kind']=='element_value_pair':result[text(field(child,'key'))]=field(child,'value')
            else:result['value']=child
        return result
    def string_constant(node,cls):
        if node is None:return None
        if node['kind']=='string_literal':
            try:return json.loads(text(node))
            except ValueError:return None
        if node['kind']=='identifier':return constant_strings(ir,cls).get(text(node))
        if node['kind']=='field_access':
            owner=text(field(node,'object'));name=text(field(node,'field'));annotation_owners.add(owner)
            local=next((c for c in symbols['classes'] if owner in (c['name'],c['java_name'])),None)
            if local:return constant_strings(ir,local).get(name)
            records=project_types.get(canonical(owner,cls,unit),[])
            if len(records)==1:return records[0].get('constant_strings',{}).get(name)
        return None
    for annotation in annotations:
        identity=annotation['java_name']
        if identity not in ('net.neoforged.bus.api.SubscribeEvent','net.neoforged.fml.common.EventBusSubscriber'):continue
        node,ancestors=next((n,a) for n,a in nodes if list(n['span'])==annotation['span'])
        declaration=next((a for a in reversed(ancestors) if a['kind']=='class_declaration'),None)
        if declaration is None:raise error_type(node,'Event annotation needs a class declaration')
        cls=next(c for c in symbols['classes'] if c['name']==text(field(declaration,'name')))
        args=arguments(node)
        if identity.endswith('.SubscribeEvent'):
            method_node=next((a for a in reversed(ancestors) if a['kind']=='method_declaration'),None)
            if method_node is None:raise error_type(node,'SubscribeEvent must target a method')
            method=next(m for m in cls['methods'] if m['name']==text(field(method_node,'name')) and m['line']==method_node['line'])
            # Multiple overloads on the same line are matched by their parameter declaration.
            params=field(method_node,'parameters')
            param_types=[text(field(c,'type')) for c in params.get('children',[]) if c['kind']=='formal_parameter']
            method=next(m for m in cls['methods'] if m['name']==text(field(method_node,'name')) and [p['declared_type'] for p in m['parameters']]==param_types)
            if method['return_type']!='void' or len(method['parameters'])!=1 or method['parameters'][0]['varargs']:raise error_type(node,'SubscribeEvent needs one Event parameter and void result')
            raw_type=method['parameters'][0]['declared_type'];event_type=canonical(raw_type,cls,unit)
            if event_type in ABSTRACT_EVENT_TYPES:raise error_type(node,'Cannot register an abstract event type: '+event_type)
            bus='MOD' if event_type in MOD_BUS_TYPES else 'GAME' if event_type in GAME_BUS_TYPES else None
            if bus is None:raise error_type(node,'Event source marker facts require review: '+event_type)
            priority='NORMAL';canceled=False
            for key,value in args.items():
                if key=='priority':
                    owner,_,priority=text(value).rpartition('.')
                    if canonical(owner,cls,unit)!='net.neoforged.bus.api.EventPriority' or priority not in ('HIGHEST','HIGH','NORMAL','LOW','LOWEST'):raise error_type(value,'Unknown SubscribeEvent priority')
                elif key=='receiveCanceled':
                    if text(value) not in ('true','false'):raise error_type(value,'receiveCanceled needs a boolean constant')
                    canceled=text(value)=='true'
                else:raise error_type(value,'Unknown SubscribeEvent option: '+key)
            handlers.setdefault(cls['name'],[]).append({'method_name':method['name'],'signature':signature(method,cls,unit),'event_type':event_type,'source_event_type':raw_type,'static':method['static'],'priority':priority,'receive_canceled':canceled,'bus':bus,'line':node['line']})
        else:
            if annotation['target_kind']!='class_declaration':raise error_type(node,'EventBusSubscriber must target a class')
            mod_id=string_constant(args.get('modid'),cls)
            if 'modid' in args and mod_id is None:raise error_type(args['modid'],'Subscriber modid needs a resolvable string constant')
            sides=['CLIENT','DEDICATED_SERVER'];ignored=None
            for key,value in args.items():
                if key=='modid':continue
                if key=='value':
                    values=[c for c in value.get('children',[]) if c['kind'] not in ('{','}',',')] if value['kind']=='element_value_array_initializer' else [value]
                    sides=[]
                    for item in values:
                        owner,_,side=text(item).rpartition('.')
                        if canonical(owner,cls,unit)!='net.neoforged.api.distmarker.Dist' or side not in ('CLIENT','DEDICATED_SERVER'):raise error_type(item,'Subscriber physical side must resolve to Dist')
                        sides.append(side)
                elif key=='bus':
                    ignored=text(value)
                    owner,_,member=ignored.rpartition('.')
                    if canonical(owner,cls,unit)!='net.neoforged.fml.common.EventBusSubscriber.Bus' or member not in ('MOD','GAME'):raise error_type(value,'Legacy subscriber bus must resolve to its actual enum; FML4.0.42 ignores its value')
                else:raise error_type(value,'Unknown EventBusSubscriber option: '+key)
            subscribers.append({'class_name':cls['name'],'java_name':cls['java_name'],'mod_id':mod_id or None,'physical_sides':sorted(set(sides)),'ignored_legacy_bus':ignored,'line':node['line']})
    for subscriber in subscribers:
        if any(not handler['static'] for handler in handlers.get(subscriber['class_name'],[])):raise error_type(subscriber,'Automatic subscribers require static handlers')
    skip=set()
    for owner in annotation_owners:
        if not any(text(node)==owner and node['kind'] in ('identifier','type_identifier') and not any(a['kind'] in ('annotation','marker_annotation','import_declaration') for a in ancestors) for node,ancestors in nodes):
            skip.update(row['name'] for row in ir['imports'] if row['name'].rsplit('.',1)[-1]==owner)
    return handlers,subscribers,skip
