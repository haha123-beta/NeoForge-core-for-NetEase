import hashlib,os,sys,json,subprocess,tempfile,unittest,random
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
from workspace_paths import DEV_ROOT
pkg=helper.pkg;goals=pkg.load('minecraft.goals');Flag=goals.Goal.Flag
ROOT=DEV_ROOT/'references/minecraft-1.21.1'
FASTUTIL=Path(r'F:\PCL\.minecraft\libraries\it\unimi\dsi\fastutil\8.5.12\fastutil-8.5.12.jar')

class Probe(goals.Goal):
    def __init__(self,name,trace,flag=Flag.MOVE):
        super(Probe,self).__init__();self.name=name;self.trace=trace;self.enabled=True;self.every=False;self.interruptible=True
        if flag is not None:self.setFlags(goals.EnumSet.of(flag))
    def canUse(self):self.trace.append(self.name+'?');return self.enabled
    def canContinueToUse(self):self.trace.append(self.name+'~');return self.enabled
    def isInterruptable(self):return self.interruptible
    def start(self):self.trace.append(self.name+'+')
    def stop(self):self.trace.append(self.name+'-')
    def tick(self):self.trace.append(self.name+'!')
    def requiresUpdateEveryTick(self):return self.every

JAVA_PROBE='''
import java.util.*;
class P extends cam {
 String name; static List<String> trace=new ArrayList<>(); boolean enabled=true,every=false,interruptible=true;
 P(String n,cam.a flag){name=n;if(flag!=null)a(EnumSet.of(flag));}
 public boolean b(){trace.add(name+"?");return enabled;}
 public boolean c(){trace.add(name+"~");return enabled;}
 public boolean U_(){return interruptible;}
 public void d(){trace.add(name+"+");}
 public void e(){trace.add(name+"-");}
 public void a(){trace.add(name+"!");}
 public boolean V_(){return every;}
}
'''

