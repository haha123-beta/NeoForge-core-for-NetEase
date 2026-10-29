"""Semantic capability identities. Human prose is retained as evidence, not a key."""
import hashlib

OFFICIAL=('java.','javax.','net.minecraft.','net.neoforged.','net.minecraftforge.',
          'com.mojang.','com.google.common.','org.joml.','org.slf4j.','org.apache.logging.')
POLICIES={
 'java.generic_superclass_substitution':('泛型父类替换','C',3.0,12),
 'java.superclass_layout':('父类布局与种类降级','C',3.0,12),
 'java.functional_target_resolution':('函数式目标接口解析','C',3.0,12),
 'java.nested_record':('嵌套或局部 record 降级','C',2.0,12),
 'java.simple_record':('简单 record 降级','B',2.0,5),
 'java.generic_record':('泛型 record 类型替换','C',2.0,12),
 'jvm.mixin':('Mixin 注入语义','C',2.0,40),
 'jvm.reflection':('反射与动态调用','C',2.0,30),
 'jvm.concurrency':('线程与并发语义','C',2.0,24),
 'minecraft.renderer_hierarchy':('渲染器继承与客户端图形','C',1.0,30),
 'minecraft.network_codec':('网络编解码与协议','C',2.0,24),
 'platform.loader':('目标加载器合同','C',2.0,20),
 'platform.version':('目标版本合同','C',2.0,20),
 'dependency.missing':('第三方依赖解析','C',1.0,8),
 'metadata.annotation':('注解元数据','B',1.0,5),
 'java.unicode_prelexing':('Unicode 预处理与源码位置映射','C',3.0,8),
 'java.parse_error':('Java 语法解析','C',3.0,12),
 'java.ambiguous_project_type':('项目类型身份解析','C',3.0,10),
}
# Exact legacy emitter contracts, explicitly labelled rather than fuzzy matching.
LEGACY={
 'Nested/local records require owner and capture lowering':'java.nested_record',
 'Generic record declaration requires type substitution':'java.generic_record',
 'Superclass layout/kind requires lowering':'java.superclass_layout',
 'Functional target interface unresolved':'java.functional_target_resolution',
}
def canonical(s):return (s or '').replace('$','.')

def feature_for_owner(owner):
    if owner.startswith('org.spongepowered.asm.'):return 'jvm.mixin'
    if owner.startswith(('java.lang.reflect.','java.lang.invoke.')):return 'jvm.reflection'
    if owner.startswith(('java.util.concurrent.','java.lang.Thread')):return 'jvm.concurrency'
    if owner.startswith(('net.minecraft.client.renderer.','net.minecraft.client.model.')):return 'minecraft.renderer_hierarchy'
    if owner.startswith(('net.minecraft.network.codec.','net.neoforged.neoforge.network.')):return 'minecraft.network_codec'
    return None

