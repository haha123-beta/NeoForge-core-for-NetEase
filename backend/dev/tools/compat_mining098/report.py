"""Human-readable ranking and bounded, reviewable task bundles."""
from pathlib import Path
import html,json,zipfile
from .engine import save,stable,DEV

FIXES={
 'java.generic_superclass_substitution':'沿父类链绑定声明类型参数与实参，并在继承成员签名上执行替换；验证多层继承、原始类型、边界与错误实参，保持运行类身份。',
 'java.superclass_layout':'确定父类实例布局、构造顺序与虚分派合同，再降级继承；不得通过删除父类或跳过构造来放行。',
 'java.functional_target_resolution':'从目标函数式接口取得唯一抽象方法及泛型实例化签名，再验证 lambda/方法引用的参数、返回值与捕获；歧义继续阻断。',
 'java.nested_record':'区分静态成员 record 与局部 record 的真实 owner、类型参数和捕获合同；按实际捕获布局降级，验证构造、访问器、equals/hashCode 与作用域。',
 'jvm.mixin':'提取目标类、方法描述符、注入位置及取消/返回修改合同；只为存在受审查网易等价位置的模式构建桥，无法等价的模式保持阻断。',
 'minecraft.renderer_hierarchy':'核对客户端渲染器父类、模型和图层合同，确定网易图形能力边界；不能仅靠 API 名称映射假定画面行为等价。',
 'minecraft.network_codec':'核对两端编码格式、数据类型、包方向、线程与版本；用固定字节序列和双端往返对照验证，未知协议继续阻断。',
 'java.unicode_prelexing':'按 Java 预词法 Unicode escape 规则处理 eligible backslash 与重复 u，并保留反编译源码位置映射；验证字符串、注释、非法转义与换行。',
}

