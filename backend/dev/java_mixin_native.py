"""Reviewed runtime-owned constructor bindings; original handlers remain compiled source methods."""
from java_mixin_types import identity as type_identity

TARGET='net.minecraft.world.inventory.AbstractContainerMenu'
SITE=TARGET+'.<init>(Lnet/minecraft/world/inventory/MenuType;I)V:TAIL'
SIGNATURE=['net.minecraft.world.inventory.MenuType<?>','int']


def build(ir,cls,node,target,config,require,project_types):
    from java_mixin_native_trade import TARGET as TRADE_TARGET,build as trade_plan
    if target==TRADE_TARGET:return trade_plan(ir,cls,node,target,config,require,project_types)
    from java_mixin_plan import annotations,identity,arguments,field,text,children,walk,literal,singleton,INJECT,AT,CALLBACK,MixinPlanError
    def error(reason):raise MixinPlanError(ir['origin'],reason)
    if target!=TARGET:error('Runtime Mixin target has no reviewed site: '+target)
    if any(i['static'] or i['wildcard'] for i in ir['imports']):error('Runtime Mixin import context requires explicit types')
    if any(m['constructor'] for m in cls['methods']) or any(i['kind']!='field' for i in cls['initialization_order']):error('Runtime Mixin constructors/initializer blocks unsupported')
    if cls.get('method_overloaded_names'):error('Runtime Mixin overloaded handlers need explicit exports')
    changes=[];entries=[];fields=[]
    for ann in annotations(node):changes.append((*ann['span'],''))
    class_args=arguments(ir,annotations(node)[0],{'value','priority'})
    priority=literal(ir,class_args['priority'],int) if 'priority' in class_args else 1000
    context=dict(cls,imports=ir['imports'],package=ir['package'])
    unit={'_project_types':project_types}
    body=field(node,'body')
    for member in children(body):
        if member['kind']=='field_declaration':
            declared=[f for f in cls['fields'] if f['line']>=member['line'] and any(text(ir,field(c,'name'))==f['name'] for c in children(member) if c['kind']=='variable_declarator')]
            anns=annotations(member);names=[identity(ir,a) for a in anns]
            allowed={'org.spongepowered.asm.mixin.Shadow','org.spongepowered.asm.mixin.Final','org.spongepowered.asm.mixin.Mutable'}
            if len(declared)!=1 or set(names)!=allowed or len(names)!=3:error('Runtime constructor field binding requires Shadow/Final/Mutable menuType')
            f=declared[0]
            try:kind=type_identity(f['declared_type'],context,unit)
            except ValueError as e:error(str(e))
            if f['name']!='menuType' or kind!=SIGNATURE[0] or f['static'] or f['final'] or f['initializer'] is not None:error('Runtime menuType field identity differs')
            for a in anns:
                arguments(ir,a,set());changes.append((*a['span'],''))
            fields.append({'field':'menuType','java_type':kind,'final':True,'mutable':True})
        elif member['kind']=='method_declaration':
            method=next(m for m in cls['methods'] if m['line']==member['line'])
            anns=annotations(member);injectors=[]
            for a in anns:
                aid=identity(ir,a);name=text(ir,field(a,'name'))
                if aid==INJECT:injectors.append(a)
                elif (aid=='java.lang.SuppressWarnings' or (aid is None and name=='SuppressWarnings' and not any(i['name'].rsplit('.',1)[-1]=='SuppressWarnings' for i in ir['imports']))) and ir['package']+'.SuppressWarnings' not in project_types and 'java.lang.SuppressWarnings' not in project_types:
                    pass
                else:error('Runtime handler annotation requires review: '+name)
                changes.append((*a['span'],''))
            if len(injectors)!=1:error('Runtime constructor handler requires exactly Inject')
            options=arguments(ir,injectors[0],{'method','at','require','cancellable'})
            selector=literal(ir,singleton(ir,options.get('method'),'Inject.method'),str)
            if selector not in ('<init>','<init>(Lnet/minecraft/world/inventory/MenuType;I)V'):error('Runtime constructor selector differs')
            at=singleton(ir,options.get('at'),'Inject.at')
            if at is None or at['kind']!='annotation' or identity(ir,at)!=AT:error('Runtime constructor requires At')
            if literal(ir,arguments(ir,at,{'value'}).get('value'),str)!='TAIL':error('Runtime constructor requires TAIL')
            if 'cancellable' in options and literal(ir,options['cancellable'],bool):error('Runtime constructor cannot be cancelled')
            count=literal(ir,options['require'],int) if 'require' in options else require
            if count>1:error('Runtime constructor site count is one')
            if method['return_type']!='void' or method['static'] or 'private' not in method['modifiers'] or method['body'] is None:error('Runtime handler must be private instance void')
            try:parameters=[type_identity(p['declared_type'],context,unit) for p in method['parameters']]
            except ValueError as e:error(str(e))
            if parameters not in ([CALLBACK+'CallbackInfo'],SIGNATURE+[CALLBACK+'CallbackInfo']):error('Runtime constructor capture signature differs')
            if any(p['varargs'] for p in method['parameters']):error('Runtime constructor varargs unsupported')
            for n in walk(method['body']):
                if n['kind'] in ('identifier','type_identifier') and text(ir,n)==cls['name']:error('Runtime Mixin cannot be used as a standalone source class')
                if n['kind']=='method_invocation' and (field(n,'object') is None or text(ir,field(n,'object'))=='this'):
                    error('Runtime handler this/helper methods require explicit binding')
            entries.append({'config':config,'mixin':cls['java_name'],'mixin_file':ir['origin'],'target':target,'site':SITE,
                            'handler':method['name'],'class_name':cls['name'],'module':ir['origin'][:-5].replace('/','.'),
                            'capture_arguments':len(parameters)>1,'priority':priority,'require':count,'matches':1})
    if len(fields)!=len(cls['fields']) or not entries:error('Runtime Mixin contains unbound fields or no handlers')
    for imp in ir['imports']:
        if imp['name'].startswith('org.spongepowered.asm.mixin.') and not imp['name'].startswith(CALLBACK):
            # Delete the entire import, including semicolon; imports carry parser byte spans.
            node=next(n for n in ir['tree']['children'] if n['kind']=='import_declaration' and imp['name'] in text(ir,n))
            changes.append((*node['span'],''))
    return {'target':target,'mixin_file':ir['origin'],'entries':entries,'fields':fields,'source_edits':[list(change) for change in changes],
            'phase':'before_owner_entrypoint','scope':'reviewed_runtime_constructor_tail'}
