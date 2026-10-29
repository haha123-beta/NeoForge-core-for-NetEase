"""Offline HTML: no remote scripts, dynamic HTML, or execution of mod data."""
import html,json
from pathlib import Path

def write_html(path,graph,ranking,lock):
    esc=lambda x:html.escape(str(x),quote=True)
    summary=graph['summary']
    rows=[]
    for file,row in graph['files'].items():
        if row['baseline_status']!='MANUAL_REVIEW' and not row['dependencies']:continue
        facts=[graph['blocker_nodes'][k] for k in row['measured_blockers']]
        detail='\n'.join(n['category']+' | '+n['symbol']+' | '+n['summary'] for n in facts)
        static='\n'.join(graph['blocker_nodes'][k]['category']+' | '+graph['blocker_nodes'][k]['symbol'] for k in row['static_requirements'])
        rows.append('<tr><td>'+esc(file)+'</td><td>'+esc(row['baseline_status'])+'</td><td><pre>'+esc(detail)+'</pre></td><td><details><summary>'+str(len(row['static_requirements']))+' 个静态需求（非运行实测）</summary><pre>'+esc(static)+'</pre></details></td><td>'+esc('\n'.join(row['dependencies']))+'</td><td>'+esc('\n'.join(row['unknowns']))+'</td></tr>')
    priorities=[]
    for row in ranking['candidates'][:35]:
        s=row['scenario']
        priorities.append('<tr><td>'+esc(row['id'])+'</td><td>'+esc(row['score'])+'</td><td>'+esc(row['heuristic_cost_units'])+'</td><td>'+str(len(row['affected_files']))+'</td><td>'+esc(s['scenario_generation_range'])+'</td><td>'+str(len(s['all_observed_manual_requirements_cleared']))+'</td><td>'+esc(', '.join(row['categories']))+'</td><td><details><summary>文件</summary><pre>'+esc('\n'.join(row['affected_files']))+'</pre></details></td></tr>')
    batches=[]
    for row in ranking['greedy_sets']:
        batches.append('<details><summary>候选集合 '+str(row['step'])+'：诊断情景 '+esc(row['scenario']['scenario_generation_range'])+'</summary><pre>'+esc(json.dumps(row,ensure_ascii=False,indent=2))+'</pre></details>')
    body='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>NeoCore 0.9.1 兼容性分析</title><style>body{font:15px/1.6 system-ui,sans-serif;margin:32px;color:#182536;background:#f5f7fb}h1,h2{color:#173c65}section{background:white;padding:22px;margin:20px 0;border:1px solid #dbe3ed;border-radius:10px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #dbe3ed;padding:9px;text-align:left;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.6 monospace;max-height:28em;overflow:auto}td:first-child{overflow-wrap:anywhere;max-width:26em}.notice{border-left:6px solid #d9921c;padding:16px;background:#fff4d9}a{color:#245788}</style>
<h1>NeoCore 0.9.1 · 兼容性分析</h1><p>目标 Minecraft 1.21.1 / NeoForge 21.1.233 / FML 4.0.42；独立开发工具。</p>
<p class="notice">生成基线仍为 <b>32/130</b>，98 人工处理、0 失败、15 个生成文件缺依赖。分析器没有新增生产 API，也不声称运行/加载/玩法通过。静态引用、实测诊断、候选情景分别记录；未探索的后续编译器阻断保持 UNKNOWN。</p>
<section><h2>范围与证据</h2><p>原始 191 个 class 与 130 个 CFR 文件交叉核对。descriptor、继承、字段/方法引用和调用来自 class 字节；CFR 的调用名对照不冒充 descriptor 解析。</p><pre>'''+esc(json.dumps(summary,ensure_ascii=False,indent=2))+'''</pre><p>完整数据：analysis.json、ranking.json、cfr_index.json、official_abi.json.gz、versions.lock.json。所有路径及来源 SHA 都在锁清单；报告可离线阅读。</p></section>
<section><h2>0.9.2 候选修复排序</h2><p>成本为启发式单位。情景范围不是保证边界；下界 0，未重新转换验证，不可写成实际增益。“全部已见需求清除”仅说明图上约束，不证明完整兼容。ASM/可选插件不作为默认核心修复优先项。</p><table><thead><tr><th>候选</th><th>分数</th><th>成本估计</th><th>影响文件</th><th>仅首诊断生成情景</th><th>全部已见需求清除</th><th>分类</th><th>证据范围</th></tr></thead><tbody>'''+''.join(priorities)+'''</tbody></table></section><section><h2>候选修复集合</h2>'''+''.join(batches)+'''</section><section><h2>98 人工文件与 15 个依赖缺失文件</h2><p>每行保留 0.9.0 的实际首诊断，同时列出全 class 扫描所见的其他独立需求。后者可能受 side、可选配置或不可达路径控制，不能视为必然执行失败。</p><table><thead><tr><th>文件</th><th>基线状态</th><th>实测诊断</th><th>其他静态需求</th><th>缺失生成依赖</th><th>未知边界</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></section><section><h2>分析局限</h2><pre>'''+esc('\n'.join(graph['limits']))+'''</pre><p>原始版本锁和 0.9.0 生产字节在分析前后校验；Curios 只作为版本锁定的分析 ABI，不导入核心；未找到匹配 JEI 时保持依赖版本未知，不使用错误 Fabric 包。</p></section></html>'''
    Path(path).write_text(body,encoding='utf-8')
