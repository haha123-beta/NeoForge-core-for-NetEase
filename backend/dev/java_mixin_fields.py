"""Identity-preserving source Shadow fields and conservative handler context checks."""
import re
from java_method_overloads import canonical
from java_mixin_types import identity as type_identity

PREFIX = 'org.spongepowered.asm.mixin.'


def bind_fields(ir, cls, target_ir, target_cls, node, types):
    # Imported lazily: planner owns parse helpers; this module owns field/context policy.
    from java_mixin_plan import annotations, identity, arguments, children, field, text, MixinPlanError
    targets = {f['name']: f for f in target_cls['fields']}
    body = field(node, 'body')
    bindings = []
    for member in children(body):
        if member['kind'] not in ('field_declaration', 'constant_declaration'):
            continue
        anns = annotations(member)
        names = [identity(ir, ann) for ann in anns]
        if len(names) != len(set(names)) or PREFIX+'Shadow' not in names or set(names)-{PREFIX+'Shadow', PREFIX+'Final', PREFIX+'Mutable'}:
            raise MixinPlanError(ir['origin'], 'Mixin fields require exact Shadow/Final/Mutable annotations')
        for ann in anns:
            if arguments(ir, ann, set()):
                raise MixinPlanError(ir['origin'], 'Shadow aliases/remapping/options require context review')
        for decl in [c for c in children(member) if c['kind']=='variable_declarator']:
            name = text(ir, field(decl,'name'))
            source = next(f for f in cls['fields'] if f['name']==name)
            target = targets.get(name)
            if target is None or source['static'] != target['static']:
                raise MixinPlanError(ir['origin'], 'Shadow field missing or static identity differs: '+name)
            if source['initializer'] is not None or source['final']:
                raise MixinPlanError(ir['origin'], 'Source Shadow initializers/Java final declarations require separate lowering: '+name)
            raw = source['declared_type']
            other = target['declared_type']
            try:
                left=type_identity(raw,dict(cls,imports=ir['imports'],package=ir['package']),{'_project_types':types})
                right=type_identity(other,dict(target_cls,imports=target_ir['imports'],package=target_ir['package']),{'_project_types':types})
            except ValueError as error:
                raise MixinPlanError(ir['origin'],'Unresolved Shadow field identity: '+name+': '+str(error))
            if left != right:
                raise MixinPlanError(ir['origin'], 'Shadow field type differs: '+name)
            final = PREFIX+'Final' in names
            mutable = PREFIX+'Mutable' in names
            if final != target['final'] or (mutable and not final):
                raise MixinPlanError(ir['origin'], 'Shadow Final/Mutable must match a final target field: '+name)
            remove = None
            if mutable and target['initializer'] is not None and (right in ('boolean','byte','short','char','int','long','float','double','java.lang.String')):
                raise MixinPlanError(ir['origin'], 'Mutable constant-variable initializer may already be inlined in original bytecode: '+name)
            if mutable:
                target_node = next(n for n in children(field(next(n for n in target_ir['tree']['children'] if n['kind']=='class_declaration'), 'body'))
                                   if n['kind']=='field_declaration' and any(c['kind']=='variable_declarator' and text(target_ir,field(c,'name'))==name for c in children(n)))
                if sum(c['kind']=='variable_declarator' for c in children(target_node)) != 1:
                    raise MixinPlanError(ir['origin'], 'Mutable multi-field declaration requires splitting: '+name)
                modifiers = next(c for c in target_node['children'] if c['kind']=='modifiers')
                token = next(c for c in modifiers['children'] if c['kind']=='final')
                remove = token['span']
            bindings.append({'mixin':cls['java_name'],'mixin_file':ir['origin'],'target':target_cls['java_name'],
                             'target_file':target_ir['origin'],'field':name,'java_type':right,'static':target['static'],
                             'final':final,'mutable':mutable,'remove_final_span':remove})
    if len(bindings) != len(cls['fields']):
        raise MixinPlanError(ir['origin'], 'Unbound source Mixin field')
    return bindings


def check_handler(ir, cls, target_ir, target_cls, method, bindings, project_types):
    from java_mixin_plan import children, walk, field, text, MixinPlanError
    allowed = {b['field']:b for b in bindings}
    target_fields = {f['name'] for f in target_cls['fields']}
    locals_ = {p['name'] for p in method['parameters']}
    for n in walk(method['body']):
        if n['kind']=='variable_declarator':
            locals_.add(text(ir,field(n,'name')))
    if locals_ & target_fields:
        raise MixinPlanError(ir['origin'], 'Handler locals colliding with target fields require lexical binding review')
    for n in walk(method['body']):
        if n['kind'] in ('assignment_expression','update_expression'):
            left=field(n,'left') if n['kind']=='assignment_expression' else next((c for c in children(n) if c['kind'] not in ('++','--')),None)
            if left:
                spelling=text(ir,left)
                name=spelling.removeprefix('this.')
                if name in allowed and (spelling.startswith('this.') or name not in locals_) and allowed[name]['final'] and not allowed[name]['mutable']:
                    raise MixinPlanError(ir['origin'], 'Write to final Shadow without Mutable: '+name)
        if n['kind']=='field_access':
            name=text(ir,field(n,'field'))
            if name in target_fields and text(ir,field(n,'object'))!='this':
                raise MixinPlanError(ir['origin'], 'Target field through another qualifier requires explicit alias binding review: '+name)
            if name in target_fields and name not in allowed:
                raise MixinPlanError(ir['origin'], 'Target field requires an explicit Shadow: '+name)
        if n['kind']=='identifier' and text(ir,n) in target_fields-locals_-set(allowed):
            raise MixinPlanError(ir['origin'], 'Unbound target field identifier requires explicit Shadow/context: '+text(ir,n))
        if n['kind']=='method_invocation' and (field(n,'object') is None or text(ir,field(n,'object'))=='this'):
            name=text(ir,field(n,'name'))
            if name not in {m['name'] for m in cls['methods']}:
                raise MixinPlanError(ir['origin'], 'Unqualified target method requires explicit source method binding: '+name)
        if n['kind']=='method_reference' and children(n) and text(ir,children(n)[0])=='this':
            raise MixinPlanError(ir['origin'], 'Handler this-method references require explicit source binding review')
    if ir['package'] != target_ir['package']:
        imported={i['name'] for i in ir['imports'] if not i['static'] and not i['wildcard']}
        for n in walk(method['body']):
            if n['kind'] in ('type_identifier','identifier'):
                name=text(ir,n)
                own=ir['package']+'.'+name
                if own in project_types and own not in imported and (n['kind']=='type_identifier' or name not in locals_):
                    raise MixinPlanError(ir['origin'], 'Implicit Mixin-package reference needs explicit import for cross-package weaving: '+name)
