from java_trading_signatures import constructor as trading_constructor, TYPES as TRADING_TYPES
"""Strict first Python-2 backend. Unsupported constructs produce diagnostics, never empty replacements."""
import ast
import json
import keyword
import os
from translation_observer import call as observed
from java_symbols import declarations
from java_annotation_policy import inspect_annotations
from java_project_types import validate_identities
from java_static_imports import plan as static_import_plan
from java_event_metadata import plan as event_annotation_plan
from java_mod_metadata import plan as mod_entrypoint_plan
from java_exception_signatures import CONSTRUCTORS as exception_constructors
from java_library_signatures import resolve as library_signature, resolve_field as library_field_signature, REVIEWED_PARENTS
from java_integer_literals import INTEGER_KINDS, literal_value
from java_inheritance import plan as inheritance_plan, runtime_declaration, runtime_interface_declaration
from java_method_overloads import canonical as canonical_method_type, signature as method_signature, family as method_family, select as select_overload, subtype as overload_subtype
from java_source_generics import runtime_signature
from java_value_types import BOXES, UNBOXES, widens as primitive_widens

KEYWORDS = set(keyword.kwlist) | {'print', 'exec'}


class NeedsLowering(ValueError):
    def __init__(self, node, reason, details=None):
        self.line = node.get('line', 1)
        self.reason = reason
        self.details = details or {}
        ValueError.__init__(self, 'Line ' + str(self.line) + ': ' + reason)


