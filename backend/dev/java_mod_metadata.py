"""NeoForge1.21.1 @Mod constructor metadata; source bodies remain unchanged."""
import json,re
from java_method_overloads import canonical
INJECTIONS={'net.neoforged.bus.api.IEventBus','net.neoforged.fml.ModContainer','net.neoforged.fml.javafmlmod.FMLModContainer','net.neoforged.api.distmarker.Dist'}

def constant_strings(ir,cls):
    data=ir['source_utf8'].encode('utf-8')
    def text(node):return data[node['span'][0]:node['span'][1]].decode('utf-8') if node else ''
    def field(node,key):return next((c for c in node.get('children',[]) if c.get('field')==key),None)
    values={}
    def value(node):
        if node is None:return None
        if node['kind']=='string_literal':
            raw=text(node)
            if '\\u' in raw:return None
            try:return json.loads(raw)
            except ValueError:return None
        if node['kind']=='identifier':return values.get(text(node))
        if node['kind']=='binary_expression' and text(field(node,'operator'))=='+':
            left,right=value(field(node,'left')),value(field(node,'right'))
            return left+right if isinstance(left,str) and isinstance(right,str) else None
        return None
    for member in cls['fields']:
        if member['static'] and member['final'] and member['declared_type'] in ('String','java.lang.String'):
            resolved=value(member.get('initializer'))
            if resolved is not None:values[member['name']]=resolved
    return values

def plan(ir,symbols,records,project_types,error_type):
    data=ir['source_utf8'].encode('utf-8')
    def text(node):return data[node['span'][0]:node['span'][1]].decode('utf-8') if node else ''
    def field(node,key):return next((c for c in node.get('children',[]) if c.get('field')==key),None)
    def walk(node,ancestors=()):
        yield node,ancestors
        for child in node.get('children',[]):yield from walk(child,ancestors+(node,))
    nodes=list(walk(ir['tree']));result=[];annotation_owners=set()
    unit=dict(ir,_classes=symbols['classes'],_project_types=project_types)
    for record in records:
        if record['java_name']!='net.neoforged.fml.common.Mod':continue
        node,ancestors=next((n,a) for n,a in nodes if list(n['span'])==record['span'])
        declaration=next((a for a in reversed(ancestors) if a['kind']=='class_declaration'),None)
        if declaration is None or record['target_kind']!='class_declaration':raise error_type(node,'@Mod must target a public top-level class')
        cls=next(c for c in symbols['classes'] if c['name']==text(field(declaration,'name')))
        if cls['owner'] or 'public' not in cls.get('modifiers',[]):raise error_type(node,'@Mod class must be public and top-level')
        arguments=field(node,'arguments')
        args=[c for c in arguments.get('children',[]) if c['kind'] not in ('(',')',',')] if arguments else []
        mod_node=None;sides=['CLIENT','DEDICATED_SERVER']
        for arg in args:
            if arg['kind']=='element_value_pair':
                key=text(field(arg,'key'));value_node=field(arg,'value')
                if key=='value':mod_node=value_node
                elif key=='dist':
                    entries=[c for c in value_node.get('children',[]) if c['kind'] not in ('{','}',',')] if value_node['kind']=='element_value_array_initializer' else [value_node]
                    sides=[]
                    for entry in entries:
                        raw=text(entry);owner,separator,name=raw.rpartition('.')
                        if not separator or canonical(owner,cls,unit)!='net.neoforged.api.distmarker.Dist' or name not in ('CLIENT','DEDICATED_SERVER'):
                            raise error_type(entry,'@Mod dist must resolve to an actual Dist enum constant')
                        sides.append(name)
                else:raise error_type(arg,'Unknown @Mod annotation parameter: '+key)
            elif mod_node is None:mod_node=arg
            else:raise error_type(arg,'Multiple unnamed @Mod values')
        if mod_node is None:raise error_type(node,'@Mod value is missing')
        raw=text(mod_node);mod_id=None
        if mod_node['kind']=='string_literal':
            try:mod_id=json.loads(raw)
            except ValueError:pass
        elif mod_node['kind']=='identifier':mod_id=constant_strings(ir,cls).get(raw)
        elif mod_node['kind']=='field_access':
            owner=text(field(mod_node,'object'));name=text(field(mod_node,'field'))
            local=next((c for c in symbols['classes'] if owner in (c['name'],c['java_name'])),None)
            if local:mod_id=constant_strings(ir,local).get(name)
            else:
                identity=canonical(owner,cls,unit);candidates=project_types.get(identity,[])
                if len(candidates)==1:mod_id=candidates[0].get('constant_strings',{}).get(name)
                annotation_owners.add(owner)
        if not isinstance(mod_id,str) or not re.fullmatch('[a-z][a-z0-9_]{1,63}',mod_id):raise error_type(mod_node,'@Mod id needs a resolvable Java string constant and valid mod ID')
        constructors=[m for m in cls['methods'] if m['constructor']]
        public=[m for m in constructors if 'public' in m.get('modifiers',[])]
        if not constructors:parameters=[]
        elif len(public)!=1:raise error_type(node,'@Mod needs exactly one public constructor')
        else:parameters=[canonical(p['declared_type'],cls,unit) for p in public[0]['parameters']]
        if any(p not in INJECTIONS for p in parameters) or len(set(parameters))!=len(parameters):raise error_type(node,'@Mod constructor has unsupported or duplicated injection types')
        result.append({'class_name':cls['name'],'java_name':cls['java_name'],'mod_id':mod_id,'constructor_signature':parameters,'physical_sides':sorted(set(sides)),'line':node['line']})
    skip=set()
    for owner in annotation_owners:
        if not any(text(n)==owner and n['kind'] in ('identifier','type_identifier') and not any(a['kind'] in ('annotation','marker_annotation','import_declaration') for a in ancestors) for n,ancestors in nodes):
            skip.update(row['name'] for row in ir['imports'] if row['name'].rsplit('.',1)[-1]==owner)
    return result,skip
