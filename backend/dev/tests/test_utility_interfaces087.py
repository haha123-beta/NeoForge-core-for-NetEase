import json,os,re,sys,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from java_interface_oracle import verify
from java_official_probe import native,run_original
from test_network086 import GROUPS
import test_official_interfaces086 as execution

class UtilityInterfaces087(unittest.TestCase):
    def test_all_seven_instance_contracts_original(self):
        contracts=Package().load('minecraft.utility_contracts').INTERFACE_CONTRACTS
        evidence=verify(contracts);self.assertEqual(len(contracts),7)
        (Path(__file__).parents[1]/'builds/utility_interfaces087_official_evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')

    def test_delta_and_null_command_constants_match_original(self):
        dt=native('net.minecraft.client.DeltaTracker');cs=native('net.minecraft.commands.CommandSource')
        expected=run_original('public class Probe {public static void main(String[] a){System.out.println('+dt+'.a.a()+","+'+dt+'.a.a(true)+","+'+dt+'.a.b()+","+'+dt+'.b.a()+","+'+dt+'.b.a(false)+","+'+dt+'.b.b());'+cs+'.a.a(null);System.out.println('+cs+'.a.k_()+","+'+cs+'.a.w_()+","+'+cs+'.a.M_()+","+'+cs+'.a.l_());}}',GROUPS).splitlines()
        p=Package();m=p.load('minecraft.utility_contracts');a=m.DeltaTracker.ZERO;b=m.DeltaTracker.ONE;c=m.CommandSource.NULL;c.sendSystemMessage(None)
        actual=[','.join(map(str,[a.getGameTimeDeltaTicks(),a.getGameTimeDeltaPartialTick(True),a.getRealtimeDeltaTicks(),b.getGameTimeDeltaTicks(),b.getGameTimeDeltaPartialTick(False),b.getRealtimeDeltaTicks()])),','.join(str(f()).lower() for f in [c.acceptsSuccess,c.acceptsFailure,c.shouldInformAdmins,c.alwaysAccepts])]
        self.assertEqual(actual,expected)

    def test_command_default_source_and_actual_python2(self):
        source='public class Run implements CommandSource {public void sendSystemMessage(Component c){}public boolean acceptsSuccess(){return true;}public boolean acceptsFailure(){return true;}public boolean shouldInformAdmins(){return true;}public int run(){return alwaysAccepts()?99:7;}}'
        original=source.replace('public class Run','class Run').replace('CommandSource',native('net.minecraft.commands.CommandSource')).replace('Component',native('net.minecraft.network.chat.Component'))
        for a,b in [('sendSystemMessage','a'),('acceptsSuccess','k_'),('acceptsFailure','w_'),('shouldInformAdmins','M_'),('alwaysAccepts','l_')]:original=re.sub(r'\b'+a+r'\(',b+'(',original)
        expected=run_original(original+'public class Probe {public static void main(String[] a){System.out.print(new Run().run());}}',GROUPS)
        execution.OfficialInterfaces086().execute('import net.minecraft.commands.CommandSource;import net.minecraft.network.chat.Component;'+source,expected)

    def test_reload_listener_name_source_and_actual_python2(self):
        source='import net.minecraft.server.packs.resources.PreparableReloadListener;public class Run implements PreparableReloadListener {public java.util.concurrent.CompletableFuture<java.lang.Void> reload(net.minecraft.server.packs.resources.PreparableReloadListener.PreparationBarrier b,net.minecraft.server.packs.resources.ResourceManager r,net.minecraft.util.profiling.ProfilerFiller p,net.minecraft.util.profiling.ProfilerFiller q,java.util.concurrent.Executor e,java.util.concurrent.Executor f){return null;}public int run(){return getName().length();}}'
        execution.OfficialInterfaces086().execute(source,'3')

    def test_loot_context_validation_delegates_and_empty_set_immutable(self):
        p=Package();m=p.load('minecraft.utility_contracts');lang=p.load('java_stdlib.lang')
        class User(m.LootContextUser):pass
        user=User();self.assertEqual(user.getReferencedContextParams().size(),0)
        with self.assertRaises(lang.UnsupportedOperationException):user.getReferencedContextParams().add('x')
        class Validation(object):
            def validateContextUsage(self,value):self.received=value
        v=Validation();user.validate(v);self.assertIs(v.received,user)
        with self.assertRaises(lang.NullPointerException):user.validate(None)

    def test_number_provider_java_float_rounding(self):
        values=['Float.NaN','Float.POSITIVE_INFINITY','Float.NEGATIVE_INFINITY','-0.5f','-1.5f','0.5f','1.49f','8388607.5f','2147483648f','-2147483648f','0.49999999f']
        expected=run_original('public class Probe {public static void main(String[] a){for(float n:new float[]{'+','.join(values)+'})System.out.println(Math.round(n));}}').splitlines()
        p=Package();m=p.load('minecraft.utility_contracts')
        class Provider(m.NumberProvider):
            def getFloat(self,context):return self.value
            def getType(self):return None
        q=Provider();actual=[]
        for n in [float('nan'),float('inf'),-float('inf'),-0.5,-1.5,0.5,1.49,8388607.5,2147483648.,-2147483648.,0.49999999]:q.value=n;actual.append(str(q.getInt(None)))
        self.assertEqual(actual,expected)

if __name__=='__main__':unittest.main()
