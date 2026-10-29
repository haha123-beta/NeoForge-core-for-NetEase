import os,sys,unittest,subprocess
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
from workspace_paths import DEV_ROOT
pkg=helper.pkg;goals=pkg.load('minecraft.goals')

class Probe(goals.Goal):
    def canUse(self):return True

class GoalContract(unittest.TestCase):
    def test_default_and_virtual_continuation(self):
        value=Probe();self.assertFalse(value.requiresUpdateEveryTick());self.assertTrue(value.canContinueToUse())
        self.assertTrue(value.isInterruptable())
    def test_get_flags_returns_live_collection(self):
        value=Probe();flags=value.getFlags();flags.add(goals.Goal.Flag.MOVE)
        self.assertIs(value.getFlags(),flags);self.assertIn(goals.Goal.Flag.MOVE,value.getFlags())
    def test_set_flags_updates_existing_collection(self):
        value=Probe();flags=value.getFlags();value.setFlags({goals.Goal.Flag.LOOK})
        self.assertIs(value.getFlags(),flags);self.assertEqual(flags,{goals.Goal.Flag.LOOK})
    def test_self_alias_set_flags_clears_before_add_all(self):
        value=Probe();value.getFlags().add(goals.Goal.Flag.MOVE);value.setFlags(value.getFlags())
        self.assertEqual(value.getFlags(),set())
    def test_null_flags_fail_after_clearing_live_set(self):
        value=Probe();value.getFlags().add(goals.Goal.Flag.MOVE)
        with self.assertRaises(pkg.load('java_stdlib.lang').NullPointerException):value.setFlags(None)
        self.assertEqual(value.getFlags(),set())
    def test_abstract_can_use_is_explicitly_unimplemented(self):
        with self.assertRaises(pkg.load('java_stdlib._base').UnsupportedOperationException):goals.Goal().canUse()
    def test_original_goal_api_parameter_calls(self):
        namespace,_=helper.ArrayTests().python('import net.minecraft.world.entity.ai.goal.Goal;class Logic {static boolean run(Goal value){value.start();value.tick();value.stop();return value.canContinueToUse();}}')
        self.assertTrue(namespace['Logic'].run(Probe()))
    def test_original_signed_minecraft_goal_jvm_matches_local_contract(self):
        root=DEV_ROOT/'references/minecraft-1.21.1';probe=root/'goal-jvm-probe';java=Path(r'E:\Java\jdk-21.0.10\bin\java.exe')
        if not java.is_file() or not (probe/'neocoreprobe/GoalProbeLauncher.class').is_file():self.skipTest('Original Minecraft Goal JVM probe unavailable')
        result=subprocess.run([str(java),'-cp',str(probe),'neocoreprobe.GoalProbeLauncher',str(root/'client.jar'),str(probe)],check=True,capture_output=True,text=True)
        value=Probe();before=value.getFlags();value.setFlags(value.getFlags())
        actual=':'.join(str(entry).lower() for entry in [value.requiresUpdateEveryTick(),value.getFlags() is value.getFlags(),before is value.getFlags(),value.canContinueToUse()])
        self.assertEqual(actual,result.stdout.strip());self.assertEqual(actual,'false:true:true:true')

if __name__=='__main__':unittest.main()
