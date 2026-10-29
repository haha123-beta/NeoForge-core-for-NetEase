import hashlib,json,os,sys,subprocess,tempfile,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
from workspace_paths import DEV_ROOT
pkg=helper.pkg;profiling=pkg.load('minecraft.profiling');ROOT=DEV_ROOT/'references/minecraft-1.21.1'

def original(body,extra=''):
    version=json.loads((ROOT/'version.json').read_text(encoding='utf-8'));libraries=[]
    for row in version['libraries']:
        if row['name'].split(':')[1] in ('fastutil','guava','failureaccess','commons-lang3'):
            artifact=row['downloads']['artifact'];path=Path(r'F:\PCL\.minecraft\libraries')/artifact['path']
            assert hashlib.sha1(path.read_bytes()).hexdigest()==artifact['sha1'];libraries.append(str(path))
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'NeoCoreProfilerProbe.java'
        path.write_text(extra+' public class NeoCoreProfilerProbe {public static void main(String[] args){'+body+'}}',encoding='utf-8')
        proc=subprocess.run([str(helper.JAVAC),'-encoding','UTF-8','-cp',os.pathsep.join([str(ROOT/'client.jar')]+libraries),'-d',directory,str(path)],capture_output=True,text=True)
        assert proc.returncode==0,proc.stderr
        proc=subprocess.run([str(helper.JAVA),'-cp',str(ROOT/'profiler-jvm-probe'),'neocoreprobe.ProfilerProbeLauncher',str(ROOT/'client.jar'),directory]+libraries,capture_output=True,text=True)
        assert proc.returncode==0,proc.stderr
        return proc.stdout.strip()

class Recorder(profiling.ProfilerFiller):
    def __init__(self,name,trace):self.name,self.trace=name,trace
    def startTick(self):self.trace.append(self.name+'start')
    def endTick(self):self.trace.append(self.name+'end')
    def push(self,label):self.trace.append(self.name+str(label.get() if hasattr(label,'get') else label))
    def pop(self):self.trace.append(self.name+'pop')
    def popPush(self,label):self.trace.append(self.name+'swap')
    def markForCharting(self,category):self.trace.append(self.name+'mark')
    def incrementCounter(self,label,count):self.trace.append(self.name+'count'+str(count))

