from java_trading_signatures import resolve as trading_signature
"""Reviewed Java21 and Minecraft1.21.1 API signatures; unknown contracts stay unresolved."""
LISTS={'java.util.List','java.util.ArrayList','java.util.LinkedList','java.util.AbstractList'}
ITERATORS={'java.util.Iterator','java.util.ListIterator'}
PROFILING='net.minecraft.util.profiling.'
REVIEWED_PARENTS={
    'net.neoforged.neoforge.common.ModConfigSpec':['net.neoforged.fml.config.IConfigSpec'],
    PROFILING+'InactiveProfiler':[PROFILING+'ProfileCollector'],
    PROFILING+'ProfileCollector':[PROFILING+'ProfilerFiller'],
    PROFILING+'EmptyProfileResults':[PROFILING+'ProfileResults'],
    'net.minecraft.world.entity.ai.goal.WrappedGoal':['net.minecraft.world.entity.ai.goal.Goal']}
PROFILE_FIELDS={
    PROFILING+'ProfilerFiller':{'ROOT':'java.lang.String'},
    PROFILING+'ProfileCollector':{'ROOT':'java.lang.String'},
    PROFILING+'InactiveProfiler':{'ROOT':'java.lang.String','INSTANCE':PROFILING+'InactiveProfiler'},
    PROFILING+'ProfileResults':{'PATH_SEPARATOR':'char'},
    PROFILING+'EmptyProfileResults':{'PATH_SEPARATOR':'char','EMPTY':PROFILING+'EmptyProfileResults'}}

SETS = {'java.util.Set', 'java.util.HashSet', 'java.util.LinkedHashSet'}

MAPS = {'java.util.Map', 'java.util.HashMap', 'java.util.LinkedHashMap'}


def generic_arguments(raw, allow_wildcards=False):
    """Split reviewed nested type arguments without erasing inner Map.Entry pairs."""
    if '<' not in raw:
        return []
    if not raw.endswith('>') or '?' in raw and not allow_wildcards:
        raise ValueError('Wildcard or malformed generic type requires lowering')
    items, depth, start = [], 0, raw.index('<') + 1
    for index in range(start, len(raw) - 1):
        character = raw[index]
        if character == '<':
            depth += 1
        elif character == '>':
            depth -= 1
        elif character == ',' and depth == 0:
            items.append(raw[start:index])
            start = index + 1
    items.append(raw[start:-1])
    if depth or any(not value for value in items):
        raise ValueError('Malformed generic type requires lowering')
    return items


def canonical_generic(raw, canonical):
    parameters = generic_arguments(raw)
    base = canonical(raw.split('<', 1)[0])
    return base + '<' + ','.join(canonical_generic(item, canonical) for item in parameters) + '>' if parameters else base

def resolve_field(receiver_type,name,canonical):
    if not receiver_type:return None
    owner=canonical(receiver_type.split('<',1)[0])
    if owner=='net.neoforged.fml.config.ModConfig.Type':
        if name not in ('COMMON','CLIENT','SERVER','STARTUP'):raise ValueError('Unreviewed config type constant: '+name)
        return {'return_type':owner,'static_owner':owner,'final':True,'receiver_kind':'game_api'}
    if owner=='net.minecraft.world.item.CreativeModeTabs':
        if name not in ('INGREDIENTS','BUILDING_BLOCKS'):raise ValueError('Unreviewed creative tab field: '+name)
        return {'return_type':'net.minecraft.resources.ResourceKey','static_owner':owner,'final':True,'receiver_kind':'game_api'}
    if owner=='net.minecraft.world.level.block.SoundType' and name in ('WOOD','STONE','GRAVEL','GRASS','METAL','GLASS','SAND','WOOL','SNOW'):
        return {'return_type':owner,'static_owner':owner,'final':True,'receiver_kind':'game_api'}
    from java_model_math_signatures import resolve_field as model_field
    model=model_field(owner,name)
    if model is not None:return model
    from java_tool_signatures import resolve_field as tool_field
    tool=tool_field(owner,name)
    if tool is not None:return tool
    if owner=='java.lang.Float' and name in ('MAX_VALUE','MIN_VALUE','NaN','POSITIVE_INFINITY','NEGATIVE_INFINITY'):
        return {'return_type':'float','static_owner':owner,'final':True,'receiver_kind':'game_api'}
    from java_feature_signatures import resolve_field as feature_field
    feature=feature_field(owner,name)
    if feature is not None:return feature
    from java_network_signatures import resolve_field as network_field
    network=network_field(owner,name)
    if network is not None:return network
    from java_world_signatures import resolve_field as world_field
    world=world_field(owner,name)
    if world is not None:return world
    from java_vertex_signatures import resolve_field as vertex_field
    vertex=vertex_field(owner,name)
    if vertex is not None:return vertex
    target=PROFILE_FIELDS.get(owner,{}).get(name)
    return {'return_type':target,'static_owner':owner,'final':True,'helper':'profilers'} if target else None

