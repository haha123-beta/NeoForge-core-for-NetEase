import os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
from java_codegen import NeedsLowering
pkg=helper.pkg;goals=pkg.load('minecraft.goals')
PREFIX='import net.minecraft.world.entity.ai.goal.Goal;import net.minecraft.world.entity.ai.goal.GoalSelector;import net.minecraft.world.entity.ai.goal.WrappedGoal;'

class JavaGoalSelector(unittest.TestCase):
    def python(self,source):return helper.ArrayTests().python(PREFIX+source)
    def test_original_public_call_chain_keeps_typed_flags(self):
        source='class Logic {static int run(GoalSelector selector,Goal goal){selector.addGoal(8,goal);selector.tick();WrappedGoal wrapped=selector.getAvailableGoals().iterator().next();return wrapped.getPriority()+wrapped.getFlags().iterator().next().ordinal();}}'
        ns,result=self.python(source)
        class G(goals.Goal):
            def canUse(self):return True
        goal=G();goal.setFlags(goals.EnumSet.of(goals.Goal.Flag.JUMP))
        self.assertEqual(ns['Logic'].run(goals.GoalSelector(),goal),10)
        self.assertIn('neocore.runtime.GoalSchedulers@1',result['required_runtime_helpers'])
    def test_wrapped_constructor_forwards_and_retains_goal_identity(self):
        ns,_=self.python('class Logic {static boolean run(Goal goal){WrappedGoal wrapped=new WrappedGoal(5,goal);wrapped.start();return wrapped.isRunning()&&wrapped.getGoal()==goal;}}')
        class G(goals.Goal):
            def canUse(self):return True
        self.assertTrue(ns['Logic'].run(G()))
    def test_remove_predicate_parameter_is_goal_and_body_stays_original(self):
        ns,_=self.python('class Logic {static int run(GoalSelector selector,Goal goal){selector.addGoal(2,goal);selector.removeAllGoals(candidate -> candidate.canUse());return selector.getAvailableGoals().size();}}')
        class G(goals.Goal):
            def canUse(self):return True
        self.assertEqual(ns['Logic'].run(goals.GoalSelector(),G()),0)
    def test_control_and_selective_tick_original_calls(self):
        ns,_=self.python('class Logic {static void run(GoalSelector selector){selector.disableControlFlag(Goal.Flag.MOVE);selector.enableControlFlag(Goal.Flag.MOVE);selector.setControlFlag(Goal.Flag.LOOK,false);selector.tickRunningGoals(false);}}')
        selector=goals.GoalSelector();ns['Logic'].run(selector)
        self.assertEqual(list(selector._disabled),[goals.Goal.Flag.LOOK])
    def test_no_arg_java_selector_is_refused_instead_of_using_core_convenience(self):
        with self.assertRaisesRegex(NeedsLowering,'reviewed Java signature'):
            self.python('class Logic {GoalSelector run(){return new GoalSelector();}}')
    def test_null_supplier_accepted_at_construction_and_fails_on_tick(self):
        ns,_=self.python('class Logic {boolean run(){GoalSelector selector=new GoalSelector(null);try{selector.tick();}catch(NullPointerException e){return true;}return false;}}')
        self.assertTrue(ns['Logic']().run())
    def test_core_only_extensions_are_not_exposed_as_vanilla_methods(self):
        for method in ('stopAll','getRunningGoals'):
            with self.subTest(method=method),self.assertRaisesRegex(NeedsLowering,'implemented public adapter'):
                self.python('class Logic {void run(GoalSelector selector){selector.'+method+'();}}')
    def test_legacy_or_wrong_receiver_and_null_are_explicit(self):
        ns,_=self.python('class Logic {static void run(GoalSelector selector){selector.tickRunningGoals(false);}}')
        with self.assertRaises(pkg.load('java_stdlib.lang').NullPointerException):ns['Logic'].run(None)
        with self.assertRaises(pkg.load('java_stdlib._base').UnsupportedOperationException):ns['Logic'].run(object())
    def test_available_set_iterator_removes_from_live_selector(self):
        ns,_=self.python('class Logic {static int run(GoalSelector selector,Goal goal){selector.addGoal(1,goal);java.util.Iterator<WrappedGoal> iterator=selector.getAvailableGoals().iterator();iterator.next();iterator.remove();return selector.getAvailableGoals().size();}}')
        self.assertEqual(ns['Logic'].run(goals.GoalSelector(),goals.Goal()),0)
    def test_reference_equality_is_identity_and_evaluates_each_operand_once(self):
        source='class Logic {int calls;Goal value;Logic(Goal goal){value=goal;}Goal read(){calls++;return value;}boolean run(){return read()==value&&read()!=null&&calls==2;}}'
        ns,_=self.python(source)
        class G(goals.Goal):
            def equals(self,other):return True
        goal=G();self.assertTrue(ns['Logic'](goal).run())
        ns,_=self.python('class Logic {static boolean run(Goal a,Goal b){return a==b;}}')
        self.assertFalse(ns['Logic'].run(G(),G()));self.assertTrue(ns['Logic'].run(goal,goal))
        java='class Logic {int calls;Object value;Logic(Object goal){value=goal;}Object read(){calls++;return value;}boolean run(){return read()==value&&read()!=null&&calls==2;}}'
        self.assertEqual(helper.ArrayTests().java(java,'System.out.print(new Logic(new Object()).run());'),'true')
    def test_reference_equality_unrelated_and_string_interning_stay_explicit(self):
        for source in ('class Logic {boolean run(Goal a,GoalSelector b){return a==b;}}','class Logic {boolean run(String a,String b){return a==b;}}'):
            with self.subTest(source=source),self.assertRaises(NeedsLowering):self.python(source)

if __name__=='__main__':unittest.main()