class ProfilingTests(unittest.TestCase):
    def test_inactive_does_not_evaluate_supplier_or_reject_null(self):
        p=profiling.InactiveProfiler.INSTANCE;calls=[]
        p.startTick();p.push(lambda:calls.append('push'));p.popPush(None);p.incrementCounter(None,4);p.markForCharting(None);p.pop();p.endTick()
        self.assertEqual(calls,[])
        self.assertEqual(original('java.util.concurrent.atomic.AtomicInteger n=new java.util.concurrent.atomic.AtomicInteger();bnc p=bnc.a;p.a();p.a((java.util.function.Supplier<String>)()->{n.incrementAndGet();return "x";});p.b((String)null);p.a((String)null,4);p.a((bol)null);p.c();p.b();System.out.print(n.get());'),'0')
    def test_tee_inactive_identity_and_null_shortcuts(self):
        p=profiling.InactiveProfiler.INSTANCE;r=Recorder('r',[])
        self.assertIs(profiling.ProfilerFiller.tee(p,r),r);self.assertIs(profiling.ProfilerFiller.tee(r,p),r)
        self.assertIsNone(profiling.ProfilerFiller.tee(p,None));self.assertIsNone(profiling.ProfilerFiller.tee(None,p))
        self.assertEqual(original('System.out.print((bnf.a(bnc.a,null)==null)+":"+(bnf.a(null,bnc.a)==null));'),'true:true')
    def test_tee_same_instance_is_not_deduplicated(self):
        trace=[];r=Recorder('r',trace);tee=profiling.ProfilerFiller.tee(r,r);tee.startTick();tee.push('x');tee.pop();tee.endTick()
        self.assertEqual(trace,['rstart','rstart','rx','rx','rpop','rpop','rend','rend'])
        self.assertEqual(original('java.util.List<String> t=new java.util.ArrayList<>();bnf r=(bnf)java.lang.reflect.Proxy.newProxyInstance(bnf.class.getClassLoader(),new Class[]{bnf.class},(o,m,a)->{if(m.getParameterCount()==0)t.add(m.getName());return null;});bnf q=bnf.a(r,r);q.a();q.c();q.b();System.out.print(t);'),'[a, a, c, c, b, b]')
    def test_tee_invokes_supplier_once_per_child_in_order(self):
        trace=[];counter=[0]
        class Supplier:
            def get(self):counter[0]+=1;return str(counter[0])
        profiling.ProfilerFiller.tee(Recorder('L',trace),Recorder('R',trace)).push(Supplier())
        self.assertEqual(trace,['L1','R2'])
        self.assertEqual(original('java.util.List<String> t=new java.util.ArrayList<>();java.util.concurrent.atomic.AtomicInteger n=new java.util.concurrent.atomic.AtomicInteger();bnf r=(bnf)java.lang.reflect.Proxy.newProxyInstance(bnf.class.getClassLoader(),new Class[]{bnf.class},(o,m,a)->{if(a!=null&&a[0] instanceof java.util.function.Supplier)t.add(((java.util.function.Supplier<?>)a[0]).get().toString());return null;});bnf.a(r,r).a((java.util.function.Supplier<String>)()->""+n.incrementAndGet());System.out.print(t);'),'[1, 2]')
    def test_tee_first_failure_prevents_second_call(self):
        trace=[]
        class Throwing(Recorder):
            def push(self,label):raise RuntimeError('first')
        with self.assertRaisesRegex(RuntimeError,'first'):profiling.ProfilerFiller.tee(Throwing('L',trace),Recorder('R',trace)).push('x')
        self.assertEqual(trace,[])
        with self.assertRaises(pkg.load('java_stdlib.lang').NullPointerException):profiling.ProfilerFiller.tee(None,Recorder('R',trace)).pop()
    def test_default_counter_dispatches_virtual_two_argument_method(self):
        trace=[];p=Recorder('r',trace)
        profiling.Profilers.invoke(p,'incrementCounter',['java.lang.String'],['x'])
        profiling.Profilers.invoke(p,'incrementCounter',['java.lang.String','int'],['x',3])
        self.assertEqual(trace,['rcount1','rcount3'])
        self.assertEqual(original('java.util.List<String> t=new java.util.ArrayList<>();bnf p=(bnf)java.lang.reflect.Proxy.newProxyInstance(bnf.class.getClassLoader(),new Class[]{bnf.class},(o,m,a)->{if(m.isDefault())return java.lang.reflect.InvocationHandler.invokeDefault(o,m,a);if(a!=null&&a.length==2)t.add(a[1].toString());return null;});p.d("x");p.a("x",3);System.out.print(t);'),'[1, 3]')
    def test_results_singleton_and_real_empty_semantics(self):
        p=profiling.InactiveProfiler.INSTANCE;r=p.getResults()
        self.assertIs(r,profiling.EmptyProfileResults.EMPTY);self.assertIsNone(p.getEntry(None));self.assertFalse(r.saveResults(None))
        self.assertEqual([r.getStartTimeNano(),r.getEndTimeNano(),r.getStartTimeTicks(),r.getEndTimeTicks(),r.getNanoDuration(),r.getTickDuration()],[0]*6)
        self.assertEqual(r.getProfilerResults(),'');self.assertTrue(r.getTimes(None).isEmpty());r.getTimes('root').clear()
        self.assertEqual(original('bnc p=bnc.a;bne r=p.d();System.out.print((r==bna.a)+":"+(p.c((String)null)==null)+":"+r.a((java.nio.file.Path)null)+":"+r.f()+":"+r.g()+":"+r.a((String)null).size());'),'true:true:false:0:0:0')
    def test_chart_set_is_guava_immutable_empty_even_on_clear(self):
        s=profiling.InactiveProfiler.INSTANCE.getChartedPaths();self.assertEqual(s.size(),0)
        with self.assertRaises(pkg.load('java_stdlib._base').UnsupportedOperationException):s.clear()
        with self.assertRaises(pkg.load('java_stdlib._base').NoSuchElementException):s.iterator().next()
        self.assertEqual(original('java.util.Set<?> s=bnc.a.e();try{s.clear();}catch(UnsupportedOperationException e){System.out.print("immutable:");}System.out.print(s.size());'),'immutable:0')
    def test_metric_categories_match_original_enum(self):
        actual=';'.join(str(v.name())+':'+str(v.getDescription()) for v in profiling.MetricCategory.values())
        expected=original('java.util.List<String> r=new java.util.ArrayList<>();for(bol v:bol.values())r.add(v.name()+":"+v.a());System.out.print(String.join(";",r));')
        self.assertEqual(actual,expected)
    def test_demangle_and_default_wrapping(self):
        self.assertEqual(profiling.ProfileResults.demanglePath('a\x1eb\x1ec'),'a.b.c')
        with self.assertRaises(pkg.load('java_stdlib.lang').NullPointerException):profiling.ProfileResults.demanglePath(None)
        self.assertEqual(original('System.out.print(bne.b("a"+(char)30+"b"+(char)30+"c"));'),'a.b.c')
        class Results(profiling.ProfileResults):
            def getStartTimeTicks(self):return -1
            def getEndTimeTicks(self):return 2147483647
        self.assertEqual(Results().getTickDuration(),-2147483648)
    def test_private_construction_and_guard(self):
        for cls in (profiling.InactiveProfiler,profiling.EmptyProfileResults):
            with self.assertRaises(pkg.load('java_stdlib._base').UnsupportedOperationException):cls()
        with self.assertRaises(pkg.load('java_stdlib._base').UnsupportedOperationException):profiling.Profilers.require(object())

if __name__=='__main__':unittest.main()
