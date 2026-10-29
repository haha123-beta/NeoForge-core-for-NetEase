"""Prove a small context-independent item behavior; never execute Java or guess.

Only a private int field set by a direct Item(Properties,int) constructor and
returned unchanged by the sole instance method qualifies. Other subclasses fail
closed at native binding. No mod/package/field name is special-cased.
"""
import hashlib


def constant_fuel(owner, ir, canonical):
    if owner.get('owner') is not None or owner.get('interfaces') or owner.get('type_parameters'):
        return None
    if not owner.get('superclass') or canonical(owner['superclass']) != 'net.minecraft.world.item.Item':
        return None
    fields = owner['fields']
    if len(fields) != 1:
        return None
    member = fields[0]
    if member['static'] or member['declared_type'] != 'int' or 'private' not in member['modifiers']:
        return None
    if any(row['kind'] != 'field' for row in owner.get('initialization_order', [])):
        return None
    methods = [m for m in owner['methods'] if not m['constructor']]
    constructors = [m for m in owner['methods'] if m['constructor']]
    if len(methods) != 1 or not constructors:
        return None
    method = methods[0]
    if method['name'] != 'getBurnTime' or method['static'] or method['return_type'] != 'int' or 'public' not in method['modifiers']:
        return None
    params = method['parameters']
    if len(params) != 2 or [canonical(p['declared_type'].split('<',1)[0]) for p in params] != [
            'net.minecraft.world.item.ItemStack','net.minecraft.world.item.crafting.RecipeType']:
        return None
    source = ir['source_utf8'].encode('utf-8')
    def text(node):
        return source[node['span'][0]:node['span'][1]].decode('utf-8') if node else ''
    def child(node, field):
        return next((c for c in node.get('children',[]) if c.get('field') == field),None)
    def named(node):
        return [c for c in node.get('children',[]) if c['kind'] not in ('{','}',';', 'return')]
    def field_access(node):
        return (node and node['kind']=='field_access' and text(child(node,'object'))=='this'
                and text(child(node,'field'))==member['name'])
    body = named(method.get('body') or {})
    if len(body)!=1 or body[0]['kind']!='return_statement':
        return None
    values = named(body[0])
    if len(values)!=1 or not field_access(values[0]):
        return None
    for constructor in constructors:
        ps = constructor['parameters']
        if len(ps)!=2 or canonical(ps[0]['declared_type'])!='net.minecraft.world.item.Item.Properties' or ps[1]['declared_type']!='int':
            return None
        statements = named(constructor.get('body') or {})
        if len(statements)!=2 or statements[0]['kind']!='explicit_constructor_invocation' or statements[1]['kind']!='expression_statement':
            return None
        if text(child(statements[0],'constructor'))!='super':
            return None
        args = child(statements[0],'arguments')
        if text(args).replace(' ','').replace('\n','') != '('+ps[0]['name']+')':
            return None
        exprs = named(statements[1])
        if len(exprs)!=1 or exprs[0]['kind']!='assignment_expression':
            return None
        assignment = exprs[0]
        if not field_access(child(assignment,'left')) or text(child(assignment,'operator'))!='=' or text(child(assignment,'right'))!=ps[1]['name']:
            return None
    return {'abi':1,'kind':'CONSTANT_FUEL_PRIVATE_FIELD','field':member['name'],
            'java_source_sha256':hashlib.sha256(source).hexdigest(),
            'descriptor':'(Lnet/minecraft/world/item/ItemStack;Lnet/minecraft/world/item/crafting/RecipeType;)I'}