def generate(ir, project_types=None, dependency_index=None, defer_external_symbols=True):
    from java_source_lowering import lower
    ir=lower(ir)
    project_types = project_types or {}
    dependencies = []
    external_symbols=[];translated_dependencies=set();deferred_external_types=set()
    intrinsics = set()
    required_enums = set()
    symbols = declarations(ir)
    static_imports = static_import_plan(ir, project_types, NeedsLowering)
    ordered_classes, parents, external_classes = observed('inheritance_resolution',inheritance_plan,symbols['classes'], NeedsLowering, project_types, ir,observation={'file':ir['origin']})
    overload_unit = dict(ir, _classes=symbols['classes'], _external_classes=list(external_classes), _project_types=project_types)
    ignored_imports = validate_identities(ir, symbols, project_types, NeedsLowering)
    annotation_metadata, annotation_imports = inspect_annotations(ir, project_types, NeedsLowering)
    mod_entries,annotation_constant_imports=mod_entrypoint_plan(ir,symbols,annotation_metadata,project_types,NeedsLowering)
    annotation_imports.update(annotation_constant_imports)
    event_handlers,event_subscribers,event_constant_imports=event_annotation_plan(ir,symbols,annotation_metadata,project_types,NeedsLowering)
    annotation_imports.update(event_constant_imports)
    data = ir['source_utf8'].encode('utf-8')
    lines = ['# -*- coding: utf-8 -*-', 'from __future__ import absolute_import',
        'from java.lang import String as _nc_String', '']
    aliases, types = {}, {}
    resolved_static_calls = {}
    deferred_imports = []
    api_identities, required_api_types = {}, set()
    def text(node):
        if node and '_nc_text' in node: return node['_nc_text']
        return data[node['span'][0]:node['span'][1]].decode('utf-8') if node else ''
    def field(node, name):
        if (node is not None and node['kind'] == 'method_invocation' and name == 'object'
                and not any(c.get('field') == 'object' for c in node.get('children', []))):
            method_name = next((text(c) for c in node.get('children', []) if c.get('field') == 'name'), None)
            candidates = static_imports.get(method_name, {}).get('methods', [])
            if candidates and current is not None and find_method(method_name) is None:
                entries = []
                for binding in candidates:
                    if binding.get('error'): raise NeedsLowering(node, binding['error'])
                    owner = binding['declaration']
                    entries.extend((owner, method) for method in binding['methods'])
                arguments = next((c for c in node.get('children', []) if c.get('field') == 'arguments'), None)
                declaring, selected = select_overload(entries, [invocation_type(arg) for arg in named(arguments)], parents, overload_unit, node, NeedsLowering)
                resolved_static_calls[id(node)] = (declaring, selected)
                project_type_reference(declaring['java_name'], node)
                return {'kind': 'identifier', '_nc_text': declaring['java_name'], 'line': node['line'], 'children': []}
        return next((c for c in node.get('children', []) if c.get('field') == name), None)
    def named(node):
        return [c for c in node.get('children', []) if c['kind'] not in
            ('(', ')', '{', '}', ';', ',', 'line_comment', 'block_comment')]
    def walk(node):
        yield node
        for child in node.get('children', []):
            yield from walk(child)
    node_parents={id(child):parent for parent in walk(ir['tree']) for child in parent.get('children',[])}
    for node in walk(ir['tree']):
        if node['kind']=='method_reference' and any(c['kind']=='super' and c.get('field')!='object' for c in node.get('children',[])) and field(node,'object') is not None:
            raise NeedsLowering(node,'Qualified interface super invocation requires lowering')
        if node.get('text') in ('native', 'synchronized', 'volatile'):
            raise NeedsLowering(node, 'Thread/native semantics require lowering: ' + node['text'],
                {'category': 'thread_or_native', 'modifier': node['text']})
    for index, item in enumerate(ir['imports']):
        if item['static']: continue
        if index in ignored_imports:
            continue
        if item['name'] in annotation_imports:
            continue
        records = project_types.get(item['name'], [])
        if item['static'] or item['wildcard']:
            raise NeedsLowering(item, 'Static or wildcard import requires semantic resolution')
        alias = '_nc_type_' + str(index)
        while any(row['name'] == alias for row in symbols['classes']):
            alias += '_'
        if records:
            if len(records) != 1:
                raise NeedsLowering(item, 'Ambiguous project type: ' + item['name'],
                    {'category': 'ambiguous_project_type', 'java_name': item['name'], 'candidates': records})
            record = records[0]
            if not record['layout_matches_package']:
                raise NeedsLowering(item, 'Project package/source-root layout mismatch: ' + item['name'])
            if len(record['attribute_chain']) != 1:
                raise NeedsLowering(item, 'Nested project type export requires lowering')
            owner, name = record['module'], record['attribute_chain'][0]
            if record.get('external_dependency'):
                translated_dependencies.add(record['dependency_id'])
                external_symbols.append({'category':'TRANSLATED_DEPENDENCY_SYMBOL','symbol':item['name'],'dependency_id':record['dependency_id'],'deferred':False})
            else:dependencies.append(record['file'])
        else:
            if item['requires_semantic_resolution']:
                is_core=item['name'].startswith(('java.','javax.','net.minecraft.','net.neoforged.','com.mojang.','org.spongepowered.','neocore.'))
                if not defer_external_symbols or is_core:
                    raise NeedsLowering(item, 'Unresolved external import: ' + item['name'],{'category':'EXTERNAL_ABI_REQUIRED' if is_core else 'UNRESOLVED_EXTERNAL','symbol':item['name']})
                resolution=dependency_index.resolve(item['name']) if dependency_index else {'category':'UNRESOLVED_EXTERNAL','symbol':item['name'],'deferred':True}
                if not resolution.get('deferred'):raise NeedsLowering(item,'External symbol requires complete translated ABI: '+item['name'],resolution)
                external_symbols.append(resolution);deferred_external_types.add(item['name'])
                short=item['name'].rsplit('.',1)[-1];module,_,attribute=item['name'].rpartition('.')
                types[short]='getattr(__import__('+repr(module)+', globals(), locals(), ['+repr(attribute)+'], 0), '+repr(attribute)+')'
                api_identities[short]=item['name']
                continue
            owner, _, name = item['name'].rpartition('.')
            api_identities[name] = item['name']
            required_api_types.add(item['name'])
        if any(part in KEYWORDS for part in owner.split('.')):
            raise NeedsLowering(item, 'Keyword module path requires import adapter')
        lines.append('from ' + owner + ' import ' + name + ' as ' + alias)
        types[item['name'].rsplit('.', 1)[-1]] = alias
    for cls in symbols['classes']:
        remaining_review = set(cls['review']) - {'Inheritance resolution pending', 'Initializer block order needs semantic lowering'}
        constructors = [method for method in cls['methods'] if method['constructor']]
        if len({method_signature(method, cls, overload_unit) for method in constructors}) == len(constructors):
            remaining_review.discard('Overload dispatch and type erasure pending')
        if cls['kind'] not in ('class_declaration','interface_declaration') or cls['owner'] or remaining_review or cls['name'] in KEYWORDS:
            raise NeedsLowering(cls, 'Class kind, inheritance, nested types, initialization or overloads require lowering')
        if cls['name'] in ('_nc_Records', '_nc_Functional', '_nc_Int32', '_nc_String', '_nc_JavaArrays', '_nc_Collections', '_nc_System', '_nc_Exceptions', '_nc_ModEntrypoints', '_nc_RuntimeClasses', '_nc_EnumSets', '_nc_Goals', '_nc_Profilers', '_nc_MixinCallbacks', '_nc_NativeMixinHooks'):
            raise NeedsLowering(cls, 'Source class collides with generated runtime helper binding')
        if not cls['name'].isascii():
            raise NeedsLowering(cls, 'Non-ASCII class name requires Python2 export adapter')
        records = project_types.get(cls['java_name'], [])
        if records and records[0].get('source_sha256') not in (None, ir['source_sha256']):
            raise NeedsLowering(cls, 'Project source changed between declaration scan and generation')
        field_names = {f['name'] for f in cls['fields']}
        if field_names & {'_nc_JavaClassABI','_nc_JavaMethodsABI','_nc_JavaName','_nc_RecordComponents','_nc_record_sealed'} or any(method['name'] in ('_nc_JavaClassABI','_nc_JavaMethodsABI','_nc_JavaName','_nc_RecordComponents','_nc_record_sealed') for method in cls['methods']):
            raise NeedsLowering(cls, 'Source member collides with generated initialization ABI')
        method_names = {m['name'] for m in cls['methods'] if not m['constructor']}
        if (field_names & method_names)-{f['name'] for f in cls['fields'] if f.get('storage_name')}:
            raise NeedsLowering(cls, 'Java field/method namespaces collide in Python')
        if any(name.startswith('__') and name.endswith('__') for name in field_names | method_names):
            raise NeedsLowering(cls, 'Python special attribute collision requires member adapter')
        types[cls['name']] = cls['name']
    current = None
    current_return_type = None
    current_sam_return = None
    current_method_body = None
    current_method_constructor=False
    observed_calls=set()
    def observe_call(node,owner,name,parameters,return_type,kind):
        if not os.environ.get('NEOCORE_OBSERVABILITY_DIR'):return
        key=(tuple(node.get('span',())),owner,name,tuple(parameters),return_type,kind)
        if key in observed_calls:return
        observed_calls.add(key)
        from translation_observer import event
        event('compiler_resolution','OBSERVED',file=ir['origin'],source_sha256=ir['source_sha256'],java_class=(current or {}).get('java_name'),
            source_span=node.get('span'),owner=owner,name=name,parameters=list(parameters),return_type=return_type,
            observation_kind=kind,descriptor_status='COMPILE_TIME_SIGNATURE_NOT_AN_EXPRESSION_ANCHOR')
    def observe_selected(node,owner,method,name,kind):
        if not os.environ.get('NEOCORE_OBSERVABILITY_DIR'):return
        identity=owner.get('erased_java_name',owner['java_name'])
        try:
            parameters=runtime_signature(method,owner,overload_unit)
            result='void' if name=='<init>' else canonical_method_type(method['return_type'],owner,overload_unit)
        except (ValueError,KeyError,TypeError):
            parameters=[p.get('declared_type','<unknown>') for p in method.get('parameters',[])]
            result=method.get('return_type');kind+='_ERASURE_UNKNOWN'
        observe_call(node,identity,name,parameters,result,kind)
    lambda_helpers = []
    lambda_counter = [0]
    def find_member(name, kind, owner=None):
        owner = current if owner is None else owner
        if kind=='methods' and owner is not None:
            entries=method_family(owner,name,parents,overload_unit)
            return entries[0] if entries else (None,None)
        while owner is not None:
            member = next((row for row in owner[kind] if row['name'] == name and not row.get('constructor')), None)
            if member is not None:
                return owner, member
            owner = parents.get(owner['name'])
        return None, None
    def find_field(name):
        return find_member(name, 'fields')[1]
    def find_method(name, owner=None):
        return find_member(name, 'methods', owner)[1]
    def static_owner(name, kind):
        return find_member(name, kind)[0]['name']
    def project_type_reference(name, node):
        if name in types:
            return types[name]
        for alias, identity in api_identities.items():
            if name == identity and alias in types:
                return types[alias]
        parts = name.split('.')
        if parts[0] in api_identities and len(parts) > 1:
            identity = api_identities[parts[0]] + '.' + '.'.join(parts[1:])
            if identity in ir.get('known_nested_api_types', []) and identity not in project_types:
                reference = types[parts[0]]
                for member in parts[1:]:
                    reference = 'getattr(' + reference + ', ' + repr(member) + ')'
                required_api_types.add(identity)
                types[name] = reference
                return reference
        identity = name if '.' in name else '.'.join(filter(None, (ir.get('package'), name)))
        records = project_types.get(identity, [])
        if not records:
            implicit='java.lang.'+name if '.' not in name else name
            if implicit in ir.get('known_java_lang_api_types',[]) or implicit=='java.io.Closeable':
                alias='_nc_lang_'+str(len(required_api_types))
                while alias in types.values() or any(cls['name']==alias for cls in symbols['classes']):alias+='_' 
                deferred_imports.append('from '+implicit.rpartition('.')[0]+' import '+implicit.rsplit('.',1)[1]+' as '+alias)
                required_api_types.add(implicit)
                api_identities[name]=implicit
                types[name]=alias
                return alias
            raise NeedsLowering(node, 'Unresolved project type: ' + identity)
        if len(records) != 1:
            raise NeedsLowering(node, 'Ambiguous project type: ' + identity,
                {'category': 'ambiguous_project_type', 'java_name': identity, 'candidates': records})
        record = records[0]
        if not record['layout_matches_package']:
            raise NeedsLowering(node, 'Project package/source-root layout mismatch: ' + identity)
        if len(record['attribute_chain']) != 1 or record['kind'] not in ('class_declaration','interface_declaration'):
            raise NeedsLowering(node, 'Nested/non-class project type requires lowering: ' + identity)
        if record.get('external_dependency'):
            translated_dependencies.add(record['dependency_id'])
            resolution={'category':'TRANSLATED_DEPENDENCY_SYMBOL','symbol':identity,'dependency_id':record['dependency_id'],'deferred':False}
            if resolution not in external_symbols:external_symbols.append(resolution)
        else:dependencies.append(record['file'])
        # Resolve only when used, through the existing private source importer.
        # Eagerly importing every same-package class causes spurious cycles.
        reference = ('getattr(__import__(' + repr(record['module']) +
            ', globals(), locals(), [' + repr(record['attribute_chain'][0]) + '], 0), ' +
            repr(record['attribute_chain'][0]) + ')')
        types[name] = reference
        return reference
    locals_map = {}
    local_types = {}
    local_counter = [0]
    uninitialized = set()
    loop_depth = [0]
    for_counter = [0]
    assignment_counter = [0]
    static_context = False
    from java_type_queries import request_scope
    type_query=request_scope()
    def get_attr(receiver, name):
        return 'getattr(' + receiver + ', ' + repr(name) + ')'
    def api_type_identity(node):
        if node is None:return None
        raw=text(node)
        first,_,rest=raw.partition('.')
        if first in locals_map or find_field(first) is not None:return None
        identity=api_identities.get(first)
        if identity is None and first=='Float' and not any(c['name']==first for c in symbols['classes']) and '.'.join(filter(None,(ir.get('package'),first))) not in project_types:identity='java.lang.Float'
        implicit='java.lang.'+first
        if identity is None and implicit in ir.get('known_java_lang_api_types',[]) and not any(c['name']==first for c in symbols['classes']) and '.'.join(filter(None,(ir.get('package'),first))) not in project_types:
            identity=implicit
        if identity is None:return None
        identity += ('.'+rest) if rest else ''
        known=set(api_identities.values())|set(ir.get('known_nested_api_types',[]))|set(ir.get('runtime_enum_types',{}))|set(ir.get('known_java_lang_api_types',[]))
        if identity in ir.get('runtime_enum_types',{}):required_enums.add(identity)
        return identity if identity in known else None
    def type_qualifier(node):
        return (node is not None and (text(node) in types or api_type_identity(node) is not None or reference_class(text(node)) is not None)
                and text(node).split('.',1)[0] not in locals_map
                and find_field(text(node).split('.',1)[0]) is None)
    def is_boxed_integer(name):
        if name == 'java.lang.Integer':
            return name not in project_types
        if name != 'Integer' or any(row['name'] == 'Integer' for row in symbols['classes']):
            return False
        imported = next((item['name'] for item in ir['imports'] if item['name'].rsplit('.', 1)[-1] == name), None)
        if imported is not None:
            return imported == 'java.lang.Integer' and imported not in project_types
        return '.'.join(filter(None, (ir.get('package'), name))) not in project_types

    @type_query
    def library_method(node):
        if any(c['kind']=='super' and c.get('field')!='object' for c in node.get('children',[])):return None
        receiver=field(node,'object')
        if receiver is None or receiver['kind'] in ('this','super'):return None
        receiver_type=original_type(receiver) or expression_type(receiver)
        if receiver_type is None and text(receiver) not in locals_map and find_field(text(receiver)) is None:
            receiver_type=api_type_identity(receiver)
        if receiver_type is None:return None
        if canonical_method_type(receiver_type.split('<',1)[0],current,overload_unit)=='java.util.EnumSet':
            intrinsics.add('neocore.runtime.EnumSets@1')
        args=named(field(node,'arguments'))
        argument_types=[invocation_type(arg) for arg in args]
        if canonical_method_type(receiver_type.split('<',1)[0],current,overload_unit)=='net.neoforged.neoforge.common.extensions.IMenuTypeExtension' and text(field(node,'name'))=='create' and len(args)==1 and args[0]['kind']=='method_reference':
            parts=[c for c in named(args[0]) if c['kind']!='::']
            if len(parts)!=2 or text(parts[1])!='new':raise NeedsLowering(args[0],'Menu factory inference requires a constructor reference or a typed factory variable')
            owner=reference_class(text(parts[0]))
            if owner is None:raise NeedsLowering(args[0],'Menu constructor reference requires a resolved source class')
            from java_generic_contracts import proves_bound
            if not proves_bound(owner['java_name'],'net.minecraft.world.inventory.AbstractContainerMenu',overload_unit,project_types):raise NeedsLowering(args[0],'Menu factory return type must extend AbstractContainerMenu')
            argument_types=['net.neoforged.neoforge.network.IContainerFactory<'+owner['java_name']+'>']
        elif canonical_method_type(receiver_type.split('<',1)[0],current,overload_unit)=='net.neoforged.neoforge.common.extensions.IMenuTypeExtension' and text(field(node,'name'))=='create' and len(args)==1 and argument_types[0]:
            from java_library_signatures import generic_arguments
            from java_generic_contracts import proves_bound
            try:parameters=generic_arguments(argument_types[0].replace(' ',''))
            except ValueError as error:raise NeedsLowering(args[0],str(error))
            if len(parameters)!=1 or not proves_bound(canonical_method_type(parameters[0],current,overload_unit),'net.minecraft.world.inventory.AbstractContainerMenu',overload_unit,project_types):raise NeedsLowering(args[0],'Menu factory type argument requires a proven AbstractContainerMenu subtype')
        try:
            if canonical_method_type(receiver_type.split('<',1)[0],current,overload_unit) in ('net.neoforged.neoforge.registries.DeferredRegister.Blocks','net.neoforged.neoforge.registries.DeferredRegister.Items') and text(field(node,'name'))=='register' and len(args)==2 and args[1]['kind']=='lambda_expression':
                inferred=infer_supplier(args[1])
                if inferred:argument_types[1]=inferred
            result=library_signature(receiver_type,text(field(node,'name')),len(args),argument_types,lambda value:canonical_method_type(value,current,overload_unit),ir.get('runtime_enum_types',{}),proves=lambda a,b:overload_subtype(a,b,parents,overload_unit))
            if result and result.get('event_consumer'):
                callback=args[0];event_type=None
                if callback['kind']=='lambda_expression':
                    parameters=field(callback,'parameters');parts=[parameters] if parameters['kind']=='identifier' else named(parameters)
                    if len(parts)==1 and parts[0]['kind']=='formal_parameter':event_type=canonical_method_type(text(field(parts[0],'type')),current,overload_unit)
                elif callback['kind']=='method_reference':
                    parts=[c for c in named(callback) if c['kind']!='::']
                    if len(parts)==2:
                        receiver,name_node=parts;is_class=type_qualifier(receiver)
                        owner=current if receiver['kind']=='this' else parents.get(current['name']) if receiver['kind']=='super' else reference_class(text(receiver)) if is_class else reference_class(expression_type(receiver))
                        entries=method_family(owner,text(name_node),parents,overload_unit) if owner else []
                        candidates=[]
                        for declaring,method in entries:
                            if is_class and not method['static'] and not method['parameters']:candidates.append(owner['java_name'])
                            elif len(method['parameters'])==1:candidates.append(canonical_method_type(method['parameters'][0]['declared_type'],declaring,overload_unit))
                        if len(candidates)==1:event_type=candidates[0]
                elif argument_types[0] and argument_types[0].startswith('java.util.function.Consumer<'):
                    from java_library_signatures import generic_arguments
                    values=generic_arguments(argument_types[0])
                    if len(values)==1:event_type=values[0]
                from java_generic_contracts import proves_bound
                if not event_type or not proves_bound(event_type,'net.neoforged.bus.api.Event',overload_unit,project_types):
                    raise NeedsLowering(callback,'Event listener requires one proven Event subtype; implicit/ambiguous event inference needs review')
                from java_official_event_hierarchy import ABSTRACT_TYPES
                if event_type in ABSTRACT_TYPES:
                    raise NeedsLowering(callback,'Official event bus rejects abstract event listener types: '+event_type)
                result=dict(result,parameters=['java.util.function.Consumer<'+event_type+'>'])
                argument_types=[result['parameters'][0]]
            if result and result.get('checked_arguments'):
                for index in result.get('poly_function_arguments',[]):
                    if argument_types[index] is None and args[index]['kind'] in ('lambda_expression','method_reference'):
                        # Expression lowering still proves the SAM arity and
                        # return type against this exact selected target.
                        argument_types[index]=result['parameters'][index]
                if result.get('deferred_runnable'):
                    callback=args[0];proven=argument_types[0]=='java.lang.Runnable'
                    if callback['kind']=='method_reference':
                        parts=[c for c in named(callback) if c['kind']!='::']
                        if len(parts)==2:
                            receiver,name_node=parts;is_class=type_qualifier(receiver)
                            owner=current if receiver['kind']=='this' else parents.get(current['name']) if receiver['kind']=='super' else reference_class(text(receiver)) if is_class else reference_class(expression_type(receiver))
                            entries=method_family(owner,text(name_node),parents,overload_unit) if owner else []
                            candidates=[m for d,m in entries if not m['parameters'] and m['return_type']=='void' and (not is_class or m['static'])]
                            proven=len(candidates)==1
                    elif callback['kind']=='lambda_expression':
                        parameters=field(callback,'parameters');body=field(callback,'body')
                        proven=not named(parameters) and body['kind']=='block' and not any(n['kind']=='return_statement' and named(n) for n in walk(body))
                    if not proven:raise NeedsLowering(callback,'Deferred work requires a proven Runnable; Supplier result adaptation needs review')
                    argument_types=['java.lang.Runnable']
                declaration={'java_name':canonical_method_type(receiver_type.split('<',1)[0],current,overload_unit),'name':'_nc_checked_api','external':True,'imports':[],'package':None}
                signature={'name':text(field(node,'name')),'constructor':False,'parameters':[{'declared_type':p,'varargs':False} for p in result['parameters']]}
                select_overload([(declaration,signature)],argument_types,parents,overload_unit,node,NeedsLowering)
            for index in (result or {}).get('erased_bridge_arguments',[]):
                argument=args[index]
                operand=field(argument,'value') if argument['kind']=='cast_expression' else None
                if operand is None or not overload_subtype(invocation_type(operand),result['parameters'][index],parents,overload_unit):
                    raise NeedsLowering(argument,'Erased codec bridge argument requires a proven original type')
            if result and result.get('statement_only') and node_parents.get(id(node),{}).get('kind')!='expression_statement':raise NeedsLowering(node,'Future return observation from enqueueWork requires CompletableFuture support')
            if result:observe_call(node,result.get('static_owner') or canonical_method_type(receiver_type.split('<',1)[0],current,overload_unit),text(field(node,'name')),result['parameters'],result['return_type'],'LIBRARY_RECEIVER_OR_STATIC_OWNER')
            return result
        except NeedsLowering:raise
        except ValueError as error:raise NeedsLowering(node,str(error),
            {'category':'api_call_contract','owner':canonical_method_type(receiver_type.split('<',1)[0],current,overload_unit),
             'method':text(field(node,'name')),'argument_types':argument_types})

    @type_query
    def original_type(node):
        if node is None:
            return None
        if node['kind']=='assignment_expression':return original_type(field(node,'left'))
        if node['kind'] == 'identifier':
            name = text(node)
            return local_types.get(name) or (find_field(name)['declared_type'] if find_field(name) else static_constant(name).get('type'))
        if node['kind'] == 'method_invocation':
            record=library_method(node)
            return record['return_type'] if record else None
        if node['kind']=='cast_expression':return canonical_method_type(text(field(node,'type')),current,overload_unit)
        if node['kind'] == 'array_access':
            array_type = expression_type(field(node, 'array'))
            return array_type[:-2] if array_type and array_type.endswith('[]') else None
        if node['kind'] == 'class_literal':
            target=next((child for child in named(node) if child['kind'] not in ('.','class')),None)
            return 'java.lang.Class<' + canonical_method_type(text(target),current,overload_unit) + '>' if target else None
        if node['kind'] == 'field_access':
            receiver = field(node, 'object')
            static_record=library_field(node)
            if static_record:return static_record['return_type']
            enum_type = api_type_identity(receiver)
            if enum_type=='net.minecraft.world.entity.MobCategory':
                from java_entity_signatures import CATEGORIES
                if text(field(node,'field')) not in CATEGORIES:raise NeedsLowering(node,'Unknown MobCategory field')
                return enum_type
            if enum_type in ir.get('runtime_enum_types',{}):
                if text(field(node,'field')) in ir['runtime_enum_types'][enum_type]['constants']:return enum_type
            if receiver['kind'] in ('this','super'):
                declaration = current if receiver['kind'] == 'this' else parents.get(current['name'])
            else:
                declaration = reference_class(text(receiver)) if type_qualifier(receiver) else reference_class(expression_type(receiver))
            if text(field(node, 'field')) == 'length' and (expression_type(receiver) or '').endswith('[]'):
                return 'int'
            declaring, member = find_member(text(field(node, 'field')), 'fields', declaration) if declaration is not None else (None,None)
            return canonical_method_type(member['declared_type'], declaring, overload_unit) if member else None
        return None

    @type_query
    def library_field(node):
        if node is None or node['kind']!='field_access':return None
        receiver=field(node,'object')
        receiver_type=api_type_identity(receiver) or original_type(receiver) or expression_type(receiver)
        try:return library_field_signature(receiver_type,text(field(node,'field')),lambda value:canonical_method_type(value,current,overload_unit))
        except ValueError as error:raise NeedsLowering(node,str(error))

    @type_query
    def invocation_type(node):
        if node is not None and node['kind']=='method_invocation':
            factory=library_method(node)
            if factory and factory.get('polymorphic_empty_collection')=='map':return '<poly-empty-map>'
            if factory and factory.get('polymorphic_empty_optional'):return '<poly-empty-optional>'
        kind = node['kind']
        if kind=='cast_expression':return original_type(node)
        if kind=='this':return current['java_name']
        if kind=='super':return (parents.get(current['name']) or {}).get('java_name')
        if kind=='instanceof_expression':return 'boolean'
        if kind == 'null_literal':
            return '<null>'
        if kind == 'string_literal':
            return 'java.lang.String'
        if kind == 'array_creation_expression':
            count = sum(1 if child['kind']=='dimensions_expr' else text(child).count('[') for child in node.get('children',[]) if child['kind'] in ('dimensions_expr','dimensions'))
            return canonical_method_type(text(field(node,'type')),current,overload_unit)+'[]'*count
        if kind == 'array_access':
            return canonical_method_type(original_type(node), current, overload_unit)
        if kind == 'object_creation_expression':
            return canonical_method_type(text(field(node, 'type')), current, overload_unit)
        if kind == 'parenthesized_expression':
            return invocation_type(named(node)[0])
        declared = original_type(node) or expression_type(node)
        return canonical_method_type(declared, current, overload_unit)

    def converted_argument(node, formal_type, owner):
        actual, target = invocation_type(node), canonical_method_type(formal_type, owner, overload_unit)
        if actual in BOXES and target in UNBOXES and BOXES[actual]!=target:
            raise NeedsLowering(node,'Invocation does not allow narrowing followed by boxing')
        if actual in BOXES and target in BOXES and not primitive_widens(actual,target):
            raise NeedsLowering(node,'Invocation primitive conversion would narrow')
        if actual in UNBOXES and target in BOXES and not primitive_widens(UNBOXES[actual],target):
            raise NeedsLowering(node,'Invocation unboxing conversion would narrow')
        code = expr(node, formal_type)
        if actual == 'java.lang.Integer' and target == 'int':
            intrinsics.add('neocore.runtime.Functional@3')
            return '_nc_Functional.unboxInt(' + code + ')'
        if (target == 'java.lang.Integer' and actual in ('int','java.lang.Integer')) or (actual == 'int' and target == 'java.lang.Object'):
            intrinsics.add('neocore.runtime.Functional@3')
            return '_nc_Functional.boxInt(' + code + ')'
        return code

    def scalar_type(node):
        """Only resolve scalar identities; leave generic/diamond inference alone."""
        if node is None:return None
        if node['kind']=='parenthesized_expression':return scalar_type(named(node)[0])
        raw=original_type(node)
        if raw is None and node['kind']=='object_creation_expression':raw=text(field(node,'type'))
        if raw:
            if '<' in raw or '[' in raw:return None
            identity=canonical_method_type(raw,current,overload_unit)
            return identity if identity in BOXES or identity in UNBOXES else None
        if node['kind'] in INTEGER_KINDS or node['kind'] in ('true','false','character_literal','decimal_floating_point_literal','unary_expression','binary_expression','ternary_expression','instanceof_expression','method_invocation'):
            identity=expression_type(node)
            if identity and '<' not in identity and '[' not in identity:identity=canonical_method_type(identity,current,overload_unit)
            return identity if identity in BOXES or identity in UNBOXES else None
        return None

    def validate_sam_return(node,expected):
        from java_method_overloads import canonical_return
        if node is None:
            if expected!='void':raise NeedsLowering(current,'Non-void functional target requires a return value')
            return
        if expected=='void':raise NeedsLowering(node,'Void functional target cannot return a value')
        if node['kind'] in ('lambda_expression','method_reference'):
            # Nested functional expressions take their type from the return
            # context; their body/reference is validated by expr below.
            functional_target(expected,node)
            return
        actual=invocation_type(node)
        target=canonical_return(expected,current,overload_unit)
        if actual is None:raise NeedsLowering(node,'Functional return compile-time type is unresolved')
        actual=canonical_return(actual,current,overload_unit)
        if overload_subtype(actual,target,parents,overload_unit):return
        if actual in BOXES and target in BOXES and primitive_widens(actual,target):return
        if actual in UNBOXES and target in BOXES and primitive_widens(UNBOXES[actual],target):return
        if actual in BOXES and overload_subtype(BOXES[actual],target,parents,overload_unit):return
        if target=='float' and actual=='int' or target=='int' and actual=='java.lang.Integer' or actual=='int' and target in ('java.lang.Integer','java.lang.Object'):return
        raise NeedsLowering(node,'Functional return type does not satisfy target: '+actual+' -> '+target)

    default_constructors = {}
    def constructor_entries(owner):
        entries = [method for method in owner['methods'] if method['constructor']]
        if not entries:
            default = default_constructors.setdefault(owner['java_name'], {'name': owner['name'],
                'constructor': True, 'static': False, 'parameters': [], 'return_type': None,
                'body': {'kind': 'block', 'children': [], 'line': owner['line']}, 'line': owner['line']})
            entries = [default]
        return entries

    def has_poly_arguments(arguments):
        return any(arg['kind']=='method_invocation' and (library_method(arg) or {}).get('polymorphic_empty_collection') for arg in arguments)

    def infer_supplier(node):
        if node['kind']!='lambda_expression':return None
        parameters=field(node,'parameters');body=field(node,'body')
        if named(parameters) or parameters['kind']=='identifier' or body['kind']=='block':return None
        result=invocation_type(body)
        return 'java.util.function.Supplier<'+result+'>' if result and result!='<null>' else None
    def selected_constructor(owner, arguments, node):
        entries = [(owner, method) for method in constructor_entries(owner)]
        if len(entries) == 1 and not owner.get('runtime_contract') and owner.get('record_components') is None and len(entries[0][1]['parameters']) == len(arguments) and not has_poly_arguments(arguments):
            selected=entries[0][1]
        else:selected=select_overload(entries, [invocation_type(arg) for arg in arguments], parents, overload_unit, node, NeedsLowering)[1]
        observe_selected(node,owner,selected,'<init>','CONSTRUCTOR_SELECTED')
        return selected

    def selected_method(owner, name, arguments, node):
        # Later expression/type passes must not reconsider the entire owner and
        # accidentally select a private or instance overload excluded above.
        if id(node) in resolved_static_calls:
            return resolved_static_calls[id(node)]
        entries = method_family(owner, name, parents, overload_unit)
        entries=[(declaring,method) for declaring,method in entries if 'private' not in method.get('modifiers',[]) or declaring['java_name']==current['java_name']]
        if not entries:
            raise NeedsLowering(node, 'Unresolved declared method: ' + name, {'category': 'unresolved_method', 'name': name})
        if any(method.get('type_parameters') for declaring,method in entries):
            if len(entries)!=1:raise NeedsLowering(node,'Generic overload inference requires lowering')
            from java_method_generics import instantiate
            declaring,method=entries[0]
            try:
                method,actuals=instantiate(declaring,method,[invocation_type(arg) for arg in arguments],overload_unit,parents,lambda index,formal:infer_supplier(arguments[index]) if formal.startswith('java.util.function.Supplier<') else None)
            except ValueError as error:raise NeedsLowering(node,str(error))
            selected=select_overload([(declaring,method)],actuals,parents,overload_unit,node,NeedsLowering)
        elif len(entries) == 1 and not any(p.get('varargs') for p in entries[0][1]['parameters']) and not entries[0][0].get('runtime_contract') and not entries[0][0].get('runtime_interface_contract') and len(entries[0][1]['parameters']) == len(arguments) and not has_poly_arguments(arguments):
            selected=entries[0]
        else:selected=select_overload(entries, [invocation_type(arg) for arg in arguments], parents, overload_unit, node, NeedsLowering)
        declaring,method=selected
        observe_selected(node,declaring,method,name,'SOURCE_OR_NATIVE_CONTRACT_SELECTED')
        return selected

    def check_runtime_access(declaring, method, receiver, node):
        if not declaring or not declaring.get('runtime_contract') or method.get('visibility') != 'protected':
            return
        if current.get('package', ir.get('package')) == declaring.get('package'):
            return
        ancestor = current
        while ancestor is not None and ancestor.get('java_name') != declaring['java_name']:
            ancestor = parents.get(ancestor['name'])
        if ancestor is None:
            raise NeedsLowering(node, 'Protected runtime method requires subclass access: ' + method['name'])
        if method['static'] or receiver is None or receiver['kind'] in ('this', 'super'):
            return
        owner = reference_class(expression_type(receiver))
        while owner is not None and owner.get('java_name') != current.get('java_name'):
            owner = parents.get(owner['name'])
        if owner is None:
            raise NeedsLowering(node, 'Protected runtime receiver must be the accessing subclass or its subtype')

    def numeric_operand(node, target=None):
        code = expr(node)
        actual=scalar_type(node)
        primitive=UNBOXES.get(actual,actual)
        if actual in UNBOXES:
            intrinsics.add('neocore.runtime.Functional@9')
            code='_nc_Functional.unbox('+repr(primitive)+', '+code+')'
        target=target or ('int' if primitive=='char' else primitive)
        if primitive in BOXES and target!=primitive:
            intrinsics.add('neocore.runtime.Functional@9')
            code='_nc_Functional.castPrimitive('+repr(target)+', '+repr(primitive)+', '+code+')'
        return code

    primitive_numeric_types={'byte','short','char','int','long','float','double'}
    def numeric_type(name):
        name=canonical_method_type(name,current,overload_unit) if name else None
        name=UNBOXES.get(name,name)
        return name if name in primitive_numeric_types else None
    def binary_numeric_type(left,right):
        left,right=numeric_type(left),numeric_type(right)
        if left is None or right is None:return None
        if 'double' in (left,right):return 'double'
        if 'float' in (left,right):return 'float'
        if 'long' in (left,right):return 'long'
        return 'int'

    @type_query
    def expression_type(node):
        if node is None:
            return None
        kind = node['kind']
        if kind=='assignment_expression':return original_type(field(node,'left'))
        if kind=='this':return current['java_name']
        if kind=='super':return (parents.get(current['name']) or {}).get('java_name')
        if kind=='cast_expression':return original_type(node)
        if kind=='instanceof_expression':return 'boolean'
        if kind == 'null_literal':return '<null>'
        if kind == 'array_creation_expression':
            count = sum(1 if child['kind']=='dimensions_expr' else text(child).count('[') for child in node.get('children',[]) if child['kind'] in ('dimensions_expr','dimensions'))
            return canonical_method_type(text(field(node,'type')),current,overload_unit)+'[]'*count
        if kind == 'array_access':
            return original_type(node)
        if kind == 'object_creation_expression':
            return canonical_method_type(text(field(node, 'type')), current, overload_unit)
        if kind == 'field_access':
            return original_type(node)
        if kind == 'string_literal':
            return 'java.lang.String'
        if kind in ('true', 'false'):
            return 'boolean'
        if kind=='character_literal':return 'char'
        if kind in INTEGER_KINDS:
            return 'long' if text(node)[-1:] in ('L', 'l') else 'int'
        if kind=='decimal_floating_point_literal':return 'float' if text(node)[-1:] in ('f','F') else 'double'
        if kind == 'unary_expression' and text(field(node, 'operator')) == '~':
            return 'int' if expression_type(field(node, 'operand')) == 'int' else None
        if kind == 'binary_expression' and text(field(node, 'operator')) in ('&', '|', '^', '<<', '>>', '>>>'):
            left_type, right_type = expression_type(field(node, 'left')), expression_type(field(node, 'right'))
            if left_type == right_type == 'int':
                return 'int'
            if left_type == right_type == 'boolean' and text(field(node, 'operator')) in ('&', '|', '^'):
                return 'boolean'
            return None
        if kind == 'unary_expression' and text(field(node, 'operator')) in ('+', '-'):
            return expression_type(field(node, 'operand'))
        if kind == 'binary_expression' and text(field(node, 'operator')) in ('+', '-', '*', '/', '%'):
            left_type, right_type = expression_type(field(node, 'left')), expression_type(field(node, 'right'))
            if text(field(node,'operator')) == '+' and any(canonical_method_type(t,current,overload_unit)=='java.lang.String' for t in (left_type,right_type) if t):
                return 'java.lang.String'
            return binary_numeric_type(left_type,right_type)
        if kind == 'binary_expression' and text(field(node, 'operator')) in ('<', '>', '<=', '>=', '==', '!='):
            left_type, right_type = expression_type(field(node, 'left')), expression_type(field(node, 'right'))
            operator = text(field(node, 'operator'))
            if operator in ('==','!=') and reference_equality(left_type,right_type):return 'boolean'
            bool_types=('boolean','java.lang.Boolean')
            if binary_numeric_type(left_type,right_type) or (operator in ('==', '!=') and scalar_type(field(node,'left')) in bool_types and scalar_type(field(node,'right')) in bool_types):
                return 'boolean'
        if kind == 'identifier':
            name = text(node)
            if name in local_types:
                return "int" if is_boxed_integer(local_types[name]) else local_types[name]
            member = find_field(name)
            return member['declared_type'] if member else static_constant(name).get('type')
        if kind == 'parenthesized_expression':
            return expression_type(named(node)[0])
        if kind == 'field_access' and field(node, 'object')['kind'] in ('this', 'super'):
            name = text(field(node, 'field'))
            member = find_field(name)
            return member['declared_type'] if member else None
        if kind == 'method_invocation':
            record=library_method(node)
            if record:return 'int' if is_boxed_integer(record['return_type']) else record['return_type']
            receiver = field(node, 'object')
            if receiver is not None and text(field(node, 'name')) == 'intValue' and not named(field(node, 'arguments')) and is_boxed_integer(original_type(receiver) or expression_type(receiver)):
                return 'int'
            if receiver is None or receiver['kind'] in ('this', 'super'):
                owner = parents.get(current['name']) if receiver is not None and receiver['kind'] == 'super' else current
                if owner is None:
                    return None
                declaring, method = selected_method(owner, text(field(node, 'name')), named(field(node, 'arguments')), node)
                return method['return_type']
            receiver_decl = reference_class(text(receiver)) if type_qualifier(receiver) else reference_class(expression_type(receiver))
            if receiver_decl is not None:
                declaring, method = selected_method(receiver_decl, text(field(node, 'name')), named(field(node, 'arguments')), node)
                return canonical_method_type(method['return_type'], declaring, overload_unit)
        if kind == 'unary_expression' and text(field(node, 'operator')) == '!':
            if scalar_type(field(node, 'operand')) in ('boolean','java.lang.Boolean'):
                return 'boolean'
        if kind=='ternary_expression':
            left=expression_type(field(node,'consequence'));right=expression_type(field(node,'alternative'))
            if left is not None and left==right:return left
        if kind == 'binary_expression' and text(field(node, 'operator')) in ('&&', '||'):
            if all(scalar_type(field(node,k)) in ('boolean','java.lang.Boolean') for k in ('left','right')):
                return 'boolean'
        return None

    def static_constant(name):
        candidates = static_imports.get(name, {}).get('constants', [])
        if len(candidates) > 1:
            raise NeedsLowering(candidates[0]['item'], 'Ambiguous static field import: ' + name)
        if not candidates: return {}
        if candidates[0].get('error'): raise NeedsLowering(candidates[0]['item'], candidates[0]['error'])
        return candidates[0]

    def reference_equality(left_type,right_type):
        primitives={'boolean','byte','short','char','int','long','float','double','void'}
        left=canonical_method_type(left_type,current,overload_unit) if left_type else None
        right=canonical_method_type(right_type,current,overload_unit) if right_type else None
        if not left or not right or left in primitives or right in primitives:return False
        if '<null>' in (left,right):return True
        # String interning/constant-pool identity needs its own implementation.
        if 'java.lang.String' in (left,right):return False
        if left==right or 'java.lang.Object' in (left,right):return True
        if overload_subtype(left,right,parents,overload_unit) or overload_subtype(right,left,parents,overload_unit):return True
        def ancestors(identity):
            pending=[reference_class(identity)];result=set()
            while pending:
                owner=pending.pop()
                if owner is None or owner['java_name'] in result:continue
                result.add(owner['java_name'])
                pending.extend(owner.get('source_interfaces',[]))
                pending.append(parents.get(owner['name']))
            pending=[identity]+list(result)
            while pending:
                for parent in REVIEWED_PARENTS.get(pending.pop(),[]):
                    if parent not in result:result.add(parent);pending.append(parent)
            return result
        return left in ancestors(right) or right in ancestors(left)

    def set_uninitialized(values):
        uninitialized.clear();uninitialized.update(values)

    def condition_flow(node):
        if scalar_type(node)=='java.lang.Boolean':
            intrinsics.add('neocore.runtime.Functional@9')
            state=set(uninitialized)
            return "_nc_Functional.unbox('boolean', "+expr(node)+')',state,state.copy()
        if expression_type(node) != 'boolean':
            raise NeedsLowering(node, 'Condition requires resolved primitive boolean type')
        if node['kind']=='parenthesized_expression':
            code,yes,no=condition_flow(named(node)[0]);return '('+code+')',yes,no
        operator=text(field(node,'operator'))
        if node['kind']=='unary_expression' and operator=='!':
            code,yes,no=condition_flow(field(node,'operand'));return '(not '+code+')',no,yes
        if node['kind']=='binary_expression' and operator in ('&&','||'):
            left,ly,ln=condition_flow(field(node,'left'))
            set_uninitialized(ly if operator=='&&' else ln)
            right,ry,rn=condition_flow(field(node,'right'))
            yes,no=(ry,ln|rn) if operator=='&&' else (ly|ry,rn)
            set_uninitialized(yes|no)
            return '('+left+(' and ' if operator=='&&' else ' or ')+right+')',yes,no
        code=expr(node);state=set(uninitialized)
        return code,state,state

    def boolean_expression(node):
        code,yes,no=condition_flow(node);set_uninitialized(yes|no)
        return code

    def always_abrupt(node):
        if node is None:return False
        if node['kind'] in ('return_statement','throw_statement'):return True
        if node['kind'] in ('block','constructor_body'):
            children=named(node)
            return bool(children) and always_abrupt(children[-1])
        if node['kind']=='if_statement':return always_abrupt(field(node,'consequence')) and always_abrupt(field(node,'alternative'))
        return False

    def functional_target(expected, node):
        if expected is None:
            return None, None
        base = expected.split('<', 1)[0].strip()
        identity = base if '.' in base else api_identities.get(base)
        if identity is None and base == 'Runnable' and not any(row['name'] == base for row in symbols['classes']) and '.'.join(filter(None, (ir.get('package'), base))) not in project_types:
            identity = 'java.lang.Runnable'
        targets = {'java.util.function.BiFunction': ('BiFunction', 2),
                   'java.util.function.BiConsumer': ('BiConsumer', 2),
                   'java.util.function.Supplier': ('Supplier', 0),
                   'java.util.function.Function': ('Function', 1),
                   'java.util.function.Consumer': ('Consumer', 1),
                   'java.util.function.Predicate': ('Predicate', 1),
                   'java.lang.Runnable': ('Runnable', 0)}
        if identity not in targets and identity not in project_types:
            declaration=reference_class(expected)
            contract=declaration.get('runtime_interface_contract') if declaration else None
            methods=[m for m in (contract or {}).get('methods',[]) if m['abstract'] and not m['static']]
            if contract and len(methods)==1:
                required_api_types.add(identity)
                intrinsics.add('neocore.runtime.Functional@7')
                intrinsics.add('neocore.runtime.RuntimeClasses@'+str(max(6,contract.get('helper_abi',6))))
                return contract,len(methods[0]['parameters'])
        if identity not in targets or identity in project_types:
            raise NeedsLowering(node, 'Functional target interface requires resolution: ' + expected)
        required_api_types.add(identity)
        if identity in ('java.util.function.BiFunction','java.util.function.BiConsumer'):
            intrinsics.add('neocore.runtime.Functional@5')
        return targets[identity]

    reference_declarations = {}
    def reference_class(name):
        base = (name or '').split('<', 1)[0].strip()
        row = next((row for row in symbols['classes'] if base in (row['name'], row['java_name'])), None)
        if row is not None and not (name and '<' in name):
            return row
        identity = base if '.' in base else next((item['name'] for item in ir['imports'] if item['name'].rsplit('.', 1)[-1] == base), '.'.join(filter(None, (ir.get('package'), base))))
        if name and '<' in name and identity in ir.get('runtime_generic_interfaces',{}) and identity not in ('net.minecraft.network.codec.StreamCodec','net.minecraft.network.codec.StreamEncoder','net.minecraft.network.codec.StreamDecoder'):
            from java_library_signatures import generic_arguments
            from java_generic_contracts import proves_bound,specialize
            template=ir['runtime_generic_interfaces'][identity]
            arguments=[canonical_method_type(a.strip(),current,overload_unit) for a in generic_arguments(name.replace(' ',''))]
            if len(arguments)!=len(template['type_parameters']) or any(any(c in a for c in '<>[]?') for a in arguments):raise NeedsLowering(current,'Runtime generic interface requires concrete reference type arguments')
            bindings=dict(zip(template['type_parameters'],arguments))
            if any(not proves_bound(bindings[key],bindings.get(bound,bound),overload_unit,project_types) for key,bound in template.get('type_bounds',{}).items()):raise NeedsLowering(current,'Generic bound specialization needs reviewed subtype proof')
            contract=specialize(template,arguments)
            return runtime_interface_declaration(contract['java_name'],contract,'_nc_generic_interface_reference')
        external = next((row for row in external_classes if row['java_name']==identity or row['name']==base),None)
        if external is not None:
            if external.get('runtime_contract',{}).get('helper_abi',1)>1:
                intrinsics.add('neocore.runtime.RuntimeClasses@'+str(external['runtime_contract']['helper_abi']))
            return external
        records = project_types.get(identity, [])
        if not records and identity in ir.get('runtime_superclasses',{}):
            intrinsics.add('neocore.runtime.RuntimeClasses@'+str(ir['runtime_superclasses'][identity].get('helper_abi',1)))
            return runtime_declaration(identity,ir['runtime_superclasses'][identity],'_nc_runtime_declaration')
        if not records and identity in ir.get('runtime_interface_contracts',{}):
            return runtime_interface_declaration(identity,ir['runtime_interface_contracts'][identity],'_nc_interface_declaration')
        metadata = records[0].get('inheritance_metadata') if len(records) == 1 else None
        if metadata is None:return None
        reference_identity=canonical_method_type(name,current,overload_unit) if name and '<' in name and metadata.get('type_parameters') else identity
        if reference_identity not in reference_declarations:
            if reference_identity!=identity:
                from java_library_signatures import generic_arguments
                from java_source_generics import specialize
                metadata=specialize(metadata,[canonical_method_type(a,current,overload_unit) for a in generic_arguments(name)],overload_unit,project_types,NeedsLowering,current)
            # A receiver declared in another file retains its resolved ancestry.
            # Keep lookup-only names separate from emitted superclass bindings.
            context = dict(metadata, runtime_superclasses=ir.get('runtime_superclasses',{}),runtime_interface_contracts=ir.get('runtime_interface_contracts',{}),runtime_generic_interfaces=ir.get('runtime_generic_interfaces',{}))
            try:
                rows, linked, bases = observed('referenced_type_resolution',inheritance_plan,[dict(metadata)], NeedsLowering, project_types, context,observation={'file':ir['origin'],'referenced_type':reference_identity,'referenced_file':records[0].get('file')})
            except NeedsLowering as error:
                # The diagnostic line belongs to the referenced declaration, not
                # necessarily this compilation unit. Preserve the original guard
                # and reason while making the cross-file provenance explicit.
                error.details = dict(error.details, diagnostic_origin={
                    'compilation_unit': ir['origin'],
                    'referenced_type': reference_identity,
                    'referenced_file': records[0].get('file'),
                    'declaration_line': error.line,
                    'phase': 'referenced_type_inheritance'})
                raise
            graph = rows + bases
            old_parents = {id(row): linked.get(row['name']) for row in graph}
            for row in graph:
                row['name'] = '_nc_reference_' + str(len(reference_declarations))
                row['external'] = True
                reference_declarations[row['java_name']] = row
                overload_unit['_external_classes'].append(row)
            for row in graph:
                parents[row['name']] = old_parents[id(row)]
        return reference_declarations[reference_identity]
    overload_unit['_resolve_type']=reference_class

    def method_reference(node, expected):
        children = [child for child in named(node) if child['kind'] != '::']
        if len(children) != 2:
            raise NeedsLowering(node, 'Generic/qualified method reference requires lowering')
        receiver, member_node = children
        name, receiver_name = text(member_node), text(receiver)
        kind, target_arity = functional_target(expected, node)
        is_class = receiver_name not in locals_map and find_field(receiver_name) is None and reference_class(receiver_name) is not None
        owner = parents.get(current['name']) if receiver['kind'] == 'super' else (current if receiver['kind'] == 'this' else reference_class(receiver_name if is_class else expression_type(receiver)))
        if owner is None:
            raise NeedsLowering(node, 'Method-reference receiver declaration is unresolved')
        intrinsics.add('neocore.runtime.Functional@9')
        if name == 'new':
            if owner['kind']=='interface_declaration' or 'abstract' in owner.get('modifiers',[]):
                raise NeedsLowering(node,'Abstract runtime superclass constructor reference is invalid')
            if not is_class:
                raise NeedsLowering(node, 'Constructor reference requires a resolved class type')
            constructors = constructor_entries(owner)
            arities = {len(method['parameters']) for method in constructors}
            arity = target_arity if target_arity is not None else (next(iter(arities)) if len(arities) == 1 else None)
            if arity not in arities:
                raise NeedsLowering(node, 'Constructor reference target arity is ambiguous/incompatible')
            inputs = []
            if isinstance(kind,dict):inputs=next(m['parameters'] for m in kind['methods'] if m['abstract'] and not m['static'])
            if expected and '<' in expected and kind in ('Function','BiFunction'):
                from java_library_signatures import generic_arguments
                inputs = [canonical_method_type(item,current,overload_unit) for item in generic_arguments(expected,allow_wildcards=True)[:target_arity]]
            if len(constructors) == 1 and len(constructors[0]['parameters']) == arity and not isinstance(kind,dict):
                selected = constructors[0]
            else:
                selected = select_overload([(owner, method) for method in constructors], inputs, parents, overload_unit, node, NeedsLowering)[1]
            if isinstance(kind,dict):
                result=next(m['return_type'] for m in kind['methods'] if m['abstract'] and not m['static'])
                if result!='void' and not overload_subtype(owner['java_name'],result,parents,overload_unit):raise NeedsLowering(node,'Constructor result does not satisfy reviewed functional interface')
            intrinsics.add('neocore.runtime.Functional@4')
            return '_nc_Functional.constructor(' + repr(kind) + ', ' + project_type_reference(receiver_name, receiver) + ', ' + str(arity) + ', ' + repr(runtime_signature(selected, owner, overload_unit)) + ', ' + repr(tuple(inputs)) + ')'
        entries = method_family(owner, name, parents, overload_unit)
        reference_inputs = []
        if isinstance(kind,dict):reference_inputs=next(m['parameters'] for m in kind['methods'] if m['abstract'] and not m['static'])
        if expected and '<' in expected and kind in ('Function','Consumer','Predicate','BiFunction','BiConsumer'):
            from java_library_signatures import generic_arguments
            reference_inputs = [canonical_method_type(item,current,overload_unit) for item in generic_arguments(expected,allow_wildcards=True)[:target_arity]]
        if len(entries) > 1 or entries and (isinstance(kind,dict) or reference_inputs):
            selection_inputs = reference_inputs[1:] if is_class and not entries[0][1]['static'] else reference_inputs
            declaring, method = select_overload(entries, selection_inputs, parents, overload_unit, node, NeedsLowering)
        else:
            declaring, method = entries[0] if entries else (None,None)
        if method is None:
            raise NeedsLowering(node, 'Unresolved referenced method: ' + name)
        if any(p.get('varargs') for p in method['parameters']):
            raise NeedsLowering(node,'Variable-arity method reference adaptation requires lowering')
        check_runtime_access(declaring, method, receiver, node)
        def reference_result_adapter(code):
            if not isinstance(kind,dict) and kind not in ('Function', 'Supplier', 'BiFunction'):
                return code
            from java_method_overloads import canonical_return
            actual=canonical_return(method['return_type'],declaring,overload_unit)
            target=next(m['return_type'] for m in kind['methods'] if m['abstract'] and not m['static']) if isinstance(kind,dict) else 'java.lang.Object'
            if not isinstance(kind,dict) and expected and '<' in expected:
                from java_library_signatures import generic_arguments
                target=canonical_method_type(generic_arguments(expected)[-1],current,overload_unit)
            if target=='void':return code
            value='_nc_ref_function(*_nc_ref_args)'
            if actual in BOXES and target in BOXES and primitive_widens(actual,target):
                if actual!=target:value='_nc_Functional.castPrimitive('+repr(target)+', '+repr(actual)+', '+value+')'
            elif actual in BOXES and (target==BOXES[actual] or target=='java.lang.Object' or target=='java.lang.Number' and actual not in ('boolean','char')):
                value='_nc_Functional.box('+repr(actual)+', '+value+')'
            elif actual in UNBOXES and target in BOXES and primitive_widens(UNBOXES[actual],target):
                primitive=UNBOXES[actual];value='_nc_Functional.unbox('+repr(primitive)+', '+value+')'
                if target!=primitive:value='_nc_Functional.castPrimitive('+repr(target)+', '+repr(primitive)+', '+value+')'
            elif actual not in BOXES and target not in BOXES and overload_subtype(actual,target,parents,overload_unit):return code
            else:raise NeedsLowering(node,'Referenced method result conversion is not Java invocation compatible')
            return '(lambda _nc_ref_function: _nc_Functional.make(' + repr(kind) + ', lambda *_nc_ref_args: '+value+', ' + str(arity) + ', None))(' + code + ')'

        if receiver['kind']=='super' and method.get('abstract'):
            raise NeedsLowering(node,'Abstract superclass method reference requires a concrete declaration')
        unbound = is_class and not method['static']
        arity = len(method['parameters']) + (1 if unbound else 0)
        if target_arity is not None and arity != target_arity:
            raise NeedsLowering(node, 'Method reference has incompatible functional arity')
        if not is_class and method['static']:
            raise NeedsLowering(node, 'Static method reference through an expression requires validation')
        event_code = 'None'
        if arity == 1 and not unbound:
            parameter_type = method['parameters'][0]['declared_type']
            simple = parameter_type.split('<', 1)[0]
            if simple.split('.',1)[0] in api_identities:
                event_code = project_type_reference(simple,method['parameters'][0])
        if receiver['kind'] == 'super':
            if static_context:
                raise NeedsLowering(node, 'super method reference in static context')
            if method['parameters']:
                intrinsics.add('neocore.runtime.Functional@4')
                converted = '_nc_Functional._methodArgs(_nc_ref_args, ' + repr(runtime_signature(method, declaring, overload_unit)) + ', ' + repr(tuple(reference_inputs)) + ')'
                callback = 'lambda *_nc_ref_args: ' + get_attr(owner['name'], name) + '(self, *' + converted + ', _nc_java_signature=' + repr(runtime_signature(method, declaring, overload_unit)) + ')'
            else:
                callback = 'lambda *_nc_ref_args: ' + get_attr(owner['name'], name) + '(self, *_nc_ref_args, _nc_java_signature=' + repr(runtime_signature(method, declaring, overload_unit)) + ')'
            return reference_result_adapter('_nc_Functional.make(' + repr(kind) + ', ' + callback + ', ' + str(arity) + ', ' + event_code + ')')
        if declaring.get('runtime_contract'):
            signature = repr(runtime_signature(method, declaring, overload_unit))
            if method['parameters']:
                intrinsics.add('neocore.runtime.Functional@4')
            converted = '_nc_Functional._methodArgs(_nc_ref_args, ' + signature + ', ' + repr(tuple(reference_inputs)) + ')'
            if method['static']:
                intrinsics.add('neocore.runtime.RuntimeClasses@2')
                invocation = '_nc_RuntimeClasses.invokeStatic(' + repr(declaring['java_name']) + ', ' + repr(name) + ', ' + signature + ', ' + converted + ')'
                return reference_result_adapter('_nc_Functional.make(' + repr(kind) + ', lambda *_nc_ref_args: ' + invocation + ', ' + str(arity) + ', None)')
            intrinsics.add('neocore.runtime.RuntimeClasses@1')
            invocation = '_nc_RuntimeClasses.invoke(' + repr(declaring['java_name']) + ', _nc_ref_receiver, ' + repr(name) + ', ' + signature + ', ' + converted + ')'
            if unbound:
                return reference_result_adapter('_nc_Functional.make(' + repr(kind) + ', lambda _nc_ref_receiver, *_nc_ref_args: ' + invocation + ', ' + str(arity) + ', None)')
            return reference_result_adapter('(lambda _nc_ref_receiver: _nc_Functional.make(' + repr(kind) + ', lambda *_nc_ref_args: ' + invocation + ', ' + str(arity) + ', None))(_nc_Functional.requireNonNull(' + expr(receiver) + '))')
        receiver_code = project_type_reference(receiver_name, receiver) if is_class else expr(receiver)
        if unbound:
            return reference_result_adapter('_nc_Functional.unbound(' + repr(kind) + ', ' + receiver_code + ', ' + repr(name) + ', ' + str(arity) + ', ' + repr(runtime_signature(method,declaring,overload_unit)) + ', ' + repr(tuple(reference_inputs[1:])) + ')')
        return reference_result_adapter('_nc_Functional.bound(' + repr(kind) + ', ' + receiver_code + ', ' + repr(name) + ', ' + str(arity) + ', ' + event_code + ', ' + repr(runtime_signature(method,declaring,overload_unit)) + ', ' + repr(tuple(reference_inputs)) + ')')


    def lambda_expression(node, expected):
        nonlocal locals_map, local_types, current_return_type,current_sam_return
        kind, target_arity = functional_target(expected, node)
        parameter_node, body = field(node, 'parameters'), field(node, 'body')
        parameters = [parameter_node] if parameter_node['kind'] == 'identifier' else named(parameter_node)
        args = []
        for parameter in parameters:
            if parameter['kind'] == 'identifier':
                args.append((text(parameter), None))
            elif parameter['kind'] == 'formal_parameter':
                args.append((text(field(parameter, 'name')), text(field(parameter, 'type'))))
            else:
                raise NeedsLowering(parameter, 'Lambda parameter shape requires lowering')
        if target_arity is not None and len(args) != target_arity:
            raise NeedsLowering(node, 'Lambda argument count differs from functional target')
        type_args = []
        if expected and '<' in expected:
            inner = expected[expected.index('<') + 1:expected.rfind('>')]
            start, depth = 0, 0
            for number, char in enumerate(inner):
                if char == '<': depth += 1
                elif char == '>': depth -= 1
                elif char == ',' and depth == 0:
                    type_args.append(inner[start:number].strip()); start = number + 1
            type_args.append(inner[start:].strip())
        typed_args = []
        for index, (name, declared_type) in enumerate(args):
            if name in locals_map:
                raise NeedsLowering(node, 'Lambda argument shadows an existing local/parameter')
            inferred = next(m['parameters'] for m in kind['methods'] if m['abstract'] and not m['static'])[index] if isinstance(kind,dict) else type_args[index] if kind in ('Function', 'Consumer', 'Predicate', 'BiFunction', 'BiConsumer') and index < len(type_args) else None
            if declared_type and inferred and canonical_method_type(declared_type,current,overload_unit)!=canonical_method_type(inferred,current,overload_unit):raise NeedsLowering(node,'Explicit lambda parameter differs from reviewed functional target')
            declared_type = declared_type or inferred
            if declared_type is None or '?' in declared_type:
                raise NeedsLowering(node, 'Lambda argument type requires contextual resolution')
            typed_args.append((name, declared_type))
        used = {text(child) for child in walk(body) if child['kind'] == 'identifier' and child.get('field') not in ('name', 'field')}
        captures = {name: alias for name, alias in locals_map.items() if name in used}
        if set(captures)&uninitialized:raise NeedsLowering(node,'Captured local is not definitely assigned')
        if any(alias.endswith('[0]') for alias in captures.values()):raise NeedsLowering(node,'Delayed local lambda capture requires effective-final flow lowering')
        for child in walk(current_method_body or body):
            target = field(child, 'left') if child['kind'] == 'assignment_expression' else (next((c for c in named(child) if c['kind'] not in ('++', '--')), None) if child['kind'] == 'update_expression' else None)
            if target is not None and target['kind'] == 'identifier' and text(target) in captures:
                raise NeedsLowering(target, 'Captured Java local/parameter is not effectively final')
        number = lambda_counter[0];lambda_counter[0] += 1
        helper_name = '_nc_lambda_' + str(number)
        while helper_name in types:
            helper_name += '_'
        saved_names, saved_types, saved_return = locals_map, local_types, current_return_type
        saved_sam_return=current_sam_return
        saved_unassigned=set(uninitialized)
        parameter_aliases = ['_nc_lambda_arg_' + str(number) + '_' + str(index) for index in range(len(typed_args))]
        locals_map, local_types = dict(saved_names), dict(saved_types)
        for (name, declared_type), alias in zip(typed_args, parameter_aliases):
            locals_map[name], local_types[name] = alias, declared_type
        capture_aliases = list(captures.values())
        helper_parameters = (['self'] if not static_context else []) + capture_aliases + parameter_aliases
        helper_lines = ['def ' + helper_name + '(' + ', '.join(helper_parameters) + '):']
        event_code = 'None'
        try:
            current_return_type = (next(m['return_type'] for m in kind['methods'] if m['abstract'] and not m['static']) if isinstance(kind,dict) else type_args[-1] if kind in ('Function', 'Supplier', 'BiFunction') and type_args else 'boolean' if kind == 'Predicate' else None)
            current_sam_return=current_return_type if isinstance(kind,dict) or kind in ('Supplier','Function','BiFunction') else None
            for (name, declared_type), alias in zip(typed_args, parameter_aliases):
                if is_boxed_integer(declared_type):
                    intrinsics.add('neocore.runtime.Functional@2')
                    helper_lines.append('    ' + alias + ' = _nc_Functional.castInteger(' + alias + ')')
                elif declared_type in api_identities and len(typed_args) == 1:
                    event_code = types[declared_type]
                    helper_lines.append('    ' + alias + ' = _nc_Functional.castReference(' + alias + ', ' + event_code + ')')
                elif reference_class(declared_type) is not None:
                    helper_lines.append('    ' + alias + ' = _nc_Functional.castReference(' + alias + ', ' + project_type_reference(declared_type, node) + ')')
            if body['kind'] == 'block':
                helper_lines.extend(statement(body, 1))
            elif (kind in ('Consumer','Runnable','BiConsumer') or current_return_type=='void') and body['kind'] in ('assignment_expression','update_expression'):
                helper_lines.extend(statement({'kind':'expression_statement','children':[body],'line':body.get('line',1)}, 1))
            else:
                if current_sam_return is not None:
                    if current_sam_return=='void':
                        if body['kind'] not in ('method_invocation','object_creation_expression'):raise NeedsLowering(body,'Void functional expression must be a statement expression')
                    else:validate_sam_return(body,current_sam_return)
                helper_lines.append('    return ' + expr(body, current_return_type))
        finally:
            locals_map, local_types, current_return_type = saved_names, saved_types, saved_return
            set_uninitialized(saved_unassigned)
            current_sam_return=saved_sam_return
        lambda_helpers.extend(helper_lines + [''])
        defaults = [alias + '=' + alias for alias in capture_aliases]
        values = list(capture_aliases) + parameter_aliases
        if not static_context:
            defaults.append('_nc_self_capture=self');values.insert(0, '_nc_self_capture')
        callback = 'lambda ' + ', '.join(parameter_aliases + defaults) + ': ' + helper_name + '(' + ', '.join(values) + ')'
        intrinsics.add('neocore.runtime.Functional@2')
        return '_nc_Functional.make(' + repr(kind) + ', ' + callback + ', ' + str(len(args)) + ', ' + event_code + ')'

    def array_descriptor(type_name, node):
        intrinsics.add('neocore.runtime.JavaArrays@3')
        compact = (type_name or '').replace(' ', '')
        rank = compact.count('[]')
        base = compact[:-2*rank] if rank else compact
        if not base or '<' in base or '@' in base:
            raise NeedsLowering(node, 'Array component identity requires lowering')
        identity = canonical_method_type(base, current, overload_unit)
        if base in ('boolean','byte','short','char','int','long','float','double'):
            reference = 'None'
        elif identity == 'java.lang.Object':
            reference = 'object'
        elif identity == 'java.lang.String':
            reference = '_nc_String'
        else:
            reference = project_type_reference(base, node)
        return identity, rank, reference

    def array_initializer(node, expected):
        identity, rank, reference = array_descriptor(expected,node)
        if rank < 1:
            raise NeedsLowering(node, 'Array initializer requires a declared array target')
        element_type = expected.replace(' ','')[:-2]
        values = [array_initializer(child, element_type) if child['kind']=='array_initializer' else expr(child, element_type) for child in named(node)]
        intrinsics.add('neocore.runtime.JavaArrays@1')
        return '_nc_JavaArrays.initialized(' + repr(identity) + ', ' + str(rank) + ', [' + ', '.join(values) + '], ' + reference + ')'

    def expr(node, expected=None):
        if node is None:
            raise NeedsLowering({'line': 1}, 'Missing expression')
        kind, raw = node['kind'], text(node)
        # Convert the complete expression, including checked casts, exactly once.
        if expected is not None and kind not in ('lambda_expression','method_reference'):
            target=canonical_method_type(expected,current,overload_unit)
            if target in BOXES or target in UNBOXES or target in ('java.lang.Object','java.lang.Number'):
                actual=scalar_type(node)
                if actual in UNBOXES and target in BOXES:
                    primitive=UNBOXES[actual]
                    if not primitive_widens(primitive,target):
                        raise NeedsLowering(node,'Implicit unboxing/narrowing conversion is not legal: '+actual+' -> '+target)
                    intrinsics.add('neocore.runtime.Functional@9')
                    value='_nc_Functional.unbox('+repr(primitive)+', '+expr(node)+')'
                    return value if primitive==target else '_nc_Functional.castPrimitive('+repr(target)+', '+repr(primitive)+', '+value+')'
                if actual in BOXES:
                    narrow=False
                    narrow_target=UNBOXES.get(target,target)
                    if actual=='int' and narrow_target in ('byte','short','char'):
                        constant=node;sign=1
                        if kind=='unary_expression' and text(field(node,'operator')) in ('+','-'):
                            constant=field(node,'operand');sign=-1 if text(field(node,'operator'))=='-' else 1
                        if constant['kind'] in INTEGER_KINDS:
                            number,width=literal_value(constant,text(constant),NeedsLowering,allow_decimal_min=sign<0)
                            number*=sign
                            low,high={'byte':(-128,127),'short':(-32768,32767),'char':(0,65535)}[narrow_target]
                            narrow=width==32 and low<=number<=high
                    if target in BOXES:
                        if actual!=target:
                            if not primitive_widens(actual,target) and not narrow:
                                raise NeedsLowering(node,'Implicit primitive narrowing requires a valid constant or explicit cast')
                            intrinsics.add('neocore.runtime.Functional@9')
                            return '_nc_Functional.castPrimitive('+repr(target)+', '+repr(actual)+', '+expr(node)+')'
                        if target=='float':
                            intrinsics.add('neocore.runtime.Functional@9')
                            return "_nc_Functional.castPrimitive('float', 'float', "+expr(node)+')'
                    else:
                        primitive=UNBOXES.get(target,actual)
                        valid=(target=='java.lang.Object' or target=='java.lang.Number' and actual not in ('boolean','char') or UNBOXES.get(target)==actual or narrow)
                        if not valid:
                            raise NeedsLowering(node,'Boxing cannot change the declared wrapper type')
                        intrinsics.add('neocore.runtime.Functional@9')
                        value=expr(node)
                        if narrow:value='_nc_Functional.castPrimitive('+repr(primitive)+', '+repr(actual)+', '+value+')'
                        return '_nc_Functional.box('+repr(primitive)+', '+value+')'
        if kind=='assignment_expression':
            left,right=field(node,'left'),field(node,'right');name=text(left)
            if text(field(node,'operator'))!='=' or left['kind']!='identifier' or name not in locals_map or not locals_map[name].endswith('[0]'):
                raise NeedsLowering(node,'Assignment expression requires a tracked delayed local storage cell')
            code=expr(right,local_types[name]);uninitialized.discard(name)
            return '(lambda _nc_value: ('+locals_map[name][:-3]+'.__setitem__(0, _nc_value), _nc_value)[1])('+code+')'
        if kind=='instanceof_expression':
            operand=field(node,'left');right=field(node,'right')
            if operand is None or right is None or right['kind'] not in ('type_identifier','scoped_type_identifier') or field(node,'name') is not None:
                raise NeedsLowering(node,'Pattern/generic/array instanceof requires reified binding lowering')
            target=canonical_method_type(text(right),current,overload_unit)
            if target not in project_types and target not in ir.get('runtime_superclasses',{}) and target not in tuple(UNBOXES)+('java.lang.Object','java.lang.Number'):
                raise NeedsLowering(node,'instanceof requires a reviewed source/runtime superclass identity')
            if scalar_type(operand) in BOXES or original_type(operand)=='void':
                raise NeedsLowering(node,'instanceof operand must have reference type')
            reference='object' if target=='java.lang.Object' else project_type_reference(text(right),node)
            intrinsics.add('neocore.runtime.Functional@9')
            return '_nc_Functional.isInstance('+expr(operand)+', '+reference+')'
        if kind=='cast_expression':
            target=original_type(node);operand=field(node,'value')
            if target in BOXES:
                actual=scalar_type(operand);primitive=UNBOXES.get(actual,actual)
                intrinsics.add('neocore.runtime.Functional@9')
                value=expr(operand)
                if actual in UNBOXES:
                    value='_nc_Functional.unbox('+repr(primitive)+', '+value+')'
                elif canonical_method_type(original_type(operand),current,overload_unit)=='java.lang.Object':
                    primitive=target
                    reference=project_type_reference(BOXES[target],node)
                    value='_nc_Functional.unbox('+repr(target)+', _nc_Functional.castReference('+value+', '+reference+'))'
                if primitive not in BOXES:raise NeedsLowering(node,'Primitive cast requires a reviewed scalar identity')
                if (target=='boolean')!=(primitive=='boolean'):raise NeedsLowering(node,'Boolean has no numeric cast')
                return '_nc_Functional.castPrimitive('+repr(target)+', '+repr(primitive)+', '+value+')'
            if operand is None or sum(child.get('field')=='type' for child in node.get('children',[]))!=1:
                raise NeedsLowering(node,'Intersection cast requires lowering')
            if target.endswith('[]'):
                if operand['kind']=='null_literal':
                    array_descriptor(text(field(node,'type')),node)
                    return 'None'
                identity,rank,reference=array_descriptor(text(field(node,'type')),node)
                intrinsics.add('neocore.runtime.JavaArrays@2')
                return '_nc_JavaArrays.cast('+expr(operand)+', '+repr(identity)+', '+str(rank)+', '+reference+')'
            base=text(field(node,'type')).split('<',1)[0]
            reference='object' if target=='java.lang.Object' else '_nc_String' if target=='java.lang.String' else project_type_reference(base,node)
            if operand['kind']=='null_literal':return 'None'
            intrinsics.add('neocore.runtime.Functional@9' if target in UNBOXES or target=='java.lang.Number' else 'neocore.runtime.Functional@2')
            return '_nc_Functional.castReference('+expr(operand,text(field(node,'type')))+', '+reference+')'
        if kind=='character_literal':
            from java_scalar_literals import character
            return character(raw,node,NeedsLowering)
        if kind=='decimal_floating_point_literal' and raw[-1:] not in ('f','F'):
            import math
            token=raw[:-1] if raw[-1:] in ('d','D') else raw
            try:value=float(token.replace('_',''))
            except ValueError:raise NeedsLowering(node,'Invalid double literal')
            if not math.isfinite(value):raise NeedsLowering(node,'Overflowing double literal')
            # A zero result with a nonzero decimal significand is not legal Java.
            significand=token.lower().split('e',1)[0].replace('_','').replace('.','')
            if value==0 and any(c not in '0+-' for c in significand):raise NeedsLowering(node,'Underflowing double literal')
            return repr(value)
        if kind=='decimal_floating_point_literal' and raw[-1:] in ('f','F'):
            import math,struct
            try:value=struct.unpack('f',struct.pack('f',float(raw[:-1].replace('_',''))))[0]
            except (ValueError,OverflowError):raise NeedsLowering(node,'Invalid/overflowing float literal')
            if not math.isfinite(value) or value==0 and float(raw[:-1].replace('_',''))!=0:raise NeedsLowering(node,'Nonfinite/underflowing float literal')
            return repr(value)
        if kind=='unary_expression' and text(field(node,'operator')) in ('-','+') and expression_type(field(node,'operand'))=='float':
            return '('+text(field(node,'operator'))+expr(field(node,'operand'))+')'
        if kind == 'array_initializer':
            return array_initializer(node, expected)
        if kind == 'array_creation_expression':
            component = text(field(node,'type'))
            dimensions=[]
            for child in node.get('children',[]):
                if child['kind']=='dimensions_expr':
                    dimension=next(item for item in named(child) if item['kind'] not in ('[',']'))
                    if expression_type(dimension)!='int':
                        raise NeedsLowering(dimension,'Array dimension must have resolved int type')
                    dimensions.append(expr(dimension))
                elif child['kind']=='dimensions':
                    dimensions.extend(['None']*text(child).count('['))
            type_name=component+'[]'*len(dimensions)
            initializer=field(node,'value')
            if initializer is not None:
                return array_initializer(initializer,type_name)
            identity,rank,reference=array_descriptor(type_name,node)
            intrinsics.add('neocore.runtime.JavaArrays@1')
            return '_nc_JavaArrays.create(' + repr(identity) + ', (' + ', '.join(dimensions) + ',), ' + reference + ')'
        if kind == 'array_access':
            if expression_type(field(node,'index'))!='int':
                raise NeedsLowering(node,'Array index requires resolved int type')
            intrinsics.add('neocore.runtime.JavaArrays@1')
            return '_nc_JavaArrays.get(' + expr(field(node,'array')) + ', ' + expr(field(node,'index')) + ')'
        if kind == 'class_literal':
            target=next((child for child in named(node) if child['kind'] not in ('.','class')),None)
            if target is None:raise NeedsLowering(node,'Class literal target is missing')
            api_type_identity(target)
            return project_type_reference(text(target), target)
        if kind == 'field_access' and text(field(node,'field'))=='length' and (expression_type(field(node,'object')) or '').endswith('[]'):
            intrinsics.add('neocore.runtime.JavaArrays@1')
            return '_nc_JavaArrays.length(' + expr(field(node,'object')) + ')'
        if kind in ('method_reference','lambda_expression') and expected:
            factory_type=canonical_method_type(expected.split('<',1)[0],current,overload_unit)
            if factory_type=='net.minecraft.world.entity.EntityType.EntityFactory':
                from java_library_signatures import generic_arguments
                type_args=generic_arguments(expected)
                if len(type_args)!=1:raise NeedsLowering(node,'EntityFactory requires one resolved entity type')
                required_api_types.add(factory_type)
                intrinsics.add('neocore.runtime.Functional@6')
                contextual='java.util.function.BiFunction<net.minecraft.world.entity.EntityType,net.minecraft.world.level.Level,'+type_args[0]+'>'
                callback=method_reference(node,contextual) if kind=='method_reference' else lambda_expression(node,contextual)
                return '_nc_Functional.entityFactory('+callback+')'
        if kind == 'method_reference':
            return method_reference(node, expected)
        if kind == 'lambda_expression':
            return lambda_expression(node, expected)
        if kind == 'identifier':
            if raw in locals_map:
                if raw in uninitialized:
                    raise NeedsLowering(node, 'Local variable used before its initializer')
                return locals_map[raw]
            member = find_field(raw)
            if member:
                if static_context and not member['static']:
                    raise NeedsLowering(node, 'Instance field in static context')
                return get_attr(static_owner(raw, 'fields') if member['static'] else 'self', member.get('storage_name',raw))
            if static_constant(raw): return static_constant(raw)['code']
            if raw in types:
                return types[raw]
            identity = '.'.join(filter(None, (ir.get('package'), raw)))
            if identity in project_types:
                return project_type_reference(raw, node)
            if 'java.lang.'+raw in ir.get('known_java_lang_api_types',[]):
                return project_type_reference(raw,node)
            if raw == 'System':
                lines.insert(3,'from java.lang import System as _nc_System') if 'from java.lang import System as _nc_System' not in lines else None
                required_api_types.add('java.lang.System')
                types[raw]='_nc_System'
                return '_nc_System'
            raise NeedsLowering(node, 'Unresolved expression identifier: ' + raw)
        if kind == 'this':
            if static_context:
                raise NeedsLowering(node, 'this in static context')
            return 'self'
        if kind in ('true', 'false', 'null_literal'):
            return {'true': 'True', 'false': 'False', 'null_literal': 'None'}[kind]
        if kind in INTEGER_KINDS:
            number, _ = literal_value(node, raw, NeedsLowering)
            return str(number)
        if kind == 'string_literal':
            if '\\u' in raw:
                raise NeedsLowering(node, 'Java Unicode pre-lexing requires source mapping', {'category':'unicode_prelexing'})
            try:
                value = json.loads(raw)
            except ValueError:
                raise NeedsLowering(node, 'Java string escape requires literal lowering')
            return '_nc_String(u' + json.dumps(value, ensure_ascii=False) + ')'
        if kind == 'parenthesized_expression':
            return '(' + expr(named(node)[0]) + ')'
        if kind == 'field_access' and field(node, 'object')['kind'] in ('this', 'super'):
            owner = current if field(node, 'object')['kind'] == 'this' else parents.get(current['name'])
            name = text(field(node, 'field'))
            declaring, member = find_member(name, 'fields', owner) if owner is not None else (None, None)
            if member is None or static_context:
                raise NeedsLowering(node, 'Unresolved/invalid instance field access: ' + name)
            return get_attr(declaring['name'] if member['static'] else 'self', member.get('storage_name',name))
        if kind == 'field_access':
            record=library_field(node)
            if record:
                if record.get('receiver_kind')=='game_api':
                    receiver=field(node,'object');name=text(field(node,'field'))
                    if record.get('static_owner'):
                        target=get_attr(project_type_reference(record['static_owner'],node),name)
                        return target if type_qualifier(receiver) else '(lambda _nc_field_receiver: '+target+')('+expr(receiver)+')'
                    if type_qualifier(receiver):raise NeedsLowering(node,'Instance API field requires an expression receiver')
                    intrinsics.add('neocore.runtime.Functional@3')
                    target=get_attr('_nc_Functional.requireNonNull('+expr(receiver)+')',record.get('call_name',name))
                    return target+'()' if record.get('call_name') else target
                intrinsics.add('neocore.runtime.Profilers@1')
                owner=record['static_owner'];receiver=field(node,'object')
                target='_nc_Profilers.field('+repr(owner)+', '+project_type_reference(owner,node)+', '+repr(text(field(node,'field')))+')'
                return target if type_qualifier(receiver) else '(lambda _nc_field_receiver: '+target+')('+expr(receiver)+')'
            enum_type=api_type_identity(field(node,'object'))
            if enum_type in ir.get('runtime_enum_types',{}):
                if text(field(node,'field')) not in ir['runtime_enum_types'][enum_type]['constants']:
                    raise NeedsLowering(node,'Unreviewed enum field: '+text(field(node,'field')))
            root = node
            while root['kind'] == 'field_access':
                root = field(root, 'object')
            shadowed = text(root) in locals_map or text(root) in types or any(
                f['name'] == text(root) for f in current['fields'])
            if raw in project_types and not shadowed:
                return project_type_reference(raw, node)
            receiver=field(node,'object');name=text(field(node,'field'))
            owner=reference_class(text(receiver)) if type_qualifier(receiver) else reference_class(expression_type(receiver))
            if owner is not None:
                declaring,member=find_member(name,'fields',owner)
                if member and member.get('storage_name'):
                    if type_qualifier(receiver):raise NeedsLowering(node,'Record component requires an instance receiver')
                    if current['java_name']!=declaring['java_name'] and (current.get('anonymous_codec') or {}).get('owner')!=declaring['java_name']:raise NeedsLowering(node,'Renamed field is private; use its accessor')
                    name=member['storage_name']
                    intrinsics.add('neocore.runtime.Functional@3')
                    return get_attr('_nc_Functional.requireNonNull('+expr(receiver)+')',name)
            return get_attr(expr(receiver),name)
        if kind == 'method_invocation':
            name, receiver = text(field(node, 'name')), field(node, 'object')
            arguments = named(field(node, 'arguments'))
            if receiver is not None and name=='register' and len(arguments)==1 and arguments[0]['kind']=='class_literal':
                receiver_type=canonical_method_type(original_type(receiver) or expression_type(receiver),current,overload_unit)
                global_bus=text(receiver).endswith('.EVENT_BUS') and api_identities.get(text(receiver).split('.',1)[0])=='net.neoforged.neoforge.common.NeoForge'
                if receiver_type=='net.neoforged.bus.api.IEventBus' or global_bus:
                    literal=arguments[0]
                    type_node=next((child for child in named(literal) if child['kind'] not in ('.','class')),None)
                    if type_node is None:raise NeedsLowering(literal,'Event class registration reference is missing')
                    intrinsics.add('neocore.runtime.ModEntrypoints@2')
                    return get_attr(expr(receiver),name)+'('+project_type_reference(text(type_node),type_node)+')'
            if receiver is not None and name == 'intValue' and not arguments and is_boxed_integer(original_type(receiver) or expression_type(receiver)):
                intrinsics.add('neocore.runtime.Functional@3')
                return get_attr('_nc_Functional.requireNonNull(' + expr(receiver) + ')', name) + '()'
            qualified_super=any(c['kind']=='super' and c.get('field')!='object' for c in node.get('children',[]))
            declaration = None
            if qualified_super:
                declaration=reference_class(text(receiver))
                direct=current.get('source_interfaces',[])
                if static_context or declaration is None or declaration['kind']!='interface_declaration' or not any(r['java_name']==declaration['java_name'] for r in direct):raise NeedsLowering(node,'Qualified super requires a direct superinterface in instance context')
                others=[r for r in direct if r['java_name']!=declaration['java_name']]
                parent=parents.get(current['name'])
                if parent is not None:others.append(parent)
                if any(overload_subtype(r['java_name'],declaration['java_name'],parents,overload_unit) for r in others):raise NeedsLowering(node,'Qualified superinterface is redundant through another direct parent')
            elif receiver is None or receiver['kind'] == 'this':
                declaration = current
            elif receiver['kind'] == 'super':
                declaration = parents.get(current['name'])
                if static_context or declaration is None:
                    raise NeedsLowering(node, 'super call requires resolved instance parent')
            else:
                declaration = reference_class(text(receiver)) if type_qualifier(receiver) else reference_class(expression_type(receiver))
            native_static=library_method(node) if declaration is not None and declaration.get('runtime_interface_contract') else None
            if native_static and native_static.get('static_owner'):
                if not type_qualifier(receiver):raise NeedsLowering(node,'Static interface factory requires its declaring interface qualifier')
                declaring,method=None,None
            else:
                native_static=None
                declaring, method = selected_method(declaration, name, arguments, node) if declaration is not None else (None, None)
            if qualified_super and (method is None or method['static'] or not (method.get('body') or method.get('has_body')) or declaring.get('runtime_interface_contract')):raise NeedsLowering(node,'Qualified super requires a source default method body; native default dispatch requires a separate adapter')
            if method is not None:check_runtime_access(declaring, method, receiver, node)
            if receiver is not None and receiver['kind']=='super' and method is not None and method.get('abstract'):
                raise NeedsLowering(node,'Abstract superclass method cannot be invoked with super')
            if receiver is None:
                if method is None or (static_context and not method['static']):
                    raise NeedsLowering(node, 'Unresolved unqualified method: ' + name)
                receiver_code = declaring['name'] if method['static'] else 'self'
            elif receiver['kind'] == 'super':
                receiver_code = parents[current['name']]['name']
            else:
                receiver_code = expr(receiver)
            library=(native_static or library_method(node)) if method is None else None
            if method is None and library is None and receiver is not None:
                identity=canonical_method_type(api_type_identity(receiver) or original_type(receiver) or expression_type(receiver),current,overload_unit)
                base=(identity or '').split('<',1)[0]
                if base in ir.get('known_api_types',[]):
                    raise NeedsLowering(node,'No reviewed API call contract: '+base+'#'+name,
                        {'category':'REVIEWED_API_CONTRACT_MISSING','owner':base,'method':name,
                         'argument_types':[invocation_type(a) for a in arguments],
                         'call_form':'type_qualifier' if type_qualifier(receiver) else 'expression_receiver'})
            formal = method['parameters'] if method is not None and len(method['parameters']) == len(arguments) else []
            if method is not None and method.get('_nc_varargs_expanded'):
                parameters=method['parameters'];fixed=len(parameters)-1;array_type=parameters[-1]['declared_type']
                args=[converted_argument(arg,parameters[index]['declared_type'],declaring) for index,arg in enumerate(arguments[:fixed])]
                identity,rank,reference=array_descriptor(array_type,node)
                values=[converted_argument(arg,array_type[:-2],declaring) for arg in arguments[fixed:]]
                intrinsics.add('neocore.runtime.JavaArrays@1')
                args.append('_nc_JavaArrays.initialized('+repr(identity)+', '+str(rank)+', ['+', '.join(values)+'], '+reference+')')
            else:args = [converted_argument(arg, formal[index]['declared_type'], declaring) if formal else expr(arg,library['parameters'][index]) if library else expr(arg) for index, arg in enumerate(arguments)]
            if qualified_super:
                return get_attr(declaring['name'],name)+'(self'+(', '+', '.join(args) if args else '')+', _nc_java_signature='+repr(runtime_signature(method,declaring,overload_unit))+')'
            if library:
                if library.get('array_abi'):intrinsics.add('neocore.runtime.JavaArrays@'+str(library['array_abi']))
                if library.get('mixin_abi'):intrinsics.add('neocore.runtime.MixinCallbacks@'+str(library['mixin_abi']))
                if library.get('functional_abi'):
                    intrinsics.add('neocore.runtime.Functional@'+str(library['functional_abi']))
                if library.get('collection_abi'):
                    intrinsics.add('neocore.runtime.JavaCollections@'+str(library['collection_abi']))
                if library.get('receiver_kind')=='profiler':intrinsics.add('neocore.runtime.Profilers@1')
                tuple_args='('+', '.join(args)+(',' if args else '')+')'
                is_type_receiver = type_qualifier(receiver)
                api_static_owner=library.get('static_owner')
                if api_static_owner:
                    # Only reviewed static declarations select the owner; never dispatch through the qualifier value.
                    alias=next((types[short] for short,identity in api_identities.items()
                                if identity==api_static_owner and short in types),None)
                    if alias is None:
                        alias='_nc_static_api_'+str(len(required_api_types))
                        while alias in types.values() or any(cls['name']==alias for cls in symbols['classes']):alias+='_' 
                        owner,_,member=api_static_owner.rpartition('.')
                        if not owner or any(part in KEYWORDS for part in owner.split('.')):
                            raise NeedsLowering(node,'Static API owner requires an import adapter')
                        deferred_imports.append('from '+owner+' import '+member+' as '+alias)
                        required_api_types.add(api_static_owner)
                    target=get_attr(alias,library.get('call_name',name))
                    if library.get('caller_logger'):
                        target=get_attr(alias,'forCaller')
                        args=[repr(current['java_name'])]
                    checks=library.get('nonnull_arguments',[])
                    if checks:
                        intrinsics.add('neocore.runtime.Functional@1')
                        def guarded(arguments_name):
                            values=['_nc_Functional.requireNonNull('+arguments_name+'['+str(i)+'])' for i in checks]
                            values.append(target+'(*'+arguments_name+')')
                            return '('+', '.join(values)+')[-1]'
                        if is_type_receiver:return '(lambda _nc_api_args: '+guarded('_nc_api_args')+')('+tuple_args+')'
                        return '(lambda _nc_static_receiver, _nc_static_args: '+guarded('_nc_static_args')+')('+receiver_code+', '+tuple_args+')'
                    if is_type_receiver:return target+'('+', '.join(args)+')'
                    return '(lambda _nc_static_receiver, _nc_static_args: '+target+'(*_nc_static_args))('+receiver_code+', '+tuple_args+')'
                if is_type_receiver:
                    raise NeedsLowering(node,'Instance API method requires an expression receiver: '+name)
                if library.get('receiver_kind')=='profiler':
                    intrinsics.add('neocore.runtime.Profilers@1')
                    return '(lambda _nc_call_receiver, _nc_call_args: _nc_Profilers.invoke(_nc_call_receiver, '+repr(name)+', '+repr(library['parameters'])+', _nc_call_args))('+receiver_code+', '+tuple_args+')'
                if library.get('receiver_kind')=='throwable':
                    intrinsics.add('neocore.runtime.JavaExceptions@3' if library.get('throwable_api') else 'neocore.runtime.JavaExceptions@2')
                    checked='_nc_Exceptions.require(_nc_call_receiver)'
                elif library.get('receiver_kind')=='game_api':
                    intrinsics.add('neocore.runtime.Functional@1')
                    checked='_nc_Functional.requireNonNull(_nc_call_receiver)'
                elif library.get('receiver_kind')=='goal_scheduler':
                    intrinsics.add('neocore.runtime.GoalSchedulers@1')
                    checked='_nc_Goals.require(_nc_call_receiver)'
                elif library.get('receiver_kind')=='memory_stream':
                    intrinsics.add('neocore.runtime.JavaExceptions@2')
                    checked='_nc_Exceptions.requireResource(_nc_call_receiver)'
                else:
                    collection_abi=library.get('collection_abi',1)
                    intrinsics.add('neocore.runtime.JavaCollections@'+str(collection_abi))
                    checked='_nc_Collections.require(_nc_call_receiver, '+str(collection_abi)+')'
                keywords=', **'+repr({'_nc_remove_mode':library['remove_mode']}) if 'remove_mode' in library else ''
                # Java evaluates the receiver and every argument before null checking and virtual dispatch.
                target=get_attr(checked,library.get('call_name',name))+'(*_nc_call_args'+keywords+')'
                if library.get('boxed_native_return'):
                    intrinsics.add('neocore.runtime.Functional@9')
                    target='_nc_Functional.box('+repr(library['boxed_native_return'])+', '+target+')'
                return '(lambda _nc_call_receiver, _nc_call_args: '+target+')('+receiver_code+', '+tuple_args+')'
            if method is not None and not method['static'] and receiver is not None and receiver['kind'] not in ('this','super'):
                if type_qualifier(receiver):
                    raise NeedsLowering(node,'Instance source method requires an expression receiver: '+name)
                intrinsics.add('neocore.runtime.Functional@1')
                tuple_args='('+', '.join(args)+(',' if args else '')+')'
                if 'private' in method.get('modifiers',[]):
                    keywords=repr({'_nc_java_signature':method_signature(method,declaring,overload_unit)})
                    target=get_attr(declaring['name'],name)+'(_nc_Functional.requireNonNull(_nc_call_receiver), *_nc_call_args, **'+keywords+')'
                    return '(lambda _nc_call_receiver, _nc_call_args: '+target+')('+receiver_code+', '+tuple_args+')'
                if declaring.get('runtime_interface_contract'):
                    intrinsics.add('neocore.runtime.RuntimeClasses@'+str(max(6,declaring['runtime_interface_contract'].get('helper_abi',6))))
                    target='_nc_RuntimeClasses.invokeInterface('+repr(declaring['runtime_interface_contract'])+', _nc_call_receiver, '+repr(name)+', '+repr(runtime_signature(method,declaring,overload_unit))+', _nc_call_args)'
                    return '(lambda _nc_call_receiver, _nc_call_args: '+target+')('+receiver_code+', '+tuple_args+')'
                if declaring.get('runtime_contract'):
                    intrinsics.add('neocore.runtime.RuntimeClasses@1')
                    target='_nc_RuntimeClasses.invoke('+repr(declaring['java_name'])+', _nc_call_receiver, '+repr(name)+', '+repr(runtime_signature(method,declaring,overload_unit))+', _nc_call_args)'
                    return '(lambda _nc_call_receiver, _nc_call_args: '+target+')('+receiver_code+', '+tuple_args+')'
                keywords=repr({'_nc_java_signature':method_signature(method,declaring,overload_unit)})
                target=get_attr('_nc_Functional.requireNonNull(_nc_call_receiver)',name)+'(*_nc_call_args, **'+keywords+')'
                return '(lambda _nc_call_receiver, _nc_call_args: '+target+')('+receiver_code+', '+tuple_args+')'
            if method is not None and method['static'] and declaring.get('runtime_contract'):
                intrinsics.add('neocore.runtime.RuntimeClasses@2')
                tuple_args = '(' + ', '.join(args) + (',' if args else '') + ')'
                target = '_nc_RuntimeClasses.invokeStatic(' + repr(declaring['java_name']) + ', ' + repr(name) + ', ' + repr(runtime_signature(method, declaring, overload_unit)) + ', ' + tuple_args + ')'
                if receiver is not None and receiver['kind'] not in ('this', 'super') and not type_qualifier(receiver):
                    return '(lambda _nc_static_receiver: ' + target + ')(' + expr(receiver) + ')'
                return target
            if receiver is not None and receiver['kind'] == 'super' and not method['static']:
                args.insert(0, 'self')
            elif method is not None and not method['static'] and 'private' in method.get('modifiers',[]):
                receiver_code=declaring['name'];args.insert(0,'self')
            if method is not None:
                args.append('_nc_java_signature=' + repr(runtime_signature(method, declaring, overload_unit)))
            call = get_attr(receiver_code, name) + '(' + ', '.join(args) + ')'
            if method is not None and method['static'] and receiver is not None and receiver['kind'] not in ('super','this'):
                declaring_code = project_type_reference(declaring['java_name'], node)
                static_call = get_attr(declaring_code, name) + '(' + ', '.join(args) + ')'
                # Java evaluates an expression qualifier but dispatches static methods by declared type, even if null.
                if not type_qualifier(receiver):
                    return '(lambda _nc_static_receiver: ' + static_call + ')(' + expr(receiver) + ')'
                return static_call
            return call
        if kind == 'unary_expression' and text(field(node, 'operator')) in ('+', '-'):
            operand = field(node, 'operand')
            operator = text(field(node, 'operator'))
            if operand['kind'] in INTEGER_KINDS:
                value, width = literal_value(operand, text(operand), NeedsLowering,
                    allow_decimal_min=operator == '-')
                if operator == '-':
                    value = -value
                value = (value + (1 << (width - 1))) % (1 << width) - (1 << (width - 1))
                return str(value)
            promoted=numeric_type(expression_type(operand))
            if promoted is None:
                raise NeedsLowering(node, 'Unary numeric promotion requires a resolved primitive numeric type')
            if promoted=='int':
                intrinsics.add('neocore.runtime.Int32@1')
                return '_nc_Int32.' + ('negate' if operator == '-' else 'wrap') + '(' + expr(operand) + ')'
            intrinsics.add('neocore.runtime.PrimitiveMath@1')
            return '_nc_PrimitiveMath.unary('+repr(promoted)+', '+repr(operator)+', '+expr(operand)+')'
        if kind == 'unary_expression' and text(field(node, 'operator')) == '~':
            operand = field(node, 'operand')
            if expression_type(operand) != 'int':
                raise NeedsLowering(node, 'Bitwise complement requires resolved int type')
            intrinsics.add('neocore.runtime.Int32@2')
            return '_nc_Int32.bitNot(' + expr(operand) + ')'
        if kind == 'binary_expression' and text(field(node, 'operator')) in ('&', '|', '^', '<<', '>>', '>>>'):
            operator = text(field(node, 'operator'))
            left, right = field(node, 'left'), field(node, 'right')
            if expression_type(node) == 'boolean':
                return '(' + expr(left) + ' ' + operator + ' ' + expr(right) + ')'
            if expression_type(left) != 'int' or expression_type(right) != 'int':
                raise NeedsLowering(node, 'Bit/shift operation requires resolved int operands')
            methods = {'&': 'bitAnd', '|': 'bitOr', '^': 'bitXor', '<<': 'shiftLeft',
                       '>>': 'shiftRight', '>>>': 'unsignedShiftRight'}
            intrinsics.add('neocore.runtime.Int32@2')
            return '_nc_Int32.' + methods[operator] + '(' + expr(left) + ', ' + expr(right) + ')'
        if kind == 'binary_expression' and text(field(node, 'operator')) in ('+', '-', '*', '/', '%'):
            if expression_type(node) == 'java.lang.String':
                return '_nc_String(_nc_String.valueOf(' + expr(field(node,'left')) + ') + _nc_String.valueOf(' + expr(field(node,'right')) + '))'
            promoted=binary_numeric_type(expression_type(field(node,'left')),expression_type(field(node,'right')))
            if promoted is None:
                raise NeedsLowering(node, 'Numeric/string promotion requires resolved primitive numeric operands')
            method = {'+': 'add', '-': 'subtract', '*': 'multiply', '/': 'divide', '%': 'remainder'}[text(field(node, 'operator'))]
            if promoted=='int':
                intrinsics.add('neocore.runtime.Int32@1')
                return '_nc_Int32.' + method + '(' + numeric_operand(field(node, 'left')) + ', ' + numeric_operand(field(node, 'right')) + ')'
            intrinsics.add('neocore.runtime.PrimitiveMath@1')
            return '_nc_PrimitiveMath.binary('+repr(promoted)+', '+repr(text(field(node,'operator')))+', '+numeric_operand(field(node,'left'))+', '+numeric_operand(field(node,'right'))+')'
        if kind == 'binary_expression' and text(field(node, 'operator')) in ('<', '>', '<=', '>=', '==', '!='):
            left,right=field(node,'left'),field(node,'right')
            if text(field(node,'operator')) in ('==','!=') and reference_equality(original_type(left) or expression_type(left),original_type(right) or expression_type(right)):
                return '('+expr(left)+(' is ' if text(field(node,'operator'))=='==' else ' is not ')+expr(right)+')'
            if text(field(node,'operator')) in ('==','!=') and scalar_type(left) in UNBOXES and scalar_type(right) in UNBOXES:
                raise NeedsLowering(node,'Incompatible wrapper references cannot be compared for identity')
            if expression_type(node) != 'boolean':
                raise NeedsLowering(node, 'Comparison requires resolved primitive types; reference equality is separate')
            promoted=binary_numeric_type(expression_type(left),expression_type(right))
            return '(' + numeric_operand(left,promoted) + ' ' + text(field(node, 'operator')) + ' ' + numeric_operand(right,promoted) + ')'
        if kind == 'unary_expression' and text(field(node, 'operator')) == '!':
            return '(not ' + boolean_expression(field(node, 'operand')) + ')'
        if kind == 'binary_expression' and text(field(node, 'operator')) in ('&&', '||'):
            operator = ' and ' if text(field(node, 'operator')) == '&&' else ' or '
            return boolean_expression(node)
        if kind == 'ternary_expression':
            left, right = field(node, 'consequence'), field(node, 'alternative')
            functional_branches = any(child['kind'] in ('lambda_expression', 'method_reference') for branch in (left, right) for child in walk(branch))
            if (expected is None or not functional_branches) and (expression_type(left) != expression_type(right) or expression_type(left) is None):
                raise NeedsLowering(node, 'Conditional result types and promotion require resolution')
            condition,yes,no=condition_flow(field(node,'condition'))
            set_uninitialized(yes);left_code=expr(left,expected);left_state=set(uninitialized)
            set_uninitialized(no);right_code=expr(right,expected);right_state=set(uninitialized)
            set_uninitialized(left_state|right_state)
            return '('+left_code+' if '+condition+' else '+right_code+')'
        if kind == 'object_creation_expression':
            type_name = text(field(node, 'type'))
            if canonical_method_type(type_name.split('<',1)[0],current,overload_unit) in ir.get('runtime_generic_interfaces',{}):
                raise NeedsLowering(node,'Java interfaces cannot be instantiated')
            declaration_type=type_name
            if '<' in type_name:
                type_name = type_name.split('<',1)[0].strip()
            if any(c['kind'] == 'class_body' for c in node.get('children', [])):
                raise NeedsLowering(node, 'Constructor type/anonymous class requires resolution')
            arguments = named(field(node, 'arguments'))
            declaration = reference_class(declaration_type)
            if declaration is not None:
                if declaration['kind']=='interface_declaration':raise NeedsLowering(node,'Java interfaces cannot be instantiated')
                if declaration['kind']=='interface_declaration':
                    raise NeedsLowering(node,'Java interfaces cannot be instantiated')
                if 'abstract' in declaration.get('modifiers',[]):
                    raise NeedsLowering(node,'Abstract class cannot be instantiated')
                selected = selected_constructor(declaration, arguments, node)
                argument_codes = [converted_argument(arg, selected['parameters'][index]['declared_type'], declaration) for index, arg in enumerate(arguments)]
                argument_codes.append('_nc_java_constructor=' + repr(runtime_signature(selected, declaration, overload_unit)))
                if declaration.get('runtime_contract'):
                    contract=declaration['runtime_contract'];intrinsics.add('neocore.runtime.RuntimeClasses@'+str(contract.get('helper_abi',1)));required_api_types.add(declaration['java_name'])
                    return '_nc_RuntimeClasses.bind('+repr(declaration['java_name'])+', '+repr(contract)+')('+', '.join(argument_codes)+')'
            else:
                identity=canonical_method_type(type_name,current,overload_unit)
                if identity in deferred_external_types:raise NeedsLowering(node,'External constructor requires complete translated dependency ABI',{'category':'EXTERNAL_ABI_REQUIRED','symbol':identity,'operation':'constructor'})
                if identity=='com.google.common.collect.ImmutableMap':raise NeedsLowering(node,'ImmutableMap is abstract; use its reviewed factories')
                if identity=='com.google.common.collect.ImmutableMap.Builder' and arguments:raise NeedsLowering(node,'Unreviewed ImmutableMap.Builder constructor')
                from java_model_math_signatures import TYPES as MODEL_TYPES,constructor as model_constructor
                if identity in MODEL_TYPES:
                    try:formals=model_constructor(identity,[invocation_type(arg) for arg in arguments])
                    except ValueError as error:raise NeedsLowering(node,str(error))
                    return project_type_reference(type_name,node)+'('+', '.join(converted_argument(arg,formal,current) for arg,formal in zip(arguments,formals))+')'
                from java_vertex_signatures import TYPES as VERTEX_TYPES,constructor as vertex_constructor
                if identity in VERTEX_TYPES:
                    try:formals=vertex_constructor(identity,[invocation_type(arg) for arg in arguments])
                    except ValueError as error:raise NeedsLowering(node,str(error))
                    return project_type_reference(type_name,node)+'('+', '.join(converted_argument(arg,formal,current) for arg,formal in zip(arguments,formals))+')'
                from java_gui_signatures import TYPES as GUI_TYPES,constructor as gui_constructor
                if identity in GUI_TYPES:
                    try:formals=gui_constructor(identity,[invocation_type(arg) for arg in arguments])
                    except ValueError as error:raise NeedsLowering(node,str(error))
                    return project_type_reference(type_name,node)+'('+', '.join(converted_argument(arg,formal,current) for arg,formal in zip(arguments,formals))+')'
                if identity in TRADING_TYPES:
                    try:formals=trading_constructor(identity,[invocation_type(arg) for arg in arguments])
                    except ValueError as error:raise NeedsLowering(node,str(error))
                    codes=[converted_argument(arg,formal,current) for arg,formal in zip(arguments,formals)]
                    return project_type_reference(type_name,node)+'('+', '.join(codes)+')'
                if identity=='net.minecraft.network.protocol.common.custom.CustomPacketPayload.Type':
                    if len(arguments)!=1 or invocation_type(arguments[0]) not in ('net.minecraft.resources.ResourceLocation','<null>'):raise NeedsLowering(node,'Payload Type requires ResourceLocation or null')
                if identity in ('io.netty.buffer.ByteBuf','io.netty.buffer.Unpooled','net.minecraft.network.codec.StreamCodec','net.minecraft.network.protocol.common.custom.CustomPacketPayload'):
                    raise NeedsLowering(node,'Network interface/abstract/static factory type cannot be instantiated')
                if identity in ir.get('runtime_enum_types',{}) or identity in tuple('net.minecraft.util.profiling.'+name for name in ('ProfilerFiller','ProfileCollector','InactiveProfiler','ProfileResults','EmptyProfileResults')):
                    raise NeedsLowering(node,'Enum/interface/private profiler constructor cannot be instantiated')
                if identity in ('net.minecraft.world.entity.ai.goal.GoalSelector','net.minecraft.world.entity.ai.goal.WrappedGoal'):
                    signatures={'net.minecraft.world.entity.ai.goal.GoalSelector':['java.util.function.Supplier<net.minecraft.util.profiling.ProfilerFiller>'],
                        'net.minecraft.world.entity.ai.goal.WrappedGoal':['int','net.minecraft.world.entity.ai.goal.Goal']}
                    signature=signatures[identity]
                    if len(arguments)!=len(signature):raise NeedsLowering(node,'Goal scheduler constructor requires the reviewed Java signature')
                    argument_codes=[converted_argument(arg,signature[index],current) for index,arg in enumerate(arguments)]
                    intrinsics.add('neocore.runtime.GoalSchedulers@1')
                    return '_nc_Goals.construct('+repr(identity)+', '+project_type_reference(type_name,node)+', ['+', '.join(argument_codes)+'])'
                if identity in ('java.util.HashMap','java.util.LinkedHashMap'):
                    actuals = [invocation_type(arg) for arg in arguments]
                    valid = len(arguments) == 0
                    formals = list(actuals)
                    if len(arguments) == 1:
                        actual = actuals[0]
                        capacity = actual in ('int','java.lang.Integer')
                        valid = capacity or actual == '<null>' or actual and canonical_method_type(actual.split('<',1)[0],current,overload_unit) in ('java.util.Map','java.util.HashMap','java.util.LinkedHashMap')
                        formals = ['int' if capacity else 'java.util.Map']
                    elif len(arguments) in (2,3):
                        valid = actuals[0] in ('int','java.lang.Integer') and actuals[1] in ('int','float')
                        if len(arguments) == 3:
                            valid = valid and identity == 'java.util.LinkedHashMap' and actuals[2] == 'boolean'
                        formals = ['int', actuals[1]] + (['boolean'] if len(arguments) == 3 else [])
                    if not valid:
                        raise NeedsLowering(node,'Map constructor signature requires a reviewed capacity/load-factor/map adapter')
                    intrinsics.add('neocore.runtime.JavaCollections@5')
                    argument_codes = [expr(arg,formal) for arg,formal in zip(arguments,formals)]
                    return project_type_reference(type_name,node) + '(' + ', '.join(argument_codes) + ')'
                if identity in ('java.util.HashSet','java.util.LinkedHashSet'):
                    if len(arguments) > 1:
                        raise NeedsLowering(node,'Set constructor requires zero arguments, capacity, or a collection; load-factor overload not reviewed')
                    intrinsics.add('neocore.runtime.JavaCollections@3')
                if identity == 'java.util.Set':
                    raise NeedsLowering(node,'Set interface cannot be instantiated')
                if identity in exception_constructors:
                    owner={'name':identity.rsplit('.',1)[1],'java_name':identity}
                    candidates=[(owner,{'parameters':[{'declared_type':formal} for formal in signature]}) for signature in exception_constructors[identity]]
                    _,selected=select_overload(candidates,[invocation_type(arg) for arg in arguments],parents,overload_unit,node,NeedsLowering)
                    signature=tuple(parameter['declared_type'] for parameter in selected['parameters'])
                    if identity=='java.lang.AssertionError' and any(formal in ('float','double','char') for formal in signature):
                        raise NeedsLowering(node,'AssertionError primitive text conversion requires reviewed numeric/character formatting')
                    argument_codes=[expr(arg,signature[index]) for index,arg in enumerate(arguments)]
                    intrinsics.add('neocore.runtime.JavaExceptions@3')
                    return '_nc_Exceptions.construct('+project_type_reference(type_name,node)+', '+repr(identity)+', '+repr(signature)+', ['+', '.join(argument_codes)+'])'
                argument_codes = [expr(arg) for arg in arguments]
            return project_type_reference(type_name, node) + '(' + ', '.join(argument_codes) + ')'
        raise NeedsLowering(node, 'Expression semantics not lowered: ' + kind)
    def record_write_target(node):
        def checked(declaring,member):
            if member and member.get('storage_name') and current['java_name']!=declaring['java_name'] and (current.get('anonymous_codec') or {}).get('owner')!=declaring['java_name']:
                raise NeedsLowering(node,'Renamed field is private; use its accessor')
            return member
        if node['kind']=='identifier':
            if text(node) in locals_map:return None
            return checked(*find_member(text(node),'fields'))
        if node['kind']=='field_access':
            receiver=field(node,'object')
            owner=current if receiver['kind']=='this' else reference_class(text(receiver)) if type_qualifier(receiver) else reference_class(expression_type(receiver))
            return checked(*find_member(text(field(node,'field')),'fields',owner)) if owner else None
        return None
    def checked_record_write(node):
        member=record_write_target(node)
        if member and member.get('record_component') and not current_method_constructor:raise NeedsLowering(node,'Record component is final')
        return member
    def emit_compound(left, method, right_code, indent):
        target_member=checked_record_write(left)
        prefix = '    ' * indent
        intrinsics.add('neocore.runtime.Int32@1')
        if left['kind']=='array_access':
            number=str(assignment_counter[0]);assignment_counter[0]+=1
            array,index,old='_nc_array_'+number,'_nc_index_'+number,'_nc_old_'+number
            intrinsics.add('neocore.runtime.JavaArrays@1')
            return [prefix+array+' = '+expr(field(left,'array')),prefix+index+' = '+expr(field(left,'index')),
                    prefix+old+' = _nc_JavaArrays.get('+array+', '+index+')',
                    prefix+'_nc_JavaArrays.set('+array+', '+index+', _nc_Int32.'+method+'('+old+', '+right_code+'))']
        if left['kind'] == 'identifier' and text(left) in locals_map:
            target = expr(left)
            return [prefix + target + ' = _nc_Int32.' + method + '(' + target + ', ' + right_code + ')']
        if left['kind'] == 'field_access':
            object_node, name = field(left, 'object'), text(field(left, 'field'))
            if object_node['kind'] in ('this', 'super'):
                owner = current if object_node['kind'] == 'this' else parents.get(current['name'])
                declaring, member = find_member(name, 'fields', owner) if owner is not None else (None, None)
                if member is None or static_context:
                    raise NeedsLowering(left, 'Unresolved instance compound target')
                receiver = declaring['name'] if member['static'] else 'self'
            else:
                receiver = expr(object_node)
        elif left['kind'] == 'identifier':
            name = text(left)
            member = find_field(name)
            if member is None or (static_context and not member['static']):
                raise NeedsLowering(left, 'Compound field target requires resolution')
            receiver = static_owner(name, 'fields') if member['static'] else 'self'
        else:
            raise NeedsLowering(left, 'Compound assignment target requires lowering')
        number = str(assignment_counter[0])
        assignment_counter[0] += 1
        if target_member:name=target_member.get('storage_name',name)
        owner, old_value = '_nc_owner_' + number, '_nc_old_' + number
        return [prefix + owner + ' = ' + receiver,
            prefix + old_value + ' = getattr(' + owner + ', ' + repr(name) + ')',
            prefix + 'setattr(' + owner + ', ' + repr(name) + ', _nc_Int32.' + method +
            '(' + old_value + ', ' + right_code + '))']
    def statement(node, indent):
        prefix = '    ' * indent
        kind = node['kind']
        if kind == 'empty_statement' or kind == ';':
            return [prefix + 'pass']
        if kind == 'throw_statement':
            operand=next((child for child in named(node) if child['kind']!='throw'),None)
            if operand is None:raise NeedsLowering(node,'Throw expression is missing')
            intrinsics.add('neocore.runtime.JavaExceptions@1')
            return [prefix+'raise _nc_Exceptions.throwable('+expr(operand)+')']
        if kind in ('try_statement','try_with_resources_statement'):
            try_entry=set(uninitialized)
            body=field(node,'body')
            catches=[child for child in node.get('children',[]) if child['kind']=='catch_clause']
            final=next((child for child in node.get('children',[]) if child['kind']=='finally_clause'),None)
            resources=field(node,'resources') if kind=='try_with_resources_statement' else None
            if body is None or not (catches or final or resources):raise NeedsLowering(node,'Try body/catch/finally is unresolved')
            intrinsics.add('neocore.runtime.JavaExceptions@2' if resources else 'neocore.runtime.JavaExceptions@1')
            def resource_body(depth):
                if not resources:return statement(body,depth)
                saved_names,saved_types,saved_uninitialized=dict(locals_map),dict(local_types),set(uninitialized)
                output=[]
                try:
                    entries=[child for child in resources.get('children',[]) if child['kind']=='resource']
                    if not entries:raise NeedsLowering(resources,'Resource declaration shape is unresolved')
                    for entry in entries:
                        name_node,type_node,value_node=field(entry,'name'),field(entry,'type'),field(entry,'value')
                        if name_node is None:
                            children=[child for child in named(entry) if child['kind']!=';']
                            if len(children)!=1 or children[0]['kind'] not in ('identifier','field_access'):raise NeedsLowering(entry,'Resource reference requires an effectively-final local or final field')
                            reference=children[0];name=text(reference)
                            if reference['kind']=='identifier' and name in locals_map:
                                for child in walk(current_method_body):
                                    if child['kind']=='assignment_expression' and text(field(child,'left'))==name:
                                        raise NeedsLowering(entry,'Resource reference is not effectively final')
                            else:
                                if reference['kind']=='identifier':member=find_field(name)
                                else:
                                    receiver=field(reference,'object')
                                    owner=current if receiver['kind']=='this' else parents.get(current['name']) if receiver['kind']=='super' else reference_class(text(receiver)) if type_qualifier(receiver) else reference_class(expression_type(receiver))
                                    member=find_member(text(field(reference,'field')),'fields',owner)[1] if owner else None
                                if member is None or not member.get('final'):raise NeedsLowering(entry,'Resource field reference must resolve to a final field')
                            code=expr(reference);safe='_nc_resource_'+str(local_counter[0]);local_counter[0]+=1
                        else:
                            name=text(name_node)
                            if name in locals_map:raise NeedsLowering(entry,'Resource declaration shadows active local')
                            if value_node is None:raise NeedsLowering(entry,'Resource initializer is missing')
                            declared=text(type_node)
                            if declared=='var':declared=invocation_type(value_node)
                            if declared is None:raise NeedsLowering(entry,'Resource type inference is unresolved')
                            code=expr(value_node,declared)
                            safe='_nc_resource_'+str(local_counter[0]);local_counter[0]+=1
                            locals_map[name],local_types[name]=safe,declared
                            for child in walk(body):
                                if child['kind']=='assignment_expression' and text(field(child,'left'))==name:raise NeedsLowering(child,'Resource variable is implicitly final')
                        output.append('    '*depth+'with _nc_Exceptions.resource('+code+') as '+safe+':')
                        depth+=1
                    output.extend(statement(body,depth))
                    return output
                finally:
                    locals_map.clear();locals_map.update(saved_names)
                    local_types.clear();local_types.update(saved_types)
                    uninitialized.clear();uninitialized.update(saved_uninitialized)
            output=([prefix+'try:']+resource_body(indent+1)) if catches or final else resource_body(indent)
            for catch in catches:
                set_uninitialized(try_entry)
                parameter=next((child for child in catch.get('children',[]) if child['kind']=='catch_formal_parameter'),None)
                catch_type=next((child for child in parameter.get('children',[]) if child['kind']=='catch_type'),None) if parameter else None
                if catch_type is None:raise NeedsLowering(catch,'Catch type is missing')
                type_nodes=[child for child in named(catch_type) if child['kind']!='|']
                refs=[project_type_reference(text(child),child) for child in type_nodes]
                if not refs:raise NeedsLowering(catch_type,'Empty catch type')
                name=text(field(parameter,'name'))
                if name in locals_map:raise NeedsLowering(parameter,'Catch parameter shadows an active local')
                saved_names,saved_types,saved_uninitialized=dict(locals_map),dict(local_types),set(uninitialized)
                safe='_nc_catch_'+str(local_counter[0]);local_counter[0]+=1
                locals_map[name]=safe
                local_types[name]=text(type_nodes[0]) if len(type_nodes)==1 else 'java.lang.Exception'
                target=refs[0] if len(refs)==1 else '('+', '.join(refs)+')'
                output.append(prefix+'except _nc_Exceptions.catchType('+target+') as '+safe+':')
                try:output.extend(statement(field(catch,'body'),indent+1))
                finally:
                    locals_map.clear();locals_map.update(saved_names)
                    local_types.clear();local_types.update(saved_types)
                    uninitialized.clear();uninitialized.update(saved_uninitialized)
            # Catch and finally may observe an exception before any try-body
            # store. Until exceptional-flow proof exists retain entry facts.
            set_uninitialized(try_entry)
            if final:
                final_body=next((child for child in final.get('children',[]) if child['kind']=='block'),None)
                output.append(prefix+'finally:')
                output.extend(statement(final_body,indent+1))
            return output
        if kind == 'enhanced_for_statement':
            name, declared_type = text(field(node,'name')), text(field(node,'type'))
            if declared_type=='var' or name in locals_map:
                raise NeedsLowering(node,'Enhanced-for type/scope requires resolution')
            saved_names,saved_types,saved_uninitialized=dict(locals_map),dict(local_types),set(uninitialized)
            target=expr(field(node,'value'))
            safe='_nc_each_'+str(local_counter[0]);local_counter[0]+=1
            locals_map[name],local_types[name]=safe,declared_type
            intrinsics.add('neocore.runtime.JavaArrays@1')
            output=[prefix+'for '+safe+' in _nc_JavaArrays.iterate('+target+'):']
            if declared_type=='int' and not (expression_type(field(node,'value')) or '').endswith('int[]'):
                intrinsics.add('neocore.runtime.Functional@2')
                output.append(prefix+'    '+safe+' = _nc_Functional.unboxInt('+safe+')')
            loop_depth[0]+=1
            try:output.extend(statement(field(node,'body'),indent+1))
            finally:
                loop_depth[0]-=1
                locals_map.clear();locals_map.update(saved_names)
                local_types.clear();local_types.update(saved_types)
                uninitialized.clear();uninitialized.update(saved_uninitialized)
            return output
        if kind == 'for_statement':
            saved_names, saved_types, saved_uninitialized = dict(locals_map), dict(local_types), set(uninitialized)
            first = '_nc_for_first_' + str(for_counter[0])
            for_counter[0] += 1
            def header_statement(child, depth):
                if child['kind'] == 'local_variable_declaration':
                    return statement(child, depth)
                return statement({'kind': 'expression_statement', 'children': [child], 'line': child['line']}, depth)
            try:
                output = []
                for child in node.get('children', []):
                    if child.get('field') == 'init':
                        output.extend(header_statement(child, indent))
                output.extend([prefix + first + ' = True', prefix + 'while True:',
                               prefix + '    if not ' + first + ':'])
                updates = [child for child in node.get('children', []) if child.get('field') == 'update']
                update_position=len(output)
                if uninitialized and any(c['kind']=='continue_statement' for c in walk(field(node,'body'))):raise NeedsLowering(node,'Definite assignment across for-continue requires loop flow lowering')
                output.append(prefix + '    ' + first + ' = False')
                condition = field(node, 'condition')
                if condition is not None:
                    output.extend([prefix + '    if not ' + boolean_expression(condition) + ':',
                                   prefix + '        break'])
                loop_depth[0] += 1
                try:
                    output.extend(statement(field(node, 'body'), indent + 1))
                finally:
                    loop_depth[0] -= 1
                update_lines=[]
                for child in updates:update_lines.extend(header_statement(child,indent+2))
                output[update_position:update_position]=update_lines or [prefix+'        pass']
                return output
            finally:
                locals_map.clear()
                locals_map.update(saved_names)
                local_types.clear()
                local_types.update(saved_types)
                uninitialized.clear()
                uninitialized.update(saved_uninitialized)
        if kind in ('block', 'constructor_body'):
            children = named(node)
            output = []
            saved_names, saved_types, saved_uninitialized = dict(locals_map), dict(local_types), set(uninitialized)
            try:
                for child in children:
                    output.extend(statement(child, indent))
            finally:
                remaining=uninitialized&set(saved_names)
                locals_map.clear()
                locals_map.update(saved_names)
                local_types.clear()
                local_types.update(saved_types)
                uninitialized.clear()
                uninitialized.update(remaining)
            return output or [prefix + 'pass']
        if kind == 'local_variable_declaration':
            declared_type = text(field(node, 'type'))
            if declared_type == 'var':
                raise NeedsLowering(node, 'var type inference requires semantic resolution')
            output = []
            for declarator in node.get('children', []):
                if declarator['kind'] != 'variable_declarator':
                    continue
                name = text(field(declarator, 'name'))
                if name in locals_map:
                    raise NeedsLowering(declarator, 'Local declaration overlaps an existing parameter/local')
                value = field(declarator, 'value')
                safe = '_nc_local_' + str(local_counter[0])
                local_counter[0] += 1
                locals_map[name] = safe
                local_types[name] = declared_type
                uninitialized.add(name)
                variable_type = declared_type + (text(field(declarator,'dimensions')) or '')
                local_types[name] = variable_type
                if value is None:
                    # Allocation is not a Java default value: reads are still
                    # forbidden until every incoming path has assigned it.
                    locals_map[name]=safe+'[0]'
                    output.append(prefix+safe+' = [None]')
                    continue
                initializer = expr(value, variable_type)
                # CFR may erase a holder local. Its single assignment still
                # proves the read type; mutable generic containers stay raw.
                if '<' not in variable_type:
                    from java_method_generics import readonly_local_type
                    refined=readonly_local_type(name,variable_type,invocation_type(value),current_method_body,lambda v:canonical_method_type(v,current,overload_unit))
                    if refined:local_types[name]=refined
                uninitialized.remove(name)
                output.append(prefix + safe + ' = ' + initializer)
            return output
        if kind == 'while_statement':
            condition,yes,no=condition_flow(field(node,'condition'))
            output = [prefix + 'while ' + condition + ':'];set_uninitialized(yes)
            loop_depth[0] += 1
            try:
                output.extend(statement(field(node, 'body'), indent + 1))
            finally:
                loop_depth[0] -= 1
                set_uninitialized(yes|no)
            return output
        if kind == 'do_statement':
            first = '_nc_do_first_' + str(for_counter[0])
            for_counter[0] += 1
            if uninitialized and any(c['kind'] in ('break_statement','continue_statement') for c in walk(field(node,'body'))):raise NeedsLowering(node,'Definite assignment across do-loop control requires flow lowering')
            loop_depth[0] += 1
            try:
                body_lines=statement(field(node,'body'),indent+1)
            finally:
                loop_depth[0] -= 1
            condition=boolean_expression(field(node,'condition'))
            return [prefix+first+' = True',prefix+'while '+first+' or '+condition+':',prefix+'    '+first+' = False']+body_lines
        if kind in ('break_statement', 'continue_statement'):
            if not loop_depth[0]:
                raise NeedsLowering(node, 'Loop control outside supported loop')
            if any(child['kind'] == 'identifier' for child in named(node)):
                raise NeedsLowering(node, 'Labeled loop control requires lowering')
            return [prefix + ('break' if kind == 'break_statement' else 'continue')]
        if kind == 'if_statement':
            condition,yes,no=condition_flow(field(node,'condition'))
            output = [prefix + 'if ' + condition + ':'];set_uninitialized(yes)
            output.extend(statement(field(node, 'consequence'), indent + 1))
            consequent_state=set(uninitialized);set_uninitialized(no)
            alternative = field(node, 'alternative')
            if alternative is not None:
                output.append(prefix + 'else:')
                output.extend(statement(alternative, indent + 1))
            states=[]
            if not always_abrupt(field(node,'consequence')):states.append(consequent_state)
            if not always_abrupt(alternative):states.append(set(uninitialized))
            set_uninitialized(set().union(*states) if states else consequent_state|set(uninitialized))
            return output
        if kind == 'return_statement':
            children = [c for c in named(node) if c['kind'] != 'return']
            if current_sam_return is not None:validate_sam_return(children[0] if children else None,current_sam_return)
            elif current.get('_method_type_bindings') and current_return_type is not None:
                validate_sam_return(children[0] if children else None,current_return_type)
            return [prefix + ('return ' + expr(children[0], current_return_type) if children else 'return')]
        if kind == 'expression_statement':
            child = named(node)[0]
            if child['kind'] == 'update_expression':
                operand = next((item for item in child.get('children', []) if item['kind'] not in ('++', '--')), None)
                operator = next((item['kind'] for item in child.get('children', []) if item['kind'] in ('++', '--')), None)
                if operand is None or expression_type(operand) != 'int':
                    raise NeedsLowering(child, 'Increment/decrement needs resolved int lvalue')
                return emit_compound(operand, 'add' if operator == '++' else 'subtract', '1', indent)
            if child['kind'] != 'assignment_expression':
                return [prefix + expr(child)]
            operator = text(field(child, 'operator'))
            left, right_node = field(child, 'left'), field(child, 'right')
            target_member=checked_record_write(left)
            api_field=library_field(left)
            if api_field and api_field.get('final',True):
                message='Final profiler field cannot be assigned' if api_field.get('helper')=='profilers' else 'Final API field cannot be assigned'
                raise NeedsLowering(left,message)
            if api_field:
                actual=expression_type(right_node);expected=api_field['return_type']
                if actual!=expected and not (expected=='float' and actual=='int'):raise NeedsLowering(left,'Mutable API field assignment requires a reviewed primitive conversion')
                if type_qualifier(field(left,'object')):raise NeedsLowering(left,'Instance API field requires an expression receiver')
            if operator != '=':
                methods = {'+=': 'add', '-=': 'subtract', '*=': 'multiply', '/=': 'divide', '%=': 'remainder'}
                if operator not in methods or expression_type(left) != 'int' or expression_type(right_node) != 'int':
                    raise NeedsLowering(child, 'Compound assignment requires resolved int types')
                method = methods[operator]
                intrinsics.add('neocore.runtime.Int32@1')
                return emit_compound(left, method, expr(right_node), indent)
            right = expr(right_node, original_type(left))
            if api_field:
                intrinsics.add('neocore.runtime.Functional@3')
                return [prefix+'(lambda _nc_field_owner, _nc_field_value: setattr(_nc_Functional.requireNonNull(_nc_field_owner), '+repr(text(field(left,'field')))+', _nc_field_value))('+expr(field(left,'object'))+', '+right+')']
            if left['kind']=='array_access':
                intrinsics.add('neocore.runtime.JavaArrays@1')
                return [prefix+'_nc_JavaArrays.set('+expr(field(left,'array'))+', '+expr(field(left,'index'))+', '+right+')']
            if left['kind'] == 'identifier' and text(left) in locals_map:
                uninitialized.discard(text(left))
                return [prefix + locals_map[text(left)] + ' = ' + right]
            if left['kind'] == 'field_access':
                object_node, name = field(left, 'object'), text(field(left, 'field'))
                if object_node['kind'] in ('this', 'super'):
                    owner = current if object_node['kind'] == 'this' else parents.get(current['name'])
                    declaring, member = find_member(name, 'fields', owner) if owner is not None else (None, None)
                    if member is None or static_context:
                        raise NeedsLowering(left, 'Unresolved/invalid instance field assignment: ' + name)
                    receiver = declaring['name'] if member['static'] else 'self'
                else:
                    receiver = expr(object_node)
                return [prefix + 'setattr(' + receiver + ', ' + repr(target_member.get('storage_name',name) if target_member else name) + ', ' + right + ')']
            if left['kind'] == 'identifier':
                name = text(left)
                member = find_field(name)
                if member:
                    if static_context and not member['static']:
                        raise NeedsLowering(left, 'Instance assignment in static context')
                    receiver = static_owner(name, 'fields') if member['static'] else 'self'
                    return [prefix + 'setattr(' + receiver + ', ' + repr(target_member.get('storage_name',name) if target_member else name) + ', ' + right + ')']
            raise NeedsLowering(left, 'Assignment target requires resolution')
        raise NeedsLowering(node, 'Statement semantics not lowered: ' + kind)
    def defaults(member):
        kind = member['declared_type']
        if kind == 'boolean':
            return 'False'
        if kind in ('byte', 'short', 'int', 'long', 'char'):
            return '0' if kind != 'char' else "u'\\x00'"
        if kind in ('float', 'double'):
            return '0.0'
        return 'None'
    for external in external_classes:
        if external.get('runtime_interface_contract'):
            contract=external['runtime_interface_contract'];binding=contract.get('generic_binding')
            intrinsics.add('neocore.runtime.RuntimeClasses@'+str(max(6,contract.get('helper_abi',6)) if binding else max(5,contract.get('helper_abi',5))))
            required_api_types.add(binding['java_name'] if binding else external['java_name'])
            if binding:lines.append(external['name']+' = _nc_RuntimeClasses.bindGenericInterface('+repr(binding['java_name'])+', '+repr(binding['arguments'])+', '+repr(contract)+')')
            else:lines.append(external['name']+' = _nc_RuntimeClasses.bindInterface('+repr(external['java_name'])+', '+repr(contract)+')')
            continue
        if external.get('runtime_contract'):
            intrinsics.add('neocore.runtime.RuntimeClasses@'+str(external['runtime_contract'].get('helper_abi',1)))
            required_api_types.add(external['java_name'])
            lines.append(external['name']+' = _nc_RuntimeClasses.bind('+repr(external['java_name'])+', '+repr(external['runtime_contract'])+')')
            continue
        reference = project_type_reference(external.get('erased_java_name',external['java_name']), external)
        lines.append(external['name'] + ' = ' + reference)
        lines.append("if " + external['name'] + ".__dict__.get('_nc_JavaClassABI') != 2 or " + external['name'] + ".__dict__.get('_nc_JavaMethodsABI') != 1:")
        lines.append('    raise RuntimeError(' + repr('Generated superclass initialization ABI 2 and method dispatch ABI 1 required: ' + external['java_name']) + ')')
    for current in ordered_classes:
        if current['name'] == 'object':
            raise NeedsLowering(current, 'Class name collides with Python allocation builtin')
        parent = parents.get(current['name'])
        protocol_interfaces=current.get('runtime_interfaces',[])
        bases=[parent['name']] if parent else []
        bases.extend(interface['name'] for interface in current.get('source_interfaces',[]))
        # Java permits redundantly listing both an interface and its child. Python
        # requires the most-derived bases only, independent of source list order.
        base_rows=([parent] if parent else [])+current.get('source_interfaces',[])
        bases=[row['name'] for row in base_rows if not any(other['java_name']!=row['java_name'] and overload_subtype(other['java_name'],row['java_name'],parents,overload_unit) for other in base_rows)]
        if protocol_interfaces:
            protocol='java.io.Closeable' if 'java.io.Closeable' in protocol_interfaces else 'java.lang.AutoCloseable'
            bases.append(project_type_reference(protocol,current))
        if current.get('record_components') is not None:
            intrinsics.add('neocore.runtime.JavaRecords@1')
            bases.insert(0,'_nc_Records.Base')
        lines.append('class '+current['name']+'('+', '.join(bases or ['object'])+'):')
        lines.append('    _nc_JavaName = '+repr(current['java_name']))
        if current.get('record_components') is not None:
            lines.append('    _nc_RecordComponents = '+repr(tuple((c['name'],canonical_method_type(c['declared_type'],current,overload_unit),c['storage']) for c in current['record_components'])))
        lines.append('    _nc_JavaClassABI = 2')
        lines.append('    _nc_JavaMethodsABI = 1')
        from java_item_bridges import constant_fuel
        item_bridge = constant_fuel(current, ir, lambda name:canonical_method_type(name,current,overload_unit))
        if item_bridge is not None:
            if any(row['name']=='_nc_ItemBehaviorBridge' for row in current['fields']+current['methods']):
                raise NeedsLowering(current,'Source member collides with item behavior proof')
            lines.append('    _nc_ItemBehaviorBridge = '+repr(item_bridge))
        ancestors = []
        owner = current
        while owner is not None:
            ancestors.insert(0, owner)
            owner = parents.get(owner['name'])
        allocated_fields = [member for owner in ancestors for member in owner['fields'] if not member['static']]
        lines.extend(['    def __new__(cls, *args, **kwargs):', '        _nc_instance = object.__new__(cls)'])
        if 'abstract' in current.get('modifiers',[]):
            lines.append('        if cls is '+current['name']+": raise TypeError('Abstract class cannot be instantiated')")
        if current.get('record_components') is not None:
            lines.append('        if cls is not '+current['name']+": raise TypeError('Records are final')")
        for member in allocated_fields:
            lines.append('        setattr(_nc_instance, ' + repr(member.get('storage_name',member['name'])) + ', ' + defaults(member) + ')')
        lines.extend(['        return _nc_instance', ''])
        instance_fields = [f for f in current['fields'] if not f['static']]
        methods = list(current['methods'])
        if not any(m['constructor'] for m in methods):
            methods.insert(0, constructor_entries(current)[0])
        reserved = {m['name'] for m in methods} | {f['name'] for f in current['fields']}
        aliases = []
        overload_groups = {}
        for source_method in methods:
            if not source_method['constructor']:
                overload_groups.setdefault(source_method['name'], []).append(source_method)
        for declaring,method in current.get('interface_method_bindings',[]):
            overload_groups.setdefault(method['name'],[])
        overload_families = {name: method_family(current, name, parents, overload_unit) for name in overload_groups}
        implementation_names = {}
        from java_method_overloads import erased_signature
        def erased(method,owner):
            try:return erased_signature(method,owner,overload_unit)
            except ValueError as error:raise NeedsLowering(current,str(error))
        for source_name, group in overload_groups.items():
            if len({method['static'] for owner, method in overload_families[source_name]}) != 1:
                raise NeedsLowering(current, 'Mixed static/instance overload family requires a descriptor: ' + source_name)
            if len({erased(method, current) for method in group}) != len(group):
                raise NeedsLowering(current, 'Duplicate/erasure-colliding method signature: ' + source_name)
            if len(overload_families[source_name]) > 1:
                if len({erased(method,owner) for owner,method in overload_families[source_name]})!=len(overload_families[source_name]):
                    raise NeedsLowering(current,'Generic overloads have colliding parameter erasures: '+source_name)
                if any(method.get('type_parameters') for owner,method in overload_families[source_name]):raise NeedsLowering(current,'Method type-variable overload inference requires lowering: '+source_name)
                for ordinal, source_method in enumerate(group):
                    alias = '_nc_overload_' + str(len(implementation_names))
                    while alias in reserved:
                        alias += '_'
                    reserved.add(alias)
                    implementation_names[id(source_method)] = alias
        constructors = [method for method in methods if method['constructor']]
        constructor_signatures = {method_signature(method, current, overload_unit): method for method in constructors}
        if len({erased(method,current) for method in constructors}) != len(constructors):
            raise NeedsLowering(current, 'Duplicate constructor signature')
        constructor_names = {}
        for number, constructor in enumerate(constructors):
            alias = '_nc_ctor_' + str(number)
            while alias in reserved:
                alias += '_'
            reserved.add(alias)
            constructor_names[id(constructor)] = alias
        delegations = {}
        for constructor in constructors:
            children = named(constructor['body']) if constructor['body'] else []
            invocation = children[0] if children and children[0]['kind'] == 'explicit_constructor_invocation' else None
            if invocation is not None and text(field(invocation, 'constructor')) == 'this':
                locals_map = {parameter['name']: parameter['name'] for parameter in constructor['parameters']}
                local_types = {parameter['name']: parameter['declared_type'] for parameter in constructor['parameters']}
                target = selected_constructor(current, named(field(invocation, 'arguments')), invocation)
                delegations[id(constructor)] = id(target)
        for start in delegations:
            seen = set()
            cursor = start
            while cursor in delegations:
                if cursor in seen:
                    raise NeedsLowering(current, 'Cyclic this-constructor delegation')
                seen.add(cursor)
                cursor = delegations[cursor]
        lines.append('    def __init__(self, *_nc_args, **_nc_kwargs):')
        if current['kind']=='interface_declaration':
            lines.append('        if self.__class__ is '+current['name']+':')
            lines.append("            raise TypeError('Java interfaces cannot be instantiated')")
        if current.get('record_components') is not None:
            lines.append("        if getattr(self, '_nc_record_sealed', False): raise TypeError('Record is already initialized')")
        lines.append("        _nc_selected = _nc_kwargs.pop('_nc_java_constructor', None)")
        lines.append('        if _nc_kwargs:')
        lines.append("            raise TypeError('Unexpected constructor keyword arguments')")
        for tag, constructor in constructor_signatures.items():
            condition = '_nc_selected == ' + repr(tag)
            if sum(len(row['parameters']) == len(tag) for row in constructors) == 1:
                condition += ' or (_nc_selected is None and len(_nc_args) == ' + str(len(tag)) + ')'
            lines.append('        if ' + condition + ':')
            if current.get('record_components') is not None:
                lines.append('            _nc_args = _nc_Records.arguments(self, _nc_args)')
                lines.append('            '+current['name']+'.'+constructor_names[id(constructor)]+'(self, *_nc_args)')
                lines.append("            object.__setattr__(self, '_nc_record_sealed', True)")
                lines.append('            return None')
            else:lines.append('            return ' + current['name'] + '.' + constructor_names[id(constructor)] + '(self, *_nc_args)')
        lines.append('        raise TypeError(' + repr('Compile-time Java constructor signature required for ' + current['name']) + ')')
        lines.append('')
        for index, method in enumerate(methods):
            static_context = method['static']
            current_method_constructor=method['constructor']
            current_return_type = method.get('return_type')
            current_method_body = method.get('body')
            current.pop('_method_type_bindings',None)
            if method.get('type_parameters'):
                from java_method_generics import context
                current['_method_type_bindings']=context(current,method,overload_unit)['_method_type_bindings']
            locals_map = {}
            local_types = {}
            parameters = [] if static_context else ['self']
            for number, parameter in enumerate(method['parameters']):
                if parameter.get('varargs') and number!=len(method['parameters'])-1:raise NeedsLowering(method,'Variable-arity parameter must be last')
                if parameter['name'] is None:
                    raise NeedsLowering(method, 'Varargs or unknown parameter shape')
                name = parameter['name']
                safe = '_nc_arg_' + str(number)
                while safe in reserved or safe in parameters:
                    safe += '_'
                locals_map[name] = safe
                local_types[name] = parameter["declared_type"]
                parameters.append(safe)
            if method['body'] is None and current['kind']!='interface_declaration' and not ('abstract' in current.get('modifiers',[]) and 'abstract' in method.get('modifiers',[])):
                raise NeedsLowering(method, 'Abstract/native method')
            name = constructor_names[id(method)] if method['constructor'] else implementation_names.get(id(method), method['name'])
            if not method['constructor'] and (name in KEYWORDS or name.startswith('__') or not name.isidentifier()):
                original = name
                name = '_nc_method_' + str(index)
                while name in reserved:
                    name += '_'
                aliases.append((original, name))
            if not method['constructor']:
                parameters.append('_nc_java_signature=None')
            if static_context or method['name'] in ir.get('native_mixin_handlers',[]):
                # Keep Java instance binding in the body, export a Python function with explicit receiver.
                # Python2 restricted source runtimes cannot unwrap im_func safely.
                lines.append('    @staticmethod')
            lines.append('    def ' + name + '(' + ', '.join(parameters) + '):')
            if current.get('anonymous_codec'):
                for parameter,safe in zip(method['parameters'],parameters[1:]):
                    intrinsics.add('neocore.runtime.Functional@3')
                    lines.append('        '+safe+' = _nc_Functional.castReference('+safe+', '+project_type_reference(parameter['declared_type'],method)+')')
            body = method['body']
            if method.get('record_generated'):
                lines.append('        return _nc_Records.'+method['record_generated']+'(self'+(', '+parameters[1] if method['record_generated']=='equals' else '')+')')
                lines.append('')
                continue
            if body is None:
                lines.append("        raise RuntimeError('Unimplemented abstract interface method')")
                lines.append('')
                continue
            if method['constructor']:
                children = named(body)
                invocation = children[0] if children and children[0]['kind'] == 'explicit_constructor_invocation' else None
                arguments = []
                delegate_this = False
                if invocation is not None:
                    constructor = field(invocation, 'constructor')
                    if text(constructor) not in ('super', 'this') or field(invocation, 'object') is not None:
                        raise NeedsLowering(invocation, 'Qualified constructor delegation requires lowering')
                    delegate_this = text(constructor) == 'this'
                    # Java forbids using this/instance members before the superclass call.
                    static_context = True
                    raw_arguments = named(field(invocation, 'arguments'))
                    target_owner = current if delegate_this else parent
                    selected = selected_constructor(target_owner, raw_arguments, invocation) if target_owner is not None else None
                    arguments = [converted_argument(arg, selected['parameters'][index]['declared_type'], target_owner) if selected is not None else expr(arg) for index, arg in enumerate(raw_arguments)]
                    static_context = False
                    body = dict(body, children=[child for child in body['children'] if child is not invocation])
                elif parent is not None:
                    selected = selected_constructor(parent, [], method)
                if delegate_this:
                    lines.append('        ' + current['name'] + '.' + constructor_names[id(selected)] + '(self' + (', ' + ', '.join(arguments) if arguments else '') + ')')
                elif parent is not None:
                    tag = runtime_signature(selected, parent, overload_unit)
                    lines.append('        ' + parent['name'] + '.__init__(self' + (', ' + ', '.join(arguments) if arguments else '') + ', _nc_java_constructor=' + repr(tag) + ')')
                elif arguments:
                    raise NeedsLowering(invocation, 'Object superclass constructor takes no arguments')
                saved_names, saved_types = dict(locals_map), dict(local_types)
                saved_method_body = current_method_body
                locals_map, local_types = {}, {}
                for initializer in current['initialization_order']:
                    if delegate_this or initializer['static']:
                        continue
                    if initializer['kind'] == 'field':
                        member = initializer['member']
                        if member['initializer'] is not None:
                            lines.append('        setattr(self, ' + repr(member.get('storage_name',member['name'])) + ', ' + expr(member['initializer'], member['declared_type']) + ')')
                    else:
                        current_method_body = initializer['body']
                        lines.extend(statement(initializer['body'], 2))
                current_method_body = saved_method_body
                locals_map, local_types = saved_names, saved_types
            lines.extend(statement(body, 2))
            lines.append('')
        current.pop('_method_type_bindings',None)
        for source_name, group in overload_groups.items():
            visible_entries = overload_families[source_name]
            if len(visible_entries) < 2:
                continue
            public_name = source_name
            if public_name in KEYWORDS or public_name.startswith('__') or not public_name.isidentifier():
                public_name = '_nc_dispatch_' + str(len(aliases))
                while public_name in reserved:
                    public_name += '_'
                aliases.append((source_name, public_name))
            is_static = visible_entries[0][1]['static']
            if is_static:
                lines.append('    @staticmethod')
            lines.append('    def ' + public_name + '(' + ('' if is_static else 'self, ') + '*_nc_args, **_nc_kwargs):')
            lines.append("        _nc_selected = _nc_kwargs.pop('_nc_java_signature', None)")
            lines.append('        if _nc_kwargs:')
            lines.append("            raise TypeError('Unexpected overload keyword arguments')")
            for declaring, source_method in visible_entries:
                tag = runtime_signature(source_method, declaring, overload_unit)
                unique_arity = sum(len(row['parameters']) == len(tag) for owner, row in visible_entries) == 1
                condition = '_nc_selected == ' + repr(tag)
                if unique_arity:
                    condition += ' or (_nc_selected is None and len(_nc_args) == ' + str(len(tag)) + ')'
                lines.append('        if ' + condition + ':')
                call_args = '*_nc_args' if is_static else 'self, *_nc_args'
                if declaring is current:
                    call_code = current['name'] + '.' + implementation_names[id(source_method)] + '(' + call_args + ')'
                else:
                    call_code = get_attr(declaring['name'], source_name) + '(' + call_args + ', _nc_java_signature=' + repr(tag) + ')'
                lines.append('            return ' + call_code)
            lines.append("        raise TypeError('Compile-time Java overload signature required')")
            lines.append('')
        for original, alias in aliases:
            lines.append('setattr(' + current['name'] + ', ' + repr(original) + ', ' + current['name'] + '.__dict__[' + repr(alias) + '])')
        static_context, locals_map = True, {}
        for member in current['fields']:
            if member['static']:
                lines.append('setattr(' + current['name'] + ', ' + repr(member.get('storage_name',member['name'])) + ', ' + defaults(member) + ')')
        local_types = {}
        for initializer in current['initialization_order']:
            if not initializer['static']:
                continue
            if initializer['kind'] == 'field':
                member = initializer['member']
                if member['initializer'] is not None:
                    lines.append('setattr(' + current['name'] + ', ' + repr(member.get('storage_name',member['name'])) + ', ' + expr(member['initializer'], member['declared_type']) + ')')
            else:
                current_method_body = initializer['body']
                lines.extend(statement(initializer['body'], 0))
        lines.append('')
    for cls in ordered_classes:
        if cls['name'] not in event_handlers and not any(row['class_name']==cls['name'] for row in event_subscribers):continue
        if any(field['name']=='_nc_event_handlers' for field in cls['fields']) or any(method['name']=='_nc_event_handlers' for method in cls['methods']):raise NeedsLowering(cls,'Source member collides with event annotation metadata')
        rows=[]
        for handler in event_handlers.get(cls['name'],[]):
            record=dict(handler);record.pop('source_event_type')
            event_reference=project_type_reference(handler['source_event_type'],handler)
            fields=[repr(key)+': '+repr(value) for key,value in record.items() if key!='event_type']
            fields.append("'event_type': "+event_reference)
            rows.append('{'+', '.join(fields)+'}')
        lines.append('setattr('+cls['name']+", '_nc_event_handlers', ("+', '.join(rows)+(',' if rows else '')+'))')
    for index,entry in enumerate(mod_entries):
        name='_nc_mod_entry_'+str(index)
        while any(cls['name']==name for cls in symbols['classes']):name+='_' 
        entry['attribute']=name
        lines.extend(['def '+name+'(context):','    return _nc_ModEntrypoints.create('+entry['class_name']+', '+repr(entry['mod_id'])+', '+repr(tuple(entry['constructor_signature']))+', '+repr(tuple(entry['physical_sides']))+', context)',''])
        intrinsics.add('neocore.runtime.ModEntrypoints@1')
    if required_enums:intrinsics.add('neocore.runtime.EnumSets@1')
    runtime_imports = list(deferred_imports)
    if 'neocore.runtime.JavaRecords@1' in intrinsics:
        runtime_imports.extend(['from neocore.runtime import JavaRecords as _nc_Records',"if getattr(_nc_Records, 'ABI_VERSION', 0) < 1: raise RuntimeError('JavaRecords ABI1 required')"])
    if any(name.startswith('neocore.runtime.MixinCallbacks@') for name in intrinsics):
        mixin_abi=max(int(name.rsplit('@',1)[1]) for name in intrinsics if name.startswith('neocore.runtime.MixinCallbacks@'))
        runtime_imports.extend(['from neocore.runtime import MixinCallbacks as _nc_MixinCallbacks',
            "if getattr(_nc_MixinCallbacks, 'ABI_VERSION', 0) < "+str(mixin_abi)+":",
            "    raise RuntimeError('NeoCore MixinCallbacks ABI"+str(mixin_abi)+" required')"])
    if 'neocore.runtime.GoalSchedulers@1' in intrinsics:
        runtime_imports.extend(['from neocore.runtime import GoalSchedulers as _nc_Goals',
            "if getattr(_nc_Goals, 'ABI_VERSION', 0) < 1:",
            "    raise RuntimeError('GoalSchedulers ABI1 required')"])
    if 'neocore.runtime.Profilers@1' in intrinsics:
        runtime_imports.extend(['from neocore.runtime import Profilers as _nc_Profilers',
            "if getattr(_nc_Profilers, 'ABI_VERSION', 0) < 1:",
            "    raise RuntimeError('Profilers ABI1 required')"])
    if 'neocore.runtime.EnumSets@1' in intrinsics:
        runtime_imports.extend(['from neocore.runtime import EnumSets as _nc_EnumSets',
            "if getattr(_nc_EnumSets, 'ABI_VERSION', 0) < 1:",
            "    raise RuntimeError('NeoCore EnumSets ABI1 required; update the independent core pack.')"])
        for number,identity in enumerate(sorted(required_enums)):
            owner,_,member=identity.rpartition('.')
            alias='_nc_enum_check_'+str(number)
            runtime_imports.extend(['from '+owner+' import '+member+' as '+alias,
                '_nc_EnumSets.requireEnum('+repr(identity)+', '+alias+', '+repr(ir['runtime_enum_types'][identity]['constants'])+')'])
    runtime_class_abi = max([int(value.rsplit('@',1)[1]) for value in intrinsics if value.startswith('neocore.runtime.RuntimeClasses@')] or [1])
    if any(value.startswith('neocore.runtime.RuntimeClasses@') for value in intrinsics):
        runtime_imports.extend(['from neocore.runtime import RuntimeClasses as _nc_RuntimeClasses',
            "if getattr(_nc_RuntimeClasses, 'ABI_VERSION', 0) < " + str(runtime_class_abi) + ':',
            "    raise RuntimeError('NeoCore RuntimeClasses ABI" + str(runtime_class_abi) + " required; update the independent core pack.')"])
    if mod_entries or event_handlers or event_subscribers or 'neocore.runtime.ModEntrypoints@2' in intrinsics:
        mod_abi=2 if event_handlers or event_subscribers or 'neocore.runtime.ModEntrypoints@2' in intrinsics else 1
        intrinsics.add('neocore.runtime.ModEntrypoints@'+str(mod_abi))
        runtime_imports.extend(['from neocore.runtime import ModEntrypoints as _nc_ModEntrypoints',"if getattr(_nc_ModEntrypoints, 'ABI_VERSION', 0) < "+str(mod_abi)+":","    raise RuntimeError('NeoCore ModEntrypoints ABI "+str(mod_abi)+" required; update the independent core pack.')"])
    if any(name.startswith('neocore.runtime.Int32@') for name in intrinsics):
        runtime_imports.append('from neocore.runtime import Int32 as _nc_Int32')
        if 'neocore.runtime.Int32@2' in intrinsics:
            runtime_imports.extend(["if getattr(_nc_Int32, 'ABI_VERSION', 0) < 2:",
                "    raise RuntimeError('NeoCore Int32 ABI 2 required for Java bit/shift operations; update the independent core pack.')"])
    if 'neocore.runtime.PrimitiveMath@1' in intrinsics:
        runtime_imports.extend(['from neocore.runtime import PrimitiveMath as _nc_PrimitiveMath',
            "if getattr(_nc_PrimitiveMath, 'ABI_VERSION', 0) < 1:",
            "    raise RuntimeError('NeoCore PrimitiveMath ABI 1 required; update the independent core pack.')"])
    if any(name.startswith('neocore.runtime.Functional@') for name in intrinsics):
        functional_abi = max(int(name.rsplit('@',1)[1]) for name in intrinsics if name.startswith('neocore.runtime.Functional@'))
        runtime_imports.extend(['from neocore.runtime import Functional as _nc_Functional',
            "if getattr(_nc_Functional, 'ABI_VERSION', 0) < " + str(functional_abi) + ":",
            "    raise RuntimeError('NeoCore Functional ABI " + str(functional_abi) + " required; update the independent core pack.')"])
    if any(name.startswith('neocore.runtime.JavaExceptions@') for name in intrinsics):
        exception_abi=max(int(name.rsplit('@',1)[1]) for name in intrinsics if name.startswith('neocore.runtime.JavaExceptions@'))
        runtime_imports.extend(['from neocore.runtime import JavaExceptions as _nc_Exceptions',
            "if getattr(_nc_Exceptions, 'ABI_VERSION', 0) < "+str(exception_abi)+":",
            "    raise RuntimeError('NeoCore JavaExceptions ABI "+str(exception_abi)+" required; update the independent core pack.')"])
    if any(name.startswith('neocore.runtime.JavaCollections@') for name in intrinsics):
        collection_abi=max(int(name.rsplit('@',1)[1]) for name in intrinsics if name.startswith('neocore.runtime.JavaCollections@'))
        runtime_imports.extend(['from neocore.runtime import JavaCollections as _nc_Collections',
            "if getattr(_nc_Collections, 'ABI_VERSION', 0) < "+str(collection_abi)+":",
            "    raise RuntimeError('NeoCore JavaCollections ABI"+str(collection_abi)+" required; update the independent core pack.')"])
    array_abis=[int(i.rsplit('@',1)[1]) for i in intrinsics if i.startswith('neocore.runtime.JavaArrays@')]
    if array_abis:
        array_abi=max(array_abis)
        runtime_imports.extend(['from neocore.runtime import JavaArrays as _nc_JavaArrays',
            "if getattr(_nc_JavaArrays, 'ABI_VERSION', 0) < "+str(array_abi)+":",
            "    raise RuntimeError('NeoCore JavaArrays ABI "+str(array_abi)+" required; update the independent core pack.')"])
    lines[3:3] = runtime_imports + lambda_helpers
    code = '\n'.join(lines) + '\n'
    ast.parse(code)
    return {'python_source': code, 'status': 'GENERATED_REVIEW_REQUIRED', 'engine_verified': False,
        'source_sha256': ir['source_sha256'], 'origin': ir['origin'], 'package': ir['package'],
        'project_dependencies': sorted(set(dependencies)),
        'external_symbols': external_symbols,
        'translated_dependencies': sorted(translated_dependencies),
        'annotation_metadata': annotation_metadata,
        'required_runtime_helpers': sorted(intrinsics),
        'mod_entrypoints': mod_entries,
        'event_subscribers': event_subscribers,
        'required_api_types': sorted(required_api_types),
        'limits': ['Project inheritance and reviewed runtime superclass adapters with ordered initializers; no full type checking or Java semantic proof.',
            'Unreviewed external runtime inheritance, numeric widening/varargs/generic overload conversions, full runtime annotations and compact/generic/nested/annotated records require further lowering.',
            'JetBrains nullability is preserved as review metadata; bytecode instrumentation and reflective annotation APIs are not reproduced.',
            'Static initialization happens at Python module import; Java lazy initialization is not reproduced.']}