def write_outputs(out,run):
    out=Path(out)
    tests={p.relative_to(DEV).as_posix():p.read_text(encoding='utf-8-sig',errors='replace') for p in (DEV/'tests').glob('test_*.py')}
    inputs={a['sha256']:{k:a[k] for k in ('sha256','path','aliases','metadata')} for a in run['artifacts'] if a.get('metadata')}
    (out/'tasks').mkdir(exist_ok=True)
    streams={tier:(out/'tasks'/(tier+'.jsonl')).open('wb') for tier in ('A','B','C')}
    task_index=[];expanded={tier:0 for tier in streams}
    for number,g in enumerate(run['groups']):
        chosen=[];seen=set()
        for row in g['occurrences']:
            pair=(row['logical_mod'],row['file'])
            if pair not in seen:chosen.append(row);seen.add(pair)
            if len(chosen)==5:break
        tokens=[x for x in ((g.get('owner') or '').rsplit('.',1)[-1],g.get('method')) if x and len(x)>3]
        if g.get('feature'):tokens.append(g['feature'].rsplit('.',1)[-1])
        matches=[name for name,text in tests.items() if any(token in text for token in tokens)][:12]
        task=dict(schema_version=1,capability=g['key'],title=g['title'],tier=g['tier'],
            affected_mods=g['affected_mods'],affected_files=g['affected_logical_files'],priority=g['priority'],
            score_inputs={k:g[k] for k in ('affected_mods','average_blocked_files','foundation_weight','complexity')},
            expected_generalized_fix=FIXES.get(g['key'],'补齐该语义能力的类型、调用和运行行为合同，保留未审查重载的阻断；不得按模组或文件名特判。'),
            representatives=chosen,overloads=g['descriptors'],existing_test_candidates=matches,
            artifact_inputs=[inputs[h] for h in sorted({r['artifact_sha256'] for r in chosen})],
            test_discovery='LEXICAL_CANDIDATES_NOT_EXECUTED_BY_MINER',
            required_validation=['固定版本 Java 对照','真实 Python 2/3','原件重新转换','MiniCoal/first block 回归','修改相关全量检查'],
            regression_risk=['类型/重载误放行','异常与副作用改变','首阻断消失但暴露后续阻断','静态引用不等于动态执行'],
            evidence_sources=sorted({r['evidence'] for r in g['occurrences']}),
            auto_apply=False,engine_verified=False,source_profile=run['profile_sha256'])
        if g['tier']=='B':
            task['lowering_template']=dict(status='REQUIRES_SEMANTIC_REVIEW',
                input_slots=['owner','method','descriptor','generic_arguments','registration_or_constructor_context'],
                steps=['用代表案例提取注册或 record 的输入输出合同','核对生命周期、身份、异常和副作用','仅为满足合同的模式生成候选 lowering','逐项运行 Java/Python2/Python3 对照，再重新转换原件'],
                reject_conditions=['未知重载','隐式捕获或泛型替换未求解','客户端与服务端语义混用'],
                candidate_is_executable=False)
        stem=stable(g['key'])[:20];folder=out/'tasks'/g['tier']
        stream=streams[g['tier']];raw=(json.dumps(task,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
        task_index.append(dict(capability=g['key'],tier=g['tier'],file=g['tier']+'.jsonl',offset=stream.tell(),bytes=len(raw)))
        stream.write(raw)
        if number>=200 and expanded[g['tier']]>=20:continue
        expanded[g['tier']]+=1
        save(folder/(stem+'.json'),task)
        text='# '+g['title']+'\n\n语义能力：`'+g['key']+'`\n\n'
        text+=f"影响 {g['affected_mods']} 个逻辑模组、{g['affected_logical_files']} 个逻辑源文件，优先级 {g['priority']}。这是潜在受益范围，不是已救活模组数。\n\n"
        text+='## 代表证据\n\n'+'\n'.join('- '+r['logical_mod']+' · '+r['file']+':'+str(r.get('line') or '?')+' · '+r['evidence']+' · '+r.get('reason','') for r in chosen)
        text+='\n\n## 通用修复要求\n\n'+task['expected_generalized_fix']+'\n\n现有测试候选：'+', '.join(matches)+'\n\n必须保留 Java/Py2/Py3/原件与金样回归证据。具体重载和原始诊断见同名 JSON。\n'
        (folder/(stem+'.md')).write_text(text,encoding='utf-8')
    for stream in streams.values():stream.close()
    save(out/'tasks/index.json',dict(schema_version=1,format='UTF8_JSONL_BYTE_OFFSETS',tasks=task_index,
        expanded_review_files=expanded,note='All semantic tasks are present in A/B/C.jsonl; highest-ranked tasks also have individual JSON/Markdown files.'))
    save(out/'ranking.json',dict(schema_version=1,profile=run['profile_sha256'],summary=run['summary'],
        formula='logical_mods * mean_unique_logical_source_files * foundation_weight / complexity',
        groups=[{k:v for k,v in g.items() if k!='occurrences'} for g in run['groups']]))
    review_summary=dict(status=run['status'],summary=run['summary'],errors=run['errors'],report_errors=run['report_errors'],
        unread_classes=[dict(path=a['path'],entry=e['entry'],error=e['error']) for a in run['artifacts'] for e in a.get('unknown_classes',[])],
        source_profile=run['profile_sha256'],engine_verified=False)
    with zipfile.ZipFile(out/'能力任务包.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted((out/'tasks').rglob('*')):
            if p.is_file():z.write(p,p.relative_to(out).as_posix())
        z.writestr('README.md','A：受审查精确配方；B：模板与对照审查；C：供 6.1 审查的语义任务。全部能力保存在 tasks/A.jsonl、B.jsonl、C.jsonl；index.json 给出每项 UTF-8 字节偏移与长度，可直接定位。排名前 200 项及每类至少前 20 项另附独立 JSON/Markdown。任务包仅为数据与证据，不会发送消息或启动智能体。\n')
        z.writestr('cohort.json',json.dumps(list(inputs.values()),ensure_ascii=False,indent=2))
        z.write(out/'profile.json','profile.json')
        z.writestr('run_summary.json',json.dumps(review_summary,ensure_ascii=False,indent=2))
    data=[dict(id=g['key'],name=g['title'],tier=g['tier'],mods=g['affected_mods'],files=g['affected_logical_files'],observed=g['observed_blocked_mods'],suspect=g['static_suspect_mods'],priority=g['priority'],descriptors=g['descriptors'],attribution=g['attribution']) for g in run['groups']]
    encoded=json.dumps(data,ensure_ascii=True).replace('<','\\u003c')
    summary=html.escape(json.dumps(run['summary'],ensure_ascii=False))
    summary=html.escape('扫描完成（PASSED）' if run['status']=='PASSED' else '扫描不完整（'+run['status']+'），以下失败记录不计作已覆盖。')+'<br>'+summary
    if run['status']!='PASSED':summary+='<pre>'+html.escape(json.dumps(review_summary,ensure_ascii=False,indent=2))+'</pre>'
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NeoCore 0.9.9 · 兼容性挖掘</title>
<style>body{margin:0;background:#f3f6fa;color:#233247;font:15px system-ui}main{max-width:1280px;margin:40px auto;padding:0 24px}h1{font-size:30px}p{line-height:1.7}section{background:white;border:1px solid #dce4ef;border-radius:12px;padding:22px;margin:20px 0}input,select,button{padding:10px;border:1px solid #cbd7e5;border-radius:7px;font:inherit}input{min-width:300px}table{width:100%;border-collapse:collapse}td,th{padding:12px;text-align:left;border-bottom:1px solid #e8edf4}th{cursor:pointer;color:#365b92}td:first-child{max-width:470px;overflow-wrap:anywhere}.muted{color:#63758b;font-size:13px}.scroll{overflow:auto}code{font-size:12px}</style>
<main><h1>NeoCore 兼容性挖掘引擎 <small>0.9.9</small></h1><p>按语义能力聚类，估算一次通用修复的潜在受益范围。</p><section><b>本轮统计</b><p id="summary"></p><p class="muted">优先级 = 影响逻辑模组数 × 平均源文件数 × 基础能力权重 ÷ 修复复杂度。相同 JAR 副本、同模组多个版本不会重复计为多个模组。</p></section>
<section><input id="q" placeholder="搜索能力、API 或方法"><select id="tier"><option value="">全部类别</option><option>A</option><option>B</option><option>C</option></select><p class="muted">A：精确受审查配方；B：模板候选与对照审查；C：复杂语义任务池。观察阻断来自当前编译报告，静态疑点不等于真实运行缺失。</p><div class="scroll"><table><thead><tr><th data-sort="name">语义能力</th><th data-sort="tier">类别</th><th data-sort="mods">潜在模组</th><th data-sort="files">源文件</th><th data-sort="observed">观察阻断模组</th><th data-sort="priority">优先级</th></tr></thead><tbody id="rows"></tbody></table></div><p id="count" class="muted"></p></section><p class="muted">清除静态疑点不等于 Python 生成增加，更不等于网易玩法通过。未归因诊断保留独立节点；任务包中的代表证据可直接用于后续审查。</p></main><script>
const data=DATA_PLACEHOLDER;let sort='priority',direction=-1,pageNumber=0,pageCount=1;const q=document.getElementById('q'),tier=document.getElementById('tier');
const evidence=document.createElement('select');evidence.innerHTML='<option value="">全部证据</option><option value="observed">仅已观察阻断</option><option value="static">含静态疑点</option>';tier.after(evidence);
const pager=document.createElement('div');const previous=document.createElement('button'),next=document.createElement('button');previous.textContent='上一页';next.textContent='下一页';pager.append(previous,next);document.getElementById('count').before(pager);
function render(){const rows=data.filter(x=>(!tier.value||x.tier===tier.value)&&(!evidence.value||(evidence.value==='observed'?x.observed>0:x.suspect>0))&&(x.id+' '+x.name).toLowerCase().includes(q.value.toLowerCase())).sort((a,b)=>direction*(typeof a[sort]==='number'?a[sort]-b[sort]:String(a[sort]).localeCompare(String(b[sort]))));pageCount=Math.max(1,Math.ceil(rows.length/200));pageNumber=Math.min(pageNumber,pageCount-1);const body=document.getElementById('rows');body.replaceChildren();for(const r of rows.slice(pageNumber*200,(pageNumber+1)*200)){const tr=document.createElement('tr');for(const k of ['name','tier','mods','files','observed','priority']){const td=document.createElement('td');td.textContent=r[k];if(k==='name'){const small=document.createElement('div');small.className='muted';small.textContent=r.id;td.append(small)}tr.append(td)}body.append(tr)}document.getElementById('count').textContent=rows.length+' 个能力节点 · 第 '+(pageNumber+1)+' / '+pageCount+' 页';previous.disabled=pageNumber===0;next.disabled=pageNumber===pageCount-1}
previous.onclick=()=>{pageNumber=Math.max(0,pageNumber-1);render()};next.onclick=()=>{pageNumber=Math.min(pageCount-1,pageNumber+1);render()};q.oninput=()=>{pageNumber=0;render()};tier.onchange=q.oninput;evidence.onchange=q.oninput;document.querySelectorAll('[data-sort]').forEach(th=>th.onclick=()=>{sort=th.dataset.sort;direction=-direction;pageNumber=0;render()});render();
</script></html>'''.replace('DATA_PLACEHOLDER',encoded).replace('<p id="summary"></p>','<p id="summary">'+summary+'</p>')
    (out/'report.html').write_text(page,encoding='utf-8')
