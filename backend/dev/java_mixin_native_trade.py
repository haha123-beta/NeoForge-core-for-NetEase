"""One reviewed 1.21.1 runtime ModifyArg site; original Java handler stays intact."""
from java_mixin_types import identity as type_identity

TARGET='net.minecraft.world.inventory.MerchantResultSlot'
SUBJECT='Lnet/minecraft/world/entity/player/Player;awardStat(Lnet/minecraft/resources/ResourceLocation;)V'
SITE=TARGET+'.onTake(Lnet/minecraft/world/entity/player/Player;Lnet/minecraft/world/item/ItemStack;)V:INVOKE:'+SUBJECT+':0'
RESOURCE='net.minecraft.resources.ResourceLocation'
MERCHANT='net.minecraft.world.item.trading.Merchant'

def build(ir,cls,node,target,config,require,project_types):
    from java_mixin_plan import annotations,identity,arguments,field,text,children,walk,literal,singleton,AT,MODIFY_ARG,MixinPlanError
    def error(reason):raise MixinPlanError(ir['origin'],reason)
    if any(i['static'] or i['wildcard'] for i in ir['imports']):error('Runtime Mixin import context requires explicit types')
    if any(m['constructor'] for m in cls['methods']) or any(i['kind']!='field' for i in cls['initialization_order']) or cls.get('method_overloaded_names'):
        error('Runtime trade Mixin constructors/initializers/overloads unsupported')
    changes=[];entries=[];fields=[]
    for ann in annotations(node):changes.append((*ann['span'],''))
    options=arguments(ir,annotations(node)[0],{'value','priority'})
    priority=literal(ir,options['priority'],int) if 'priority' in options else 1000
    context=dict(cls,imports=ir['imports'],package=ir['package']);unit={'_project_types':project_types}
    def kind(raw):
        try:return type_identity(raw,context,unit)
        except ValueError as e:error(str(e))
    for member in children(field(node,'body')):
        if member['kind']=='field_declaration':
            decls=[n for n in children(member) if n['kind']=='variable_declarator']
            anns=annotations(member);names=[identity(ir,a) for a in anns]
            if len(decls)!=1 or len(names)!=2 or set(names)!={'org.spongepowered.asm.mixin.Shadow','org.spongepowered.asm.mixin.Final'}:
                error('Runtime trade field requires exactly Shadow/Final merchant')
            f=next(f for f in cls['fields'] if f['name']==text(ir,field(decls[0],'name')))
            if f['name']!='merchant' or kind(f['declared_type'])!=MERCHANT or f['static'] or f['final'] or f['initializer'] is not None:
                error('Runtime trade merchant field identity differs')
            for a in anns:arguments(ir,a,set());changes.append((*a['span'],''))
            fields.append({'field':'merchant','java_type':MERCHANT,'final':True,'mutable':False})
        elif member['kind']=='method_declaration':
            method=next(m for m in cls['methods'] if m['line']==member['line'])
            anns=annotations(member)
            if len(anns)!=1 or identity(ir,anns[0])!=MODIFY_ARG:error('Runtime trade handler requires exactly ModifyArg')
            changes.append((*anns[0]['span'],''))
            options=arguments(ir,anns[0],{'method','at','index','require'})
            selector=literal(ir,singleton(ir,options.get('method'),'ModifyArg.method'),str)
            if selector not in ('onTake','onTake(Lnet/minecraft/world/entity/player/Player;Lnet/minecraft/world/item/ItemStack;)V'):
                error('Runtime trade selector differs')
            at=options.get('at')
            if at is None or at['kind']!='annotation' or identity(ir,at)!=AT:error('Runtime trade ModifyArg requires scalar At')
            point=arguments(ir,at,{'value','target'})
            if literal(ir,point.get('value'),str)!='INVOKE' or literal(ir,point.get('target'),str)!=SUBJECT:
                error('Runtime trade subject owner/name/descriptor differs')
            if 'index' in options and literal(ir,options['index'],int)!=0:error('Runtime trade argument index must be zero')
            count=literal(ir,options['require'],int) if 'require' in options else require
            if count>1:error('Runtime trade site count is one')
            if method['static'] or 'private' not in method['modifiers'] or method['body'] is None or kind(method['return_type'])!=RESOURCE:
                error('Runtime trade handler must be private instance ResourceLocation')
            if [kind(p['declared_type']) for p in method['parameters']]!=[RESOURCE] or any(p['varargs'] for p in method['parameters']):
                error('Runtime trade handler requires one ResourceLocation argument')
            for n in walk(method['body']):
                if n['kind'] in ('assignment_expression','update_expression'):
                    left=field(n,'left') if n['kind']=='assignment_expression' else children(n)[0]
                    if left and any(k['kind'] in ('identifier','field_access') and (text(ir,k)=='merchant' or k['kind']=='field_access' and text(ir,field(k,'field'))=='merchant') for k in walk(left)):
                        error('Runtime final merchant field cannot be written')
                if n['kind'] in ('identifier','type_identifier') and text(ir,n)==cls['name']:error('Runtime Mixin cannot be a standalone source class')
                if n['kind']=='method_invocation' and (field(n,'object') is None or text(ir,field(n,'object'))=='this'):
                    error('Runtime handler this/helper methods require explicit binding')
            entries.append({'config':config,'mixin':cls['java_name'],'mixin_file':ir['origin'],'target':target,'site':SITE,
                            'handler':method['name'],'class_name':cls['name'],'module':ir['origin'][:-5].replace('/','.'),
                            'kind':'modify_arg','hook_abi':2,'priority':priority,'require':count,'matches':1})
        else:error('Runtime trade Mixin contains unsupported member: '+member['kind'])
    if len(fields)!=len(cls['fields']) or not entries:error('Runtime trade Mixin contains unbound fields or no handlers')
    for imp in ir['imports']:
        if imp['name'].startswith('org.spongepowered.asm.mixin.'):
            n=next(n for n in ir['tree']['children'] if n['kind']=='import_declaration' and imp['name'] in text(ir,n))
            changes.append((*n['span'],''))
    return {'target':target,'mixin_file':ir['origin'],'entries':entries,'fields':fields,'source_edits':[list(c) for c in changes],
            'phase':'before_owner_entrypoint','scope':'reviewed_runtime_modify_arg'}
