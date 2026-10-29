import os,sys,unittest,copy,random
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
import test_java_runtime_inheritance as inheritance_helper
from java_codegen import NeedsLowering
pkg=helper.pkg;goals=pkg.load('minecraft.goals');api=pkg.load('minecraft.runtime_classes').RuntimeClasses
PREFIX='import net.minecraft.world.entity.ai.goal.Goal;'
BASE='class A extends Goal {boolean exact;public boolean canUse(){return true;}public boolean requiresUpdateEveryTick(){return exact;}int run(int n){return adjustedTickDelay(n);}int parent(int n){return super.adjustedTickDelay(n);}static int reduce(int n){return reducedTickDelay(n);}}'
VALUES=[-2147483648,-2147483647,-101,-3,-2,-1,0,1,2,3,101,2147483646,2147483647]
_random = random.Random(1211)
VALUES += [_random.randint(-2147483648,2147483647) for unused in range(257)]
class GoalDelays(unittest.TestCase):
    def python(self,source):return helper.ArrayTests().python(PREFIX+source)
    def test_original_bytecode_arithmetic_matches_real_jdk_edges(self):
        body='int[] values=new int[]{'+','.join(map(str,VALUES))+'};for(int n:values){System.out.print((-Math.floorDiv(-n,2))+", ");}'
        oracle=helper.ArrayTests().java('',body)
        actual=', '.join(str(goals.Goal.reducedTickDelay(n)) for n in VALUES)+','
        self.assertEqual(actual,oracle)
        self.assertEqual(goals.Goal.reducedTickDelay(-2147483648),1073741824)
    def test_source_delay_calls_preserve_virtual_update_frequency(self):
        ns,result=self.python(BASE);obj=ns['A']()
        for n in VALUES:
            self.assertEqual(obj.run(n),goals.Goal.reducedTickDelay(n))
            self.assertEqual(obj.parent(n),obj.run(n))
            self.assertEqual(ns['A'].reduce(n),obj.run(n))
        obj.exact=True
        for n in VALUES:self.assertEqual(obj.run(n),n);self.assertEqual(obj.parent(n),n)
        self.assertIn('neocore.runtime.RuntimeClasses@2',result['required_runtime_helpers'])
    def test_every_tick_branch_matches_original_minecraft_goal_jvm(self):
        source='class A extends Goal {public boolean canUse(){return true;}public boolean requiresUpdateEveryTick(){return true;}int run(int n){return super.adjustedTickDelay(n);}}'
        ns,_=self.python(source)
        mapped=source.replace('extends Goal','extends cam').replace('boolean canUse()','boolean b()').replace('boolean requiresUpdateEveryTick()','boolean V_()').replace('super.adjustedTickDelay','super.a')
        body='A a=new A();int[] values=new int[]{'+','.join(map(str,VALUES))+'};for(int n:values){System.out.print(a.run(n)+", ");}'
        oracle=inheritance_helper.RuntimeInheritance().original_goal_java(mapped,body)
        self.assertEqual(', '.join(str(ns['A']().run(n)) for n in VALUES)+',',oracle)
    def test_runtime_static_dispatch_ignores_hidden_method_and_evaluates_qualifier(self):
        source='class A extends Goal {int count;public boolean canUse(){return true;}protected static int reducedTickDelay(int n){return n+100;}A receiver(){count++;return null;}int run(int n){return receiver().reducedTickDelay(n);}int parent(int n){return super.reducedTickDelay(n);}}'
        ns,_=self.python(source);obj=ns['A']()
        self.assertEqual(obj.run(3),103);self.assertEqual(obj.count,1);self.assertEqual(obj.parent(3),2)
    def test_protected_access_uses_accessing_subclass_receiver(self):
        for source in ['class Logic {int run(Goal value){return value.adjustedTickDelay(3);}}',
                       'class Logic {int run(){return Goal.reducedTickDelay(3);}}',
                       'class A extends Goal {public boolean canUse(){return true;}int run(Goal value){return value.adjustedTickDelay(3);}}']:
            with self.subTest(source=source),self.assertRaisesRegex(NeedsLowering,'Protected runtime'):self.python(source)
        ns,_=self.python('class A extends Goal {public boolean canUse(){return true;}int run(A value){return value.adjustedTickDelay(3);}}')
        self.assertEqual(ns['A']().run(ns['A']()),2)
    def test_protected_override_preserves_super_and_virtual_semantics(self):
        ns,_=self.python('class A extends Goal {public boolean canUse(){return true;}protected int adjustedTickDelay(int n){return super.adjustedTickDelay(n)+10;}int run(int n){return adjustedTickDelay(n);}}')
        self.assertEqual(ns['A']().run(3),12)
        with self.assertRaises(NeedsLowering):self.python('class A extends Goal {public boolean canUse(){return true;}int adjustedTickDelay(int n){return n;}}')
    def test_bound_static_and_super_method_references_with_integer_unboxing(self):
        source='import java.util.function.Function;class A extends Goal {public boolean canUse(){return true;}Function<Integer,Integer> bound(){return this::adjustedTickDelay;}Function<Integer,Integer> parent(){return super::adjustedTickDelay;}Function<Integer,Integer> reduced(){return A::reducedTickDelay;}}'
        ns,_=self.python(source);obj=ns['A']();Integer=pkg.load('java_stdlib.lang').Integer
        for name in ('bound','parent','reduced'):
            callback=getattr(obj,name)();result=callback.apply(Integer.valueOf(3));self.assertIsInstance(result,Integer);self.assertEqual(result.intValue(),2)
            with self.assertRaises(pkg.load('java_stdlib.lang').NullPointerException):callback.apply(None)
    def test_runtime_static_call_evaluates_null_expression_qualifier_once(self):
        source='class A extends Goal {int count;public boolean canUse(){return true;}Goal receiver(){count++;return null;}int run(int n){return receiver().reducedTickDelay(n);}}'
        ns,_=self.python(source);obj=ns['A']();self.assertEqual(obj.run(3),2);self.assertEqual(obj.count,1)
    def test_same_runtime_package_can_access_protected_instance_method(self):
        ns,_=helper.ArrayTests().python('package net.minecraft.world.entity.ai.goal;import net.minecraft.world.entity.ai.goal.Goal;class Logic {int run(Goal target){return target.adjustedTickDelay(3);}}')
        self.assertEqual(ns['Logic']().run(goals.Goal()),2)
    def test_reference_rejects_incompatible_boxed_return_type(self):
        with self.assertRaisesRegex(NeedsLowering,'result conversion is not Java invocation compatible'):
            self.python('import java.util.function.Function;class A extends Goal {public boolean canUse(){return true;}Function<Integer,String> make(){return this::adjustedTickDelay;}}')
    def test_contract_rejects_wrong_signature_and_static_instance_confusion(self):
        tag='net.minecraft.world.entity.ai.goal.Goal';parent=api.bind(tag,api.contracts()[tag])
        self.assertEqual(parent.reducedTickDelay(3,_nc_java_signature=('int',)),2)
        for operation in [lambda:parent().adjustedTickDelay(3,_nc_java_signature=()),lambda:api.invokeStatic(tag,'tick',(),()),lambda:api.invoke(tag,parent(),'reducedTickDelay',('int',),(3,))]:
            with self.assertRaises(TypeError):operation()
    def test_wrong_delay_argument_is_diagnosed_before_execution(self):
        with self.assertRaises(NeedsLowering):self.python('class A extends Goal {public boolean canUse(){return true;}int run(){return adjustedTickDelay(true);}}')
if __name__=='__main__':unittest.main()
