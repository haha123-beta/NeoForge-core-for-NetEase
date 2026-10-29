"""Data-only adapter for the existing HTTP conversion pipeline, not a second packer."""
import hashlib,html,json,zipfile
from pathlib import Path
from recipe_data094 import convert_tree,load_profile
from build_distribution import build_data

def validate_source(source,info):
    """Fail closed before the data lane; never reinterpret a legacy pack."""
    source=Path(source)
    if info.get('platform')!='NeoForge':
        raise ValueError('Data source loader unverified: expected explicit NeoForge metadata')
    if any(source.rglob('*.class')) or any(source.rglob('*.java')):
        raise ValueError('Data-only routing must not skip Java business code')
    meta=source/'pack.mcmeta'
    try:
        metadata=json.loads(meta.read_bytes())
    except (OSError,ValueError) as error:
        raise ValueError('Data source pack.mcmeta missing or invalid') from error
    if not isinstance(metadata,dict) or not isinstance(metadata.get('pack'),dict):
        raise ValueError('Data source pack.mcmeta must contain a pack object')
    pack=metadata['pack']
    if type(pack.get('pack_format')) is not int or pack['pack_format']!=48:
        raise ValueError('Data-only source version unverified: expected 1.21/1.21.1 format 48; found '+str(pack.get('pack_format')))
    if set(metadata)-{'pack'} or set(pack)-{'pack_format','description'}:
        raise ValueError('Data source metadata requires review: filters/overlays/features or extended pack rules are not supported')
    if any(source.rglob('*mixins*.json')) or any(source.rglob('accesstransformer.cfg')):
        raise ValueError('Data-only route cannot silently discard Mixin/AT requirements')

def run(source,work,output,info,archive_distribution,progress):
    source,work,output=Path(source),Path(work),Path(output)
    validate_source(source,info)
    progress('data_conversion','按 1.21.1 路径、物品目录和标签转换真实数据')
    converted=convert_tree(source,load_profile());report=converted['report']
    gaps=[]
    for p in (source/'data').rglob('*'):
        if not p.is_file():continue
        parts=p.relative_to(source).parts
        if len(parts)>=4 and parts[2] in ('recipe','recipes'):continue
        # Recipe expansion does not install Java tags into the native runtime.
        gaps.append(p.relative_to(source).as_posix())
    for p in (source/'assets').rglob('*'):
        if p.is_file():gaps.append(p.relative_to(source).as_posix())
    report['unconverted_non_recipe_content']=gaps
    report['unresolved_required_dependencies']=[row for row in info.get('dependencies',[])
        if row.get('modId') not in ('minecraft','neoforge') and str(row.get('type','required')).lower()=='required']
    partial=bool(gaps) or bool(report['unresolved_required_dependencies']) or any(row['status'] not in ('CONVERTED_REVIEW_REQUIRED','VERSION_NOT_APPLICABLE') for row in report['rows'])
    report['partial']=partial
    (work/'data_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['<!doctype html><meta charset="utf-8"><title>NeoCore data conversion</title>',
           '<h1>Data-only review report; engine verification pending</h1>',
           '<p>Partial: '+str(partial)+'; '+html.escape(json.dumps(report['status_counts']))+'</p>',
           '<table><tr><th>Source</th><th>Status</th><th>Reason</th></tr>']
    for row in report['rows']:
        lines.append('<tr>'+''.join('<td>'+html.escape(str(row.get(key,'')))+'</td>' for key in ('source','status','reason'))+'</tr>')
    lines.append('</table>')
    (work/'data_ir_report.html').write_text('\n'.join(lines),encoding='utf-8')
    result=dict(source_mode='DATA_ONLY',data_only=True,java_translation_applicable=False,
        translation=dict(files=0,generated_for_review=0,manual_review=0,failed=0,engine_verified=False,python2_executed=False,ready_mods=0),
        data_conversion={key:report[key] for key in ('input_recipes','active_recipes','status_counts','output_files','partial')},
        data_report=str(work/'data_report.json'),engine_verified=False,python2_executed=False,translated=False,
        pipeline=dict(inspection='COMPLETE',source_preparation='DATA_ONLY',conversion='DATA_CONVERTED_FOR_REVIEW',engine_verified=False),
        diagnostics=[dict(file=row['source'],category=row['status'],reason=row.get('reason')) for row in report['rows'] if row['status'] not in ('CONVERTED_REVIEW_REQUIRED','VERSION_NOT_APPLICABLE')],stage='complete')
    if not converted['files']:
        return dict(result,status='CONTENT_STAGED_REVIEW_REQUIRED',message='没有可证明等效的目标配方；完整诊断可下载，未生成空行为包')
    distribution=work/'data_distribution'
    layout=build_data(distribution,info['mods'][0]['id'],converted['files'],report,partial)
    progress('archive','生成明确标记范围的独立数据行为包')
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix('.partial')
    archive_distribution(distribution,temporary,layout)
    # Use the existing checked archive writer, then attach explicit scope evidence.
    with zipfile.ZipFile(temporary,'a') as z:
        z.writestr('数据转换范围.json',json.dumps({key:report[key] for key in ('input_recipes','active_recipes','status_counts','partial')},ensure_ascii=False).encode('utf-8'))
    with zipfile.ZipFile(temporary) as z:
        if z.testzip():raise ValueError('Data artifact failed ZIP integrity check')
        if any(n.endswith(('.py','.class','.jar')) for n in z.namelist()):raise ValueError('Pure data candidate contains code')
    temporary.replace(output)
    return dict(result,status='TRANSLATION_INCOMPLETE' if partial else 'PACKAGED_REVIEW_REQUIRED',
        artifact_kind='NETEASE_DATA_SUBSET_ZIP' if partial else 'NETEASE_DATA_ZIP',output=output.name,
        output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        tree='实验性部分配方行为包；不是原模组完整兼容' if partial else '独立数据行为包；网易实机待验证',
        message='部分数据实验包已生成；未支持/缺依赖配方完整保留在报告中，不能称整包兼容' if partial else '数据配方候选已生成；Java 转译不适用，网易实机待验证')