def identify(row):
    """One stable semantic node, retaining overloads and emitter provenance."""
    d=row.get('details') or {};owner=canonical(d.get('owner') or d.get('symbol') or d.get('resolved_name'))
    method=d.get('method') or d.get('name');category=d.get('category')
    feature=d.get('capability') or row.get('capability')
    attribution='STRUCTURED'
    if not feature:feature={'unicode_prelexing':'java.unicode_prelexing','parse_error':'java.parse_error','syntax':'java.parse_error','ambiguous_project_type':'java.ambiguous_project_type','thread_or_native':'jvm.concurrency'}.get(category)
    if not feature and category=='generic_superclass':feature='java.generic_superclass_substitution'
    if not feature and row.get('reason') in LEGACY:
        feature=LEGACY[row['reason']];attribution='EXACT_LEGACY_EMITTER_CONTRACT'
    if not feature:
        for prefix,known in LEGACY.items():
            if row.get('reason','').startswith(prefix+':'):
                feature=known;attribution='LEGACY_EMITTER_PREFIX_CONTRACT';break
    if not feature and (category=='mixin_plan' or owner.startswith('org.spongepowered.asm.')):feature='jvm.mixin'
    if not feature and category=='annotation':feature='metadata.annotation'
    if feature:
        key=feature
    elif owner and method:
        feature=feature_for_owner(owner)
        key=feature or 'api.member:'+owner+'#'+method
    elif owner:
        feature=feature_for_owner(owner)
        key=feature or ('api.type:' if owner.startswith(OFFICIAL) else 'dependency.type:')+owner
    else:
        # Do not collapse all opaque "lowering" messages into a fake capability.
        evidence=(category or 'unknown')+'|'+(d.get('node_kind') or '')+'|'+row.get('reason','')
        key='unclassified:'+hashlib.sha256(evidence.encode('utf-8')).hexdigest()[:20]
        attribution='UNCLASSIFIED_REQUIRES_TRIAGE'
    policy=POLICIES.get(feature)
    if policy:title,tier,weight,cost=policy
    elif key.startswith('dependency.type:'):title,tier,weight,cost=owner,'C',1.0,8
    elif key.startswith('api.member:'):title,tier,weight,cost=owner+'#'+method,'C',2.0,8
    elif key.startswith('api.type:'):title,tier,weight,cost=owner,'C',2.0,8
    else:title,tier,weight,cost='未归因能力（保留原证据）','C',1.0,16
    if owner=='java.util.Optional' and method=='ofNullable':
        title,tier,weight,cost='Optional#ofNullable（受审查引用参数子集）','A',3.0,1
    elif owner.startswith('net.neoforged.neoforge.registries.DeferredRegister') or owner=='net.minecraft.world.item.CreativeModeTab':
        tier,cost='B',5
    return dict(key=key,title=title,tier=tier,foundation_weight=weight,complexity=cost,
                attribution=attribution,owner=owner,method=method,
                descriptor=d.get('descriptor'),feature=feature)

def aggregate(findings,mods,weights=None):
    groups={};weights=weights or {}
    for row in findings:
        cap=identify(row);key=cap['key']
        g=groups.setdefault(key,dict(cap,occurrences=[],_files=set(),_mods=set(),_observed=set(),_suspect=set(),_historical=set(),_artifacts=set(),descriptors=set()))
        logical=row['logical_mod']
        if row['evidence']!='HISTORICAL_BLOCKER':
            g['_files'].add((row['artifact_sha256'],row['file']))
            g['_mods'].add(logical);g['_artifacts'].add(row['artifact_sha256'])
        bucket='_observed' if row['evidence']=='OBSERVED_BLOCKER' else '_historical' if row['evidence']=='HISTORICAL_BLOCKER' else '_suspect'
        g[bucket].add(logical)
        if cap['descriptor']:g['descriptors'].add(cap['descriptor'])
        g['occurrences'].append(row)
    for g in groups.values():
        g['affected_mods']=len(g.pop('_mods'));g['affected_files']=len(g.pop('_files'))
        g['affected_artifacts']=len(g.pop('_artifacts'));g['observed_blocked_mods']=len(g.pop('_observed'))
        g['static_suspect_mods']=len(g.pop('_suspect'));g['descriptors']=sorted(g['descriptors'])
        g['historical_blocked_mods']=len(g.pop('_historical'))
        config=weights.get(g['key'],{})
        for field in ('foundation_weight','complexity'):
            if field in config:
                value=float(config[field])
                if not 0<value<=1000:raise ValueError('Invalid positive bounded scoring weight')
                g[field]=value
        # Files are unique logical-mod/source pairs, so version duplicates cannot
        # inflate the average. Recompute below using logical IDs, not artifacts.
        logical_files={(r['logical_mod'],r['file']) for r in g['occurrences'] if r['evidence']!='HISTORICAL_BLOCKER'}
        g['affected_logical_files']=len(logical_files)
        g['average_blocked_files']=len(logical_files)/g['affected_mods'] if g['affected_mods'] else 0
        g['priority']=round(g['affected_mods']*g['average_blocked_files']*g['foundation_weight']/g['complexity'],4)
        g['potential_help_mods']=g['affected_mods']
        g['proven_unlocked_mods']=0
        if g['key']=='api.member:java.util.Optional#ofNullable':
            exact='(Ljava/lang/Object;)Ljava/util/Optional;'
            if g['descriptors'] and g['descriptors']!=[exact]:g['tier']='C'
        g['occurrences'].sort(key=lambda r:(r['logical_mod'],r['file'],r.get('line') or 0,r['evidence']))
    return sorted(groups.values(),key=lambda g:(-g['priority'],-g['observed_blocked_mods'],g['key']))