def resolve(receiver_type,name,arity,argument_types,canonical,enum_types=None,proves=None):
    if not receiver_type:return None
    raw=receiver_type.replace(' ','')
    base=canonical(raw.split('<',1)[0])
    from java_existing_call_signatures import resolve as existing_signature
    existing=existing_signature(base,name,arity,[canonical(t) if t else t for t in argument_types])
    if existing is not None:return existing
    from java_world_signatures import resolve as world_signature
    world=world_signature(base,name,arity,argument_types)
    if world is not None:return world
    from java_guava_signatures import resolve as guava_signature
    guava=guava_signature(raw,base,name,arity,argument_types,canonical)
    if guava is not None:return guava
    from java_model_math_signatures import resolve as model_signature
    model=model_signature(base,name,arity,argument_types)
    if model is not None:return model
    from java_tool_signatures import resolve as tool_signature
    tool=tool_signature(raw,base,name,arity,argument_types,canonical)
    if tool is not None:return tool
    from java_menu_signatures import resolve as menu_signature
    menu=menu_signature(raw,base,name,arity,argument_types,canonical_generic,generic_arguments,canonical)
    if menu is not None:return menu
    from java_feature_signatures import resolve as feature_signature
    feature=feature_signature(base,name,arity,argument_types)
    if feature is not None:return feature
    from java_item_signatures import resolve as item_signature
    item=item_signature(base,name,arity,argument_types)
    if item is not None:return item
    from java_config_signatures import resolve as config_signature
    config=config_signature(base,name,arity,argument_types)
    if config is not None:return config
    from java_network_signatures import resolve as network_signature
    network=network_signature(raw,base,name,arity,argument_types,canonical_generic,generic_arguments,canonical)
    if network is not None:return network
    from java_vertex_signatures import resolve as vertex_signature
    vertex=vertex_signature(base,name,arity,argument_types)
    if vertex is not None:return vertex
    from java_gui_signatures import resolve as gui_signature
    gui=gui_signature(base,name,arity,argument_types)
    if gui is not None:return gui
    from java_entity_signatures import resolve as entity_signature
    entity=entity_signature(raw,base,name,arity,argument_types,canonical_generic,generic_arguments,canonical,proves)
    if entity is not None:return entity
    trading=trading_signature(base,name,arity,argument_types)
    if trading is not None:return trading
    if base in ('org.spongepowered.asm.mixin.injection.callback.CallbackInfo',
                'org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable'):
        record={'getId':('java.lang.String',[]),'isCancelled':('boolean',[]),
                'isCancellable':('boolean',[]),'cancel':('void',[])}.get(name)
        if base.endswith('CallbackInfoReturnable'):
            parameters=generic_arguments(raw)
            boxed=canonical(parameters[0]) if len(parameters)==1 else None
            if boxed not in ('java.lang.Integer','java.lang.Boolean'):
                raise ValueError('Return callback requires reviewed Integer/Boolean generic identity')
            primitive_getter='getReturnValueZ' if boxed=='java.lang.Boolean' else 'getReturnValueI'
            record=record or {primitive_getter:('boolean' if boxed=='java.lang.Boolean' else 'int',[]),
                             'getReturnValue':(boxed,[]),'setReturnValue':('void',[boxed])}.get(name)
        if record and len(record[1])==arity:
            return {'return_type':record[0],'parameters':record[1],
                    'receiver_kind':'game_api','mixin_abi':2 if 'Boolean' in raw else 1}
        raise ValueError('Unreviewed source callback method: '+name)
    functional={'java.util.function.Supplier':('get',1,0),
                'java.util.function.Function':('apply',2,1),
                'java.util.function.Consumer':('accept',1,1),
                'java.util.function.Predicate':('test',1,1)}
    if base in functional and name==functional[base][0]:
        method,count,parameters=functional[base]
        args=generic_arguments(raw,allow_wildcards=method=='get')
        if method=='get':
            if not args:args=['java.lang.Object'] # raw Supplier erases T to Object
            elif len(args)==1:
                arg=args[0]
                args=[arg[len('?extends'):] if arg.startswith('?extends') else 'java.lang.Object' if arg=='?' or arg.startswith('?super') else arg]
        if len(args)!=count or arity!=parameters:raise ValueError('Functional invocation requires resolved generic arguments and matching arity')
        args=[canonical_generic(item,canonical) for item in args]
        result='void' if method=='accept' else 'boolean' if method=='test' else args[-1]
        return {'return_type':result,'parameters':args[:parameters],'receiver_kind':'game_api','functional_abi':9}
    if base in ('java.util.function.BiFunction', 'java.util.function.BiConsumer'):
        args = generic_arguments(raw)
        expected = 3 if base.endswith('BiFunction') else 2
        if len(args) != expected:
            raise ValueError('Two-argument functional interface requires resolved generic arguments')
        args = [canonical_generic(item, canonical) for item in args]
        if name == ('apply' if expected == 3 else 'accept') and arity == 2:
            return {'return_type': args[-1] if expected == 3 else 'void', 'parameters': args[:2],
                    'receiver_kind': 'game_api', 'functional_abi': 5}
        raise ValueError('Two-argument functional method requires a reviewed adapter: ' + name)
    if base == 'net.minecraft.nbt.CompoundTag':
        record = {'getInt': ('int', ['java.lang.String']),
                  'putInt': ('void', ['java.lang.String', 'int'])}.get(name)
        if record and len(record[1]) == arity:
            return {'return_type': record[0], 'parameters': record[1], 'receiver_kind': 'game_api'}
    if base == 'java.lang.String':
        records = {'equals': ('boolean', ['java.lang.Object']),
                   'hashCode': ('int', []), 'length': ('int', [])}
        record = records.get(name)
        if record and len(record[1]) != arity:
            raise ValueError('Invalid String method argument count: '+name+' requires '+str(len(record[1])))
        if record:
            return {'return_type': record[0], 'parameters': record[1], 'receiver_kind': 'game_api','checked_arguments':True}
    if base == 'java.util.Collections' and name in ('emptySet', 'emptyMap') and arity == 0:
        return {'return_type': 'java.util.Set' if name == 'emptySet' else 'java.util.Map',
                'parameters': [], 'static_owner': base, 'collection_abi': 3}
    if base == 'java.util.Set' and name == 'of':
        record = {'return_type': base, 'parameters': ['java.lang.Object'] * arity,
                  'static_owner': base, 'collection_abi': 3}
        if arity == 1 and argument_types[0] and argument_types[0].endswith('[]'):
            actual = canonical_generic(argument_types[0], canonical)
            if actual.count('[]') == 1 and actual[:-2] in ('int','long','short','byte','char','boolean','float','double'):
                raise ValueError('Primitive array set elements need reviewed array identity hashing')
            record.update(parameters=[actual], call_name='ofArray')
        return record
    if base == 'java.util.Set' and name == 'copyOf' and arity == 1:
        actual = argument_types[0]
        parameters = generic_arguments(actual) if actual and actual != '<null>' else []
        result = 'java.util.Set' + ('<' + canonical_generic(parameters[0], canonical) + '>' if len(parameters) == 1 else '')
        return {'return_type': result, 'parameters': ['java.util.Collection'],
                'static_owner': base, 'collection_abi': 3}
    if base in MAPS or base == 'java.util.Map.Entry':
        parameters = generic_arguments(raw)
        if parameters and len(parameters) != 2:
            raise ValueError('Map/Entry needs two resolved generic type arguments')
        key, value = [canonical_generic(item, canonical) for item in parameters] if parameters else ['java.lang.Object'] * 2
        result_type = 'java.util.Map<' + key + ',' + value + '>'
        entry_type = 'java.util.Map.Entry<' + key + ',' + value + '>'
        if base == 'java.util.Map' and name == 'of':
            if arity > 20 or arity % 2:
                raise ValueError('Map.of requires zero to ten key/value pairs')
            return {'return_type': 'java.util.Map', 'parameters': ['java.lang.Object'] * arity,
                    'static_owner': base, 'collection_abi': 2}
        if base == 'java.util.Map' and name == 'copyOf' and arity == 1:
            actual = argument_types[0]
            result = canonical_generic(actual, canonical) if actual and actual != '<null>' else 'java.util.Map'
            return {'return_type': result, 'parameters': ['java.util.Map'],
                    'static_owner': base, 'collection_abi': 2}
        if base == 'java.util.Map.Entry':
            table = {'getKey': (key, []), 'getValue': (value, []), 'setValue': (value, [value]),
                     'equals': ('boolean', ['java.lang.Object']), 'hashCode': ('int', []), 'toString': ('java.lang.String', [])}
        else:
            table = {'size': ('int', []), 'isEmpty': ('boolean', []), 'clear': ('void', []),
                     'get': (value, ['java.lang.Object']), 'getOrDefault': (value, ['java.lang.Object', value]),
                     'put': (value, [key, value]), 'putIfAbsent': (value, [key, value]),
                     'putAll': ('void', ['java.util.Map']),
                     'containsKey': ('boolean', ['java.lang.Object']), 'containsValue': ('boolean', ['java.lang.Object']),
                     'remove': (value, ['java.lang.Object']) if arity == 1 else ('boolean', ['java.lang.Object'] * 2),
                     'keySet': ('java.util.Set<' + key + '>', []),
                     'values': ('java.util.Collection<' + value + '>', []),
                     'entrySet': ('java.util.Set<' + entry_type + '>', []),
                     'computeIfAbsent': (value, [key, 'java.util.function.Function<' + key + ',' + value + '>']),
                     'equals': ('boolean', ['java.lang.Object']), 'hashCode': ('int', []), 'toString': ('java.lang.String', [])}
        if base in MAPS:
            defaults = {
                'computeIfPresent': (value, [key, 'java.util.function.BiFunction<' + key + ',' + value + ',' + value + '>']),
                'compute': (value, [key, 'java.util.function.BiFunction<' + key + ',' + value + ',' + value + '>']),
                'merge': (value, [key, value, 'java.util.function.BiFunction<' + value + ',' + value + ',' + value + '>']),
                'replaceAll': ('void', ['java.util.function.BiFunction<' + key + ',' + value + ',' + value + '>']),
                'forEach': ('void', ['java.util.function.BiConsumer<' + key + ',' + value + '>']),
                'replace': (value, [key, value]) if arity == 2 else ('boolean', [key, value, value])}
            record = defaults.get(name)
            if record and len(record[1]) == arity:
                result = {'return_type': record[0], 'parameters': record[1], 'collection_abi': 4}
                if name != 'replace':
                    result['functional_abi'] = 5
                return result
        record = table.get(name)
        if record and len(record[1]) == arity:
            return {'return_type': record[0], 'parameters': record[1], 'collection_abi': 2}
        raise ValueError('Map method requires a reviewed adapter: ' + name)
    if base == 'java.util.Collections' and name in ('unmodifiableMap', 'unmodifiableSet') and arity == 1:
        source_type = argument_types[0]
        if source_type is None or source_type == '<null>':
            raise ValueError('Unmodifiable factory needs a resolved source type; cast null explicitly')
        resolved = canonical_generic(source_type, canonical)
        expected = MAPS if name == 'unmodifiableMap' else SETS
        if resolved.split('<', 1)[0] not in expected:
            raise ValueError('Unmodifiable factory source type is not reviewed')
        result = ('java.util.Map' if name == 'unmodifiableMap' else 'java.util.Set')
        if '<' in resolved:
            result += resolved[resolved.index('<'):]
        return {'return_type': result, 'parameters': [resolved.split('<', 1)[0]],
                'static_owner': base, 'collection_abi': 2 if name == 'unmodifiableMap' else 3}
    if base==PROFILING+'metrics.MetricCategory' and name=='getDescription' and arity==0:
        return {'return_type':'java.lang.String','parameters':[],'receiver_kind':'game_api'}
    if base in (PROFILING+'ProfilerFiller',PROFILING+'ProfileCollector',PROFILING+'InactiveProfiler'):
        table={'startTick':('void',[]),'endTick':('void',[]),'pop':('void',[]),
            'markForCharting':('void',[PROFILING+'metrics.MetricCategory'])}
        if base==PROFILING+'ProfilerFiller':table['tee']=(PROFILING+'ProfilerFiller',[PROFILING+'ProfilerFiller']*2)
        if base!=PROFILING+'ProfilerFiller':table.update({'getResults':(PROFILING+'ProfileResults',[]),
            'getEntry':(PROFILING+'ActiveProfiler.PathEntry',['java.lang.String']),
            'getChartedPaths':('java.util.Set<org.apache.commons.lang3.tuple.Pair<java.lang.String,'+PROFILING+'metrics.MetricCategory>>',[])})
        if name in ('push','popPush','incrementCounter'):
            if arity not in ((1,2) if name=='incrementCounter' else (1,)):return None
            actual=argument_types[0]
            if actual=='<null>':raise ValueError('Ambiguous profiler String/Supplier overload; cast null explicitly')
            if actual is None or actual.split('<',1)[0]=='java.util.function.Supplier':label='java.util.function.Supplier<java.lang.String>'
            elif canonical(actual)=='java.lang.String':label='java.lang.String'
            else:raise ValueError('Profiler overload requires String or Supplier<String>')
            table[name]=('void',[label]+(['int'] if arity==2 else []))
        record=table.get(name)
        if record and len(record[1])==arity:
            result={'return_type':record[0],'parameters':record[1],'receiver_kind':'profiler'}
            if name=='tee':result['static_owner']=PROFILING+'ProfilerFiller'
            return result
        raise ValueError('Profiler method requires an implemented adapter: '+name)
    if base in (PROFILING+'ProfileResults',PROFILING+'EmptyProfileResults'):
        table={'getTimes':('java.util.List<'+PROFILING+'ResultField>',['java.lang.String']),
            'saveResults':('boolean',['java.nio.file.Path']),
            'getStartTimeNano':('long',[]),'getEndTimeNano':('long',[]),
            'getStartTimeTicks':('int',[]),'getEndTimeTicks':('int',[]),
            'getTickDuration':('int',[]),'getNanoDuration':('long',[]),
            'getProfilerResults':('java.lang.String',[])}
        if base==PROFILING+'ProfileResults':table['demanglePath']=('java.lang.String',['java.lang.String'])
        record=table.get(name)
        if record and len(record[1])==arity:
            result={'return_type':record[0],'parameters':record[1],'receiver_kind':'profiler'}
            if name=='demanglePath':result['static_owner']=PROFILING+'ProfileResults'
            return result
        raise ValueError('Profile results method requires an implemented adapter: '+name)
    if base in (enum_types or {}):
        records={'name':('java.lang.String',[]),'ordinal':('int',[]),
                 'compareTo':('int',[base]),'getDeclaringClass':('java.lang.Class',[]),
                 'toString':('java.lang.String',[]),'equals':('boolean',['java.lang.Object']),'hashCode':('int',[]),'values':(base+'[]',[]),
                 'valueOf':(base,['java.lang.String'])}
        record=records.get(name)
        if record and len(record[1])==arity:
            result={'return_type':record[0],'parameters':record[1],'receiver_kind':'game_api'}
            if name in ('values','valueOf'):result['static_owner']=base
            return result
        return None
    if base=='java.util.EnumSet':
        element=canonical(raw.split('<',1)[1][:-1]) if '<' in raw and '?' not in raw and ',' not in raw else 'java.lang.Object'
        result_type=base+'<'+element+'>' if element!='java.lang.Object' else base
        factories={'noneOf':['java.lang.Class'],'allOf':['java.lang.Class'],
                   'copyOf':['java.util.Collection'],'complementOf':['java.util.EnumSet']}
        if name=='of' and arity>0:
            element=canonical(argument_types[0]) if argument_types[0] else None
            if element not in (enum_types or {}):raise ValueError('EnumSet.of requires a resolved reviewed enum type')
            params=[element]*arity
            if arity==2 and argument_types[1] and argument_types[1].endswith('[]'):params[1]=argument_types[1]
            return {'return_type':base+'<'+element+'>','parameters':params,'static_owner':base}
        if name=='range' and arity==2:
            element=canonical(argument_types[0]) if argument_types[0] else None
            if element not in (enum_types or {}):raise ValueError('EnumSet.range requires a resolved reviewed enum type')
            return {'return_type':base+'<'+element+'>','parameters':[element,element],'static_owner':base}
        if name in factories and arity==1:
            actual=argument_types[0] or ''
            generic=canonical(actual.split('<',1)[1][:-1]) if '<' in actual and '?' not in actual and ',' not in actual else None
            result=base+'<'+generic+'>' if generic in (enum_types or {}) else base
            return {'return_type':result,'parameters':factories[name],'static_owner':base}
        records={'size':('int',[]),'isEmpty':('boolean',[]),'clear':('void',[]),
                 'add':('boolean',[element]),'contains':('boolean',['java.lang.Object']),
                 'remove':('boolean',['java.lang.Object']),'clone':(result_type,[]),
                 'addAll':('boolean',['java.util.Collection']),'containsAll':('boolean',['java.util.Collection']),
                 'removeAll':('boolean',['java.util.Collection']),'retainAll':('boolean',['java.util.Collection']),
                 'iterator':('java.util.Iterator<'+element+'>',[]),'toString':('java.lang.String',[]),
                 'equals':('boolean',['java.lang.Object']),'hashCode':('int',[])}
        if name=='forEach' and arity==1:return {'return_type':'void','parameters':['java.util.function.Consumer<'+element+'>']}
        if name=='removeIf' and arity==1:return {'return_type':'boolean','parameters':['java.util.function.Predicate<'+element+'>']}
        if name=='toArray':
            if arity==0:return {'return_type':'java.lang.Object[]','parameters':[]}
            if arity==1 and argument_types[0] and argument_types[0].endswith('[]'):
                return {'return_type':argument_types[0],'parameters':[argument_types[0]]}
        record=records.get(name)
        if record and len(record[1])==arity:return {'return_type':record[0],'parameters':record[1]}
        raise ValueError('EnumSet method requires an implemented adapter: '+name)
    if base=='net.minecraft.world.item.ItemStack':
        # Official 1.21.1 mappings and cuq javap: item_stack_copy_reference.json.
        if name in ('matches','isSameItem','isSameItemSameComponents','listMatches'):
            if arity!=2:raise ValueError('Static ItemStack.'+name+' requires two arguments')
            parameter='java.util.List<'+base+'>' if name=='listMatches' else base
            return {'return_type':'boolean','parameters':[parameter,parameter],'receiver_kind':'game_api','static_owner':base}
        if name=='is':
            if arity!=1 or not argument_types[0] or canonical(argument_types[0])!='net.minecraft.world.item.Item':
                raise ValueError('ItemStack.is overload requires reviewed Item type; other overloads need adapters')
            return {'return_type':'boolean','parameters':['net.minecraft.world.item.Item'],'receiver_kind':'game_api'}
        table={'isEmpty':('boolean',[]),'getItem':('net.minecraft.world.item.Item',[]),
               'getCount':('int',[]),'setCount':('void',['int']),
               'getMaxStackSize':('int',[]),'grow':('void',['int']),'shrink':('void',['int']),
               'split':(base,['int']),'copy':(base,[]),'copyWithCount':(base,['int']),
               'equals':('boolean',['java.lang.Object']),'hashCode':('int',[])}
        record=table.get(name)
        if record and len(record[1])==arity:return {'return_type':record[0],'parameters':record[1],'receiver_kind':'game_api'}
        return None
    if base=='net.minecraft.world.entity.ai.goal.Goal':
        if name in ('canUse','canContinueToUse','isInterruptable','requiresUpdateEveryTick') and arity==0:
            return {'return_type':'boolean','parameters':[],'receiver_kind':'game_api'}
        if name in ('start','stop','tick') and arity==0:
            return {'return_type':'void','parameters':[],'receiver_kind':'game_api'}
        return None
    goal='net.minecraft.world.entity.ai.goal.Goal'
    wrapped='net.minecraft.world.entity.ai.goal.WrappedGoal'
    selector='net.minecraft.world.entity.ai.goal.GoalSelector'
    if base in (selector,wrapped):
        if base==selector:
            table={'addGoal':('void',['int',goal]),'removeGoal':('void',[goal]),
                'removeAllGoals':('void',['java.util.function.Predicate<'+goal+'>']),
                'tick':('void',[]),'tickRunningGoals':('void',['boolean']),
                'getAvailableGoals':('java.util.Set<'+wrapped+'>',[]),
                'disableControlFlag':('void',[goal+'.Flag']),
                'enableControlFlag':('void',[goal+'.Flag']),
                'setControlFlag':('void',[goal+'.Flag','boolean'])}
        else:
            table={'getGoal':(goal,[]),'getPriority':('int',[]),'isRunning':('boolean',[]),
                'canBeReplacedBy':('boolean',[wrapped]),'canUse':('boolean',[]),
                'canContinueToUse':('boolean',[]),'isInterruptable':('boolean',[]),
                'requiresUpdateEveryTick':('boolean',[]),'start':('void',[]),'stop':('void',[]),
                'tick':('void',[]),'setFlags':('void',['java.util.EnumSet']),
                'getFlags':('java.util.EnumSet<'+goal+'.Flag>',[]),
                'equals':('boolean',['java.lang.Object']),'hashCode':('int',[])}
        record=table.get(name)
        if record and len(record[1])==arity:
            return {'return_type':record[0],'parameters':record[1],'receiver_kind':'goal_scheduler'}
        raise ValueError('Goal scheduler method requires an implemented public adapter: '+name)
    if base in SETS or base == 'java.util.Collection':
        abi = 3 if base in SETS else 1
        generic = generic_arguments(raw)
        if len(generic) > 1:
            raise ValueError('Collection needs one resolved generic type argument')
        element = canonical_generic(generic[0], canonical) if generic else 'java.lang.Object'
        table={'size':('int',[]),'isEmpty':('boolean',[]),'contains':('boolean',['java.lang.Object']),
               'add':('boolean',[element]),'remove':('boolean',['java.lang.Object']),'clear':('void',[]),
               'iterator':('java.util.Iterator<'+element+'>',[]),
               'equals':('boolean',['java.lang.Object']),'hashCode':('int',[]),'toString':('java.lang.String',[])}
        if name in ('addAll', 'removeAll', 'retainAll', 'containsAll') and arity == 1:
            return {'return_type': 'boolean', 'parameters': ['java.util.Collection'], 'collection_abi': 3 if base in SETS else 2}
        if name == 'removeIf' and arity == 1:
            return {'return_type': 'boolean', 'parameters': ['java.util.function.Predicate<' + element + '>'], 'collection_abi': 3 if base in SETS else 2}
        if name == 'forEach' and arity == 1 and base in SETS:
            return {'return_type': 'void', 'parameters': ['java.util.function.Consumer<' + element + '>'], 'collection_abi': abi}
        if name=='toArray':
            if arity==0:return {'return_type':'java.lang.Object[]','parameters':[], 'collection_abi': abi}
            if arity==1 and argument_types[0] and argument_types[0].endswith('[]'):return {'return_type':argument_types[0],'parameters':[argument_types[0]], 'collection_abi': abi}
        record=table.get(name)
        if record and len(record[1])==arity:return {'return_type':record[0],'parameters':record[1], 'collection_abi': abi}
        raise ValueError('Collection method requires a reviewed adapter: '+name)
    if base in ('net.minecraft.world.inventory.AbstractContainerMenu','net.minecraft.world.inventory.RecipeBookMenu'):
        stack='net.minecraft.world.item.ItemStack'
        table={'getStateId':('int',[]),'incrementStateId':('int',[]),'isValidSlotIndex':('boolean',['int']),
               'getSlot':('net.minecraft.world.inventory.Slot',['int']),
               'getItems':('net.minecraft.core.NonNullList<'+stack+'>',[]),
               'getCarried':(stack,[]),'setCarried':('void',[stack]),
               'setItem':('void',['int','int',stack]),
               'initializeContents':('void',['int','java.util.List<'+stack+'>',stack]),
               'setRemoteSlot':('void',['int',stack]),'setRemoteSlotNoCopy':('void',['int',stack]),
               'setRemoteCarried':('void',[stack]),
               'sendAllDataToRemote':('void',[]),'broadcastChanges':('void',[]),'broadcastFullState':('void',[]),
               'suppressRemoteUpdates':('void',[]),'resumeRemoteUpdates':('void',[])}
        record=table.get(name)
        if record and len(record[1])==arity:return {'return_type':record[0],'parameters':record[1],'receiver_kind':'game_api'}
        return None
    if base=='net.minecraft.world.inventory.DataSlot':
        table={'get':('int',[]),'set':('void',['int']),'checkAndClearUpdateFlag':('boolean',[]),
               'standalone':(base,[]),'shared':(base,['int[]','int']),
               'forContainer':(base,['net.minecraft.world.inventory.ContainerData','int'])}
        record=table.get(name)
        if record and len(record[1])==arity:
            result={'return_type':record[0],'parameters':record[1],'receiver_kind':'game_api'}
            if name in ('standalone','shared','forContainer'):result['static_owner']=base
            return result
        return None
    if base=='net.minecraft.core.NonNullList':
        element='java.lang.Object'
        if '<' in raw:
            generic=raw.split('<',1)[1][:-1]
            if '?' in generic or ',' in generic:return None
            element=canonical(generic)
        table={'size':('int',[]),'isEmpty':('boolean',[]),'get':(element,['int']),
               'set':(element,['int',element]),'clear':('void',[])}
        record=table.get(name)
        if record and len(record[1])==arity:return {'return_type':record[0],'parameters':record[1],'receiver_kind':'game_api'}
        return None
    if base in ('java.io.ByteArrayOutputStream','java.io.ByteArrayInputStream'):
        table={'close':('void',[])}
        if base=='java.io.ByteArrayOutputStream':
            table.update({'size':('int',[]),'toByteArray':('byte[]',[]),'reset':('void',[]),'flush':('void',[])})
            if name=='write':table[name]=('void',['int'] if arity==1 and argument_types[0]=='int' else ['byte[]'] if arity==1 else ['byte[]','int','int'])
        else:
            table.update({'available':('int',[]),'mark':('void',['int']),'reset':('void',[]),'markSupported':('boolean',[])})
            if name=='read':table[name]=('int',[] if arity==0 else ['byte[]'] if arity==1 else ['byte[]','int','int'])
        record=table.get(name)
        if record and len(record[1])==arity:return {'return_type':record[0],'parameters':record[1],'receiver_kind':'memory_stream'}
        return None
    throwables={'java.lang.Throwable','java.lang.Exception','java.lang.Error','java.lang.RuntimeException','java.lang.IllegalArgumentException','java.lang.IllegalStateException','java.lang.NullPointerException','java.lang.AssertionError'}
    from java_exception_signatures import CONSTRUCTORS
    throwables.update(CONSTRUCTORS)
    if base in throwables:
        records={'getMessage':('java.lang.String',[]),'getLocalizedMessage':('java.lang.String',[]),'toString':('java.lang.String',[]),'getCause':('java.lang.Throwable',[]),'initCause':('java.lang.Throwable',['java.lang.Throwable'])}
        record=records.get(name)
        if record and len(record[1])==arity:return {'return_type':record[0],'parameters':record[1],'receiver_kind':'throwable','throwable_api':True}
        if name=='getSuppressed' and arity==0:return {'return_type':'java.lang.Throwable[]','parameters':[],'receiver_kind':'throwable'}
        if name=='addSuppressed' and arity==1:return {'return_type':'void','parameters':['java.lang.Throwable'],'receiver_kind':'throwable'}
        return None
    if base not in LISTS|ITERATORS:return None
    element='java.lang.Object'
    if '<' in raw:
        parameters = generic_arguments(raw)
        if len(parameters) != 1:return None
        element=canonical_generic(parameters[0], canonical)
    if base in ITERATORS:
        if name=='forEachRemaining' and arity==1:return {'return_type':'void','parameters':['java.util.function.Consumer<'+element+'>']}
        table={'hasNext':('boolean',[]),'next':(element,[]),'remove':('void',[])}
        if base=='java.util.ListIterator':table.update({'hasPrevious':('boolean',[]),'previous':(element,[]),'nextIndex':('int',[]),'previousIndex':('int',[]),'set':('void',[element]),'add':('void',[element])})
    else:
        table={'size':('int',[]),'isEmpty':('boolean',[]),'get':(element,['int']),'set':(element,['int',element]),'clear':('void',[]),'contains':('boolean',['java.lang.Object']),'indexOf':('int',['java.lang.Object']),'lastIndexOf':('int',['java.lang.Object']),'iterator':('java.util.Iterator<'+element+'>',[]),'subList':('java.util.List<'+element+'>',['int','int'])}
        if name=='add':table[name]=('boolean',[element]) if arity==1 else ('void',['int',element])
        if name=='remove' and arity==1:
            if not argument_types or argument_types[0] is None:raise ValueError('List.remove argument compile-time type is unresolved')
            by_index=argument_types[0]=='int'
            return {'return_type':element if by_index else 'boolean','parameters':['int' if by_index else 'java.lang.Object'],'remove_mode':'index' if by_index else 'object'}
        if name=='listIterator':table[name]=('java.util.ListIterator<'+element+'>',[] if arity==0 else ['int'])
        if name=='toArray':
            if arity==0:return {'return_type':'java.lang.Object[]','parameters':[]}
            if arity==1 and argument_types[0] and argument_types[0].endswith('[]'):return {'return_type':argument_types[0],'parameters':[argument_types[0]]}
    record=table.get(name)
    if record and len(record[1])==arity:return {'return_type':record[0],'parameters':record[1]}
    return None
