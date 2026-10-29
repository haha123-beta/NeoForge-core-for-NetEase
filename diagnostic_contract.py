"""Structured evidence, never classification by matching human error messages."""
import hashlib
from collections import Counter

# Codes identify the emitting contract. Unknown emitters remain visibly unknown.
CONTRACTS = {
    'EXTERNAL_ABI_REQUIRED': ('NC-API-001', 'official_api', 'API 签名与符号解析', '官方或标准库类型的受审查合同缺失；不证明已有运行行为'),
    'UNRESOLVED_EXTERNAL': ('NC-DEP-001', 'third_party_dependency', '外部依赖', '外部符号未解析，须核对真实依赖及其实现'),
    'TRANSLATED_DEPENDENCY_SYMBOL': ('NC-LINK-001', 'type_linking', 'API 签名与符号解析', '已转换依赖符号的所有权或链接条件未满足'),
    'REVIEWED_API_CONTRACT_MISSING': ('NC-API-002', 'official_api', 'API 签名与符号解析', '当前调用没有受审查合同；不能据此认定运行时不存在实现'),
    'api_call_contract': ('NC-API-003', 'official_api', 'API 签名与符号解析', '调用签名、参数类型或泛型约束未被当前合同接受'),
    'source_lowering': ('NC-JAVA-001', 'java_semantics', 'Java 前端/编译器', '源语言结构需要语义降级，当前转换器拒绝生成'),
    'unicode_prelexing': ('NC-JAVA-002', 'java_syntax', 'Java 前端/编译器', 'Java Unicode 预处理及源码位置映射尚未完成'),
    'parse_error': ('NC-JAVA-003', 'java_syntax', 'Java 前端/编译器', '解析器未接受当前源码；须查看反编译来源和解析位置'),
    'syntax': ('NC-JAVA-003', 'java_syntax', 'Java 前端/编译器', '解析器未接受当前源码；须查看反编译来源和解析位置'),
    'mixin_plan': ('NC-JVM-001', 'mixin_jvm', '运行时与网易平台适配', 'Mixin 计划缺少可审查的目标或适配位置'),
    'thread_or_native': ('NC-JVM-002', 'mixin_jvm', 'Java 前端/运行时', '线程或 native 语义尚未适配'),
    'ambiguous_project_type': ('NC-LINK-002', 'type_linking', 'API 签名与符号解析', '项目类型身份有冲突或歧义'),
    'generic_superclass': ('NC-JAVA-004', 'type_linking', 'Java 类型与继承', '父类泛型替换尚未完成；父类依赖行为须另行核查'),
    'annotation': ('NC-JAVA-005', 'java_semantics', 'Java 前端/编译器', '注解的语义尚未获得受审查适配'),
}

def file_diagnostic(row):
    details = row.get('details') or {}
    category = details.get('category')
    blocked = row.get('status') in ('MANUAL_REVIEW', 'FAILED')
    code, family, layer, explanation = CONTRACTS.get(category, (
        'NC-UNKNOWN-001', 'unknown', '暂时无法归因', '当前发出点没有结构化原因合同，保留原始错误供调查'))
    owner = details.get('owner') or details.get('symbol') or details.get('resolved_name')
    if category == 'EXTERNAL_ABI_REQUIRED' and owner and not owner.startswith((
            'java.', 'javax.', 'net.minecraft.', 'net.neoforged.', 'com.mojang.', 'org.spongepowered.asm.')):
        code,family,layer,explanation=CONTRACTS['UNRESOLVED_EXTERNAL']
    if category == 'annotation' and (owner or '').startswith('org.spongepowered.asm.'):
        code,family,layer,explanation=CONTRACTS['mixin_plan']
    method = details.get('method') or details.get('name')
    # Argument source types are not JVM descriptors. Never invent an overload.
    descriptor = details.get('descriptor')
    key = '|'.join(str(v or '') for v in (code, owner, method, descriptor))
    if not owner and not method:key += '|'+str(category or row.get('reason', ''))
    return dict(schema_version=1, file=row.get('file'), status=row.get('status'),
        first_blocker=(dict(code=code, category=family, emitter_category=category,
            explanation=explanation, reason=row.get('reason'), repair_layer=layer,
            line=row.get('line'), origin=details.get('diagnostic_origin'),
            java=dict(owner=owner, name=method, descriptor=descriptor,
                argument_types=details.get('argument_types')),
            evidence='OBSERVED_TRANSLATION_BLOCKER',
            attribution='EMITTER_CLASSIFIED' if category in CONTRACTS else 'UNKNOWN',
            shared_key=hashlib.sha256(key.encode('utf-8')).hexdigest()[:24]) if blocked else None),
        additional_requirements=row.get('additional_requirements', []),
        missing_generated_dependencies=row.get('missing_generated_dependencies', []),
        unprobed_boundary='首阻断之后的编译路径、完整 Python2 执行与网易行为尚未由本文件结果证明')

def summarize(source_reports):
    files = [file_diagnostic(row) for report in source_reports for row in report.get('results', [])]
    counts = Counter(f['first_blocker']['category'] for f in files if f['first_blocker'])
    groups = {}
    for f in files:
        b = f['first_blocker']
        if b:
            group=groups.setdefault(b['shared_key'],dict(blocker=b, affected_files=[]))
            group['affected_files'].append(f['file'])
    return dict(schema_version=1, files=files, category_counts=dict(counts),
        shared_blockers=list(groups.values()),
        evidence_note='清除首诊断不等于新增可生成文件；静态需求不等于已发生的编译错误')