class GoalSelectorContract(unittest.TestCase):
    def original(self,body):
        version=json.loads((ROOT/'version.json').read_text(encoding='utf-8'))
        spec=next(row['downloads']['artifact'] for row in version['libraries'] if row['name']=='it.unimi.dsi:fastutil:8.5.12')
        self.assertEqual(hashlib.sha1(FASTUTIL.read_bytes()).hexdigest(),spec['sha1'])
        # Actual original profiler interface, implemented only as an observation sink.
        profiler='bnf profiler=(bnf)java.lang.reflect.Proxy.newProxyInstance(bnf.class.getClassLoader(),new Class[]{bnf.class},(o,m,a)->null);can s=new can(()->profiler);'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'NeoCoreSelectorProbe.java'
            path.write_text(JAVA_PROBE+'public class NeoCoreSelectorProbe {public static void main(String[] args){'+profiler+body+'}}',encoding='utf-8')
            proc=subprocess.run([str(helper.JAVAC),'-encoding','UTF-8','-cp',str(ROOT/'client.jar'),'-d',directory,str(path)],capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr)
            proc=subprocess.run([str(helper.JAVA),'-cp',str(ROOT/'goal-selector-jvm-probe'),'neocoreprobe.GoalSelectorProbeLauncher',str(ROOT/'client.jar'),directory,str(FASTUTIL)],capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr)
            return proc.stdout.strip()
    def test_insertion_order_preemption_matches_original(self):
        trace=[];s=goals.GoalSelector();low=Probe('L',trace);high=Probe('H',trace)
        s.addGoal(8,low);s.addGoal(1,high);s.tick()
        original=self.original('P l=new P("L",cam.a.a),h=new P("H",cam.a.a);s.a(8,l);s.a(1,h);s.a();System.out.print(P.trace);')
        self.assertEqual('['+', '.join(trace)+']',original)
        self.assertEqual(trace,['L?','L+','H?','L-','H+','H!'])
    def test_wrapper_start_sets_running_before_callback_and_keeps_state_on_failure(self):
        class Throwing(Probe):
            def start(self):
                self.trace.append(wrapper.isRunning());raise RuntimeError('start')
        trace=[];wrapper=goals.WrappedGoal(1,Throwing('T',trace))
        with self.assertRaises(RuntimeError):wrapper.start()
        self.assertEqual(trace,[True]);self.assertTrue(wrapper.isRunning())
        self.assertEqual(self.original('P p=new P("T",cam.a.a){public void d(){throw new IllegalStateException();}};cca w=new cca(1,p);try{w.d();}catch(IllegalStateException e){}System.out.print(w.h());'),'true')
    def test_wrapped_delegation_delay_and_equality(self):
        trace=[];p=Probe('P',trace);w=goals.WrappedGoal(2,p)
        self.assertIsInstance(w,goals.Goal);self.assertIs(w.getFlags(),p.getFlags())
        self.assertTrue(w.equals(goals.WrappedGoal(9,p)));self.assertEqual(w.hashCode(),goals.WrappedGoal(9,p).hashCode())
        self.assertTrue(w.canBeReplacedBy(goals.WrappedGoal(1,Probe('H',trace))))
        self.assertFalse(w.canBeReplacedBy(goals.WrappedGoal(2,p)))
        p.interruptible=False;self.assertFalse(w.canBeReplacedBy(None))
        p.adjustedTickDelay=lambda n:13;self.assertEqual(w.adjustedTickDelay(5),13)
        w.setFlags(goals.EnumSet.of(Flag.LOOK));self.assertEqual(list(p.getFlags()),[Flag.LOOK])
        self.assertEqual(self.original('P p=new P("P",cam.a.a);cca w=new cca(2,p);System.out.print((w.j()==p.j())+":"+w.equals(new cca(9,p))+":"+(w.hashCode()==p.hashCode()));'),'true:true:true')
    def test_remove_all_does_not_stop_running_original(self):
        trace=[];s=goals.GoalSelector();p=Probe('P',trace);s.addGoal(1,p);s.tick();w=list(s.getAvailableGoals())[0]
        s.removeAllGoals(lambda value:True)
        self.assertTrue(w.isRunning());self.assertEqual(s.getAvailableGoals().size(),0);self.assertNotIn('P-',trace)
        self.assertEqual(self.original('P p=new P("P",cam.a.a);s.a(1,p);s.a();cca w=s.b().iterator().next();s.a((java.util.function.Predicate<cam>)(v->true));System.out.print(w.h()+":"+s.b().size()+":"+P.trace);'),'true:0:[P?, P+, P!]')
    def test_selective_tick_and_double_profiler_supplier(self):
        trace=[];s=goals.GoalSelector();a=Probe('A',trace);b=Probe('B',trace,Flag.LOOK);b.every=True
        s.addGoal(1,a);s.addGoal(2,b);s.tick();trace[:]=[];s.tickRunningGoals(False)
        self.assertEqual(trace,['B!'])
        self.assertEqual(self.original('P a=new P("A",cam.a.a),b=new P("B",cam.a.b);b.every=true;s.a(1,a);s.a(2,b);s.a();P.trace.clear();s.a(false);System.out.print(P.trace);'),'[B!]')
        calls=[]
        class Profile:
            def push(self,name):calls.append(name)
            def pop(self):calls.append('pop')
        def supply():calls.append('get');return Profile()
        goals.GoalSelector(supply).tick()
        self.assertEqual(calls,['get','goalCleanup','pop','goalUpdate','pop','get','goalTick','pop'])
    def test_available_live_order_set_and_iterator_removal(self):
        s=goals.GoalSelector();trace=[];a=Probe('A',trace);b=Probe('B',trace)
        view=s.getAvailableGoals();s.addGoal(9,a);s.addGoal(1,b);s.addGoal(0,a)
        self.assertIs(view,s.getAvailableGoals());self.assertEqual([w.getPriority() for w in view],[9,1])
        cursor=view.iterator();self.assertIs(cursor.next().getGoal(),a);cursor.remove()
        with self.assertRaises(pkg.load('java_stdlib._base').IllegalStateException):cursor.remove()
        self.assertEqual([w.getGoal() for w in view],[b])
        self.assertEqual(self.original('P a=new P("A",cam.a.a),b=new P("B",cam.a.a);java.util.Set<cca> v=s.b();s.a(9,a);s.a(1,b);s.a(0,a);java.util.Iterator<cca> i=v.iterator();System.out.print(i.next().i()+":"+v.size()+":");i.remove();System.out.print(v.iterator().next().i());'),'9:2:1')
    def test_null_predicate_empty_collection_and_null_profiler(self):
        s=goals.GoalSelector();s.removeAllGoals(None)
        s.addGoal(1,Probe('P',[]))
        with self.assertRaises(pkg.load('java_stdlib.lang').NullPointerException):s.removeAllGoals(None)
        with self.assertRaises(pkg.load('java_stdlib.lang').NullPointerException):goals.GoalSelector(None).tick()
    def test_control_flag_null_boundary(self):
        s=goals.GoalSelector();s.enableControlFlag(None)
        with self.assertRaises(pkg.load('java_stdlib.lang').NullPointerException):s.disableControlFlag(None)
    def test_minimum_priority_sentinel_does_not_start_max_priority_flagged_goal(self):
        s=goals.GoalSelector();trace=[];s.addGoal(2147483647,Probe('P',trace));s.tick();self.assertEqual(trace,[])
        self.assertEqual(self.original('s.a(Integer.MAX_VALUE,new P("P",cam.a.a));s.a();System.out.print(P.trace);'),'[]')
    def test_changed_flags_keep_original_locks_until_cleanup(self):
        trace=[];s=goals.GoalSelector();a=Probe('A',trace);b=Probe('B',trace)
        s.addGoal(1,a);s.tick();a.setFlags(goals.EnumSet.of(Flag.LOOK));s.addGoal(2,b);s.tick()
        self.assertEqual('['+', '.join(trace)+']',self.original('P a=new P("A",cam.a.a),b=new P("B",cam.a.a);s.a(1,a);s.a();a.a(EnumSet.of(cam.a.b));s.a(2,b);s.a();System.out.print(P.trace);'))
        self.assertNotIn('B?',trace)
    def test_seeded_mixed_operations_match_original_scheduler(self):
        trace=[];s=goals.GoalSelector();items=[Probe(chr(65+i),trace,Flag._values[i%4]) for i in range(6)]
        code=['P[] p=new P[6];for(int i=0;i<6;i++)p[i]=new P(""+(char)(65+i),cam.a.values()[i%4]);']
        rng=random.Random(381211)
        for unused in range(180):
            index=rng.randrange(6);op=rng.randrange(9);value=bool(rng.randrange(2));jbool=str(value).lower();flag=Flag._values[index%4]
            if op==0:
                priority=rng.randrange(-2,6);s.addGoal(priority,items[index]);code.append('s.a(%d,p[%d]);'%(priority,index))
            elif op==1:s.removeGoal(items[index]);code.append('s.a(p[%d]);'%index)
            elif op==2:items[index].enabled=value;code.append('p[%d].enabled=%s;'%(index,jbool))
            elif op==3:items[index].interruptible=value;code.append('p[%d].interruptible=%s;'%(index,jbool))
            elif op==4:items[index].every=value;code.append('p[%d].every=%s;'%(index,jbool))
            elif op==5:s.setControlFlag(flag,value);code.append('s.a(cam.a.values()[%d],%s);'%(index%4,jbool))
            elif op==6:s.tickRunningGoals(value);code.append('s.a(%s);'%jbool)
            else:s.tick();code.append('s.a();')
        code.append('System.out.print(String.join(",",P.trace));')
        self.assertEqual(','.join(trace),self.original(''.join(code)))
    def test_remove_all_leaves_lock_that_blocks_other_goals(self):
        trace=[];s=goals.GoalSelector();a=Probe('A',trace);b=Probe('B',trace)
        s.addGoal(1,a);s.tick();s.removeAllGoals(lambda value:True);s.addGoal(2,b);s.tick()
        self.assertEqual('['+', '.join(trace)+']',self.original('P a=new P("A",cam.a.a),b=new P("B",cam.a.a);s.a(1,a);s.a();s.a((java.util.function.Predicate<cam>)(v->true));s.a(2,b);s.a();System.out.print(P.trace);'))
    def test_null_entries_and_hash_failures_propagate_at_original_boundaries(self):
        s=goals.GoalSelector()
        with self.assertRaises(pkg.load('java_stdlib.lang').NullPointerException):s.addGoal(1,None)
        s.getAvailableGoals().add(None)
        with self.assertRaises(pkg.load('java_stdlib.lang').NullPointerException):s.tick()
        self.assertEqual(self.original('try{s.a(1,(cam)null);}catch(NullPointerException e){System.out.print("add:");}s.b().add(null);try{s.a();}catch(NullPointerException e){System.out.print("tick");}'),'add:tick')
    def test_set_add_does_not_swallow_original_hash_exception(self):
        class Bad(Probe):
            def hashCode(self):raise RuntimeError('hash failed')
        s=goals.GoalSelector()
        with self.assertRaisesRegex(RuntimeError,'hash failed'):s.addGoal(1,Bad('B',[]))
        self.assertEqual(s.getAvailableGoals().size(),0)
    def test_reentrant_append_is_visible_after_existing_successor(self):
        trace=[];s=goals.GoalSelector();extra=Probe('C',trace,None)
        class Adding(Probe):
            def start(self):
                super(Adding,self).start();s.addGoal(3,extra)
        s.addGoal(1,Adding('A',trace,None));s.addGoal(2,Probe('B',trace,None));s.tick()
        oracle=self.original('P c=new P("C",null);P a=new P("A",null){public void d(){super.d();s.a(3,c);}};s.a(1,a);s.a(2,new P("B",null));s.a();System.out.print(P.trace);')
        self.assertEqual('['+', '.join(trace)+']',oracle)
        self.assertIn('C+',trace)
    def test_reentrant_append_after_last_entry_waits_until_next_update(self):
        trace=[];s=goals.GoalSelector();extra=Probe('C',trace,None)
        class Adding(Probe):
            def start(self):
                super(Adding,self).start();s.addGoal(3,extra)
        s.addGoal(1,Adding('A',trace,None));s.tick()
        self.assertEqual('['+', '.join(trace)+']',self.original('P c=new P("C",null);P a=new P("A",null){public void d(){super.d();s.a(3,c);}};s.a(1,a);s.a();System.out.print(P.trace);'))
        self.assertNotIn('C+',trace);s.tick();self.assertIn('C+',trace)
    def test_removed_next_cursor_target_is_explicitly_unsupported(self):
        s=goals.GoalSelector();a=Probe('A',[]);b=Probe('B',[]);s.addGoal(1,a);s.addGoal(2,b)
        cursor=s.getAvailableGoals().iterator();cursor.next();s.removeGoal(b)
        with self.assertRaisesRegex(pkg.load('java_stdlib._base').UnsupportedOperationException,'removed externally'):cursor.next()

if __name__=='__main__':unittest.main()
