"""Same authenticated local workbench; mining writes only its own run folders."""
import json,threading,uuid
from pathlib import Path
from .engine import scan,save,load,compare

class Controller:
    def __init__(self,workspace):
        self.workspace=workspace;self.root=workspace.root/'兼容性挖掘';self.lock=threading.RLock()
        self.state=dict(status='IDLE');self.latest=None
        if self.root.exists():
            complete=[p for p in self.root.iterdir() if p.is_dir() and (p/'run.json').is_file() and (p/'report.html').is_file()]
            if complete:
                self.latest=max(complete,key=lambda p:p.stat().st_mtime)
                data=load(self.latest/('summary.json' if (self.latest/'summary.json').exists() else 'run.json'));self.state=self.finished(self.latest,data)
    def finished(self,output,data):
        errors=list(data.get('errors',[]))+list(data.get('report_errors',[]))
        artifacts=data.get('artifacts')
        if artifacts is None and data['summary'].get('unknown_classes'):
            artifacts=load(output/'cohort.json')['artifacts']
        for a in artifacts or []:
            errors.extend(dict(path=a['path'],entry=e['entry'],error=e['error']) for e in a.get('unknown_classes',[]))
        return dict(status=data['status'],id=output.name,summary=data['summary'],errors=errors)
    def snapshot(self):
        with self.lock:return dict(self.state,report_ready=self.latest is not None)
    def start(self,request):
        if set(request)-{'inputs','reports'}:raise ValueError('未知挖掘选项')
        inputs=request.get('inputs');reports=request.get('reports',[])
        if not isinstance(inputs,list) or not 1<=len(inputs)<=20 or any(not isinstance(p,str) or not p.strip() for p in inputs):raise ValueError('请填写 1–20 个 JAR 文件或目录')
        if not isinstance(reports,list) or len(reports)>20 or any(not isinstance(p,str) for p in reports):raise ValueError('报告目录格式无效')
        with self.workspace.lock,self.lock:
            if self.state['status']=='RUNNING' or self.workspace.active():raise ValueError('请等待当前转换或挖掘完成')
            identity=uuid.uuid4().hex;self.latest=None;self.state=dict(status='RUNNING',id=identity,progress=dict(done=0,total=0));output=self.root/identity
            def progress(data):
                with self.lock:self.state['progress']=data
            def worker():
                try:
                    result=scan(inputs,output,self.root/'cache',reports=reports,progress=progress)
                    with self.lock:self.latest=output;self.state=self.finished(output,result)
                except Exception as e:
                    with self.lock:self.state=dict(status='FAILED',id=identity,error=str(e))
                    save(output/'failure.json',self.state)
            threading.Thread(target=worker,daemon=True).start()
            return self.snapshot()
    def artifact(self,name):
        if name not in ('report.html','能力任务包.zip','ranking.json'):raise ValueError('未知挖掘产物')
        with self.lock:
            if self.latest is None:raise ValueError('尚无扫描结果')
            return (self.latest/name).read_bytes()

def controller(workspace):
    with workspace.lock:
        if not hasattr(workspace,'mining_controller'):workspace.mining_controller=Controller(workspace)
        return workspace.mining_controller

def page(token):
    text='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NeoCore 0.9.8 · 兼容性挖掘</title><style>body{background:#f3f6fa;color:#233247;font:15px system-ui;margin:0}main{max-width:900px;margin:40px auto;padding:0 24px}section{padding:24px;background:white;border:1px solid #dce4ef;border-radius:12px;margin:20px 0}textarea{box-sizing:border-box;width:100%;padding:12px;font:14px system-ui;border:1px solid #bacadd;border-radius:7px}button,a{display:inline-block;padding:10px 15px;margin:10px 8px 0 0;border-radius:7px}button{background:#2563a8;color:white;border:0;font:inherit;cursor:pointer}a{color:#2563a8}p{line-height:1.7}.muted{color:#63758b}pre{white-space:pre-wrap}</style><main><a href="/">← 转换工作台</a><h1>兼容性挖掘</h1><p>让一批真实模组暴露共同缺口，优先补能帮助更多模组的通用能力。</p><section><h2>开始一轮扫描</h2><p>填写本机 JAR 文件或目录，每行一个。目录会递归查找，相同文件内容会去重。</p><textarea id="inputs" rows="4" placeholder="填写存放模组 JAR 的目录"></textarea><p>已有转换报告目录（可选，每行一个）</p><textarea id="reports" rows="2"></textarea><button id="start">扫描并排序</button><p class="muted">扫描读取字节码，不执行输入模组。普通静态疑点与已经发生的转换阻断分开显示。</p></section><section><h2>本轮进展</h2><pre id="status">读取中…</pre><div id="links" hidden><a href="/mining/report" target="_blank">查看能力排行榜</a><button id="tasks">下载能力任务包</button><button id="ranking">下载排名数据</button></div></section><p class="muted">A 类：受审查精确配方自动生成候选；B 类：模板与对照验证；C 类：复杂能力任务池。候选补丁的生成、Java/Py2/Py3/全量回归及应用使用随包的兼容性挖掘命令，扫描本身不会直接修改核心。</p><p id="error"></p></main><script>
const token=__MINING_TOKEN__;const headers={'X-NeoCore-Token':token,'Content-Type':'application/json'};
async function api(path,body){let r=await fetch(path,{method:body?'POST':'GET',headers,body:body?JSON.stringify(body):undefined});let v=await r.json();if(!r.ok)throw Error(v.error||'操作失败');return v}
async function poll(){try{let s=await api('/api/mining/state');let p=s.progress||{};const labels={IDLE:'等待扫描',RUNNING:'正在扫描',PASSED:'扫描完成',PARTIAL:'扫描不完整，请查看以下失败记录',FAILED:'扫描失败'};document.getElementById('status').textContent=(labels[s.status]||s.status)+(p.total?' · '+p.done+'/'+p.total:'')+(p.name?' · '+p.name:'')+(s.summary?'\\n'+JSON.stringify(s.summary,null,2):'')+(s.errors&&s.errors.length?'\\n失败记录：\\n'+JSON.stringify(s.errors,null,2):'')+(s.error?'\\n'+s.error:'');document.getElementById('links').hidden=!s.report_ready;document.getElementById('start').disabled=s.status==='RUNNING'}catch(e){document.getElementById('error').textContent=e.message}}
document.getElementById('start').onclick=async()=>{try{const lines=id=>document.getElementById(id).value.split(/\\r?\\n/).map(s=>s.trim()).filter(Boolean);await api('/api/mining/start',{inputs:lines('inputs'),reports:lines('reports')});poll()}catch(e){document.getElementById('error').textContent=e.message}};
async function download(route,name){try{const r=await fetch(route,{headers});if(!r.ok)throw Error('下载失败');const u=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),5000)}catch(e){document.getElementById('error').textContent=e.message}}
document.getElementById('tasks').onclick=()=>download('/api/mining/tasks','能力任务包.zip');document.getElementById('ranking').onclick=()=>download('/api/mining/ranking','ranking.json');poll();setInterval(poll,1200);
</script></html>'''
    return text.replace('__MINING_TOKEN__',json.dumps(token)).encode('utf-8')
