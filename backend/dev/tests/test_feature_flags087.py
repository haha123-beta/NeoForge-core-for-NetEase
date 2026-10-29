import json,os,re,sys,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from java_official_probe import native,run_original
from java_interface_oracle import verify
from harness import Package
from test_network086 import GROUPS
import test_official_interfaces086 as execution

class FeatureFlags087(unittest.TestCase):
    def test_original_bitsets_hash_and_set_algebra(self):
        flag=native('net.minecraft.world.flag.FeatureFlag');kind=native('net.minecraft.world.flag.FeatureFlagSet');flags=native('net.minecraft.world.flag.FeatureFlags')
        source='public class Probe {public static void main(String[] a){'+flag+'[] f={'+flags+'.a,'+flags+'.b,'+flags+'.c};'+kind+'[] sets=new '+kind+'[8];for(int m=0;m<8;m++){sets[m]='+kind+'.a();for(int i=0;i<3;i++)if((m&(1<<i))!=0)sets[m]=sets[m].c('+kind+'.a(f[i]));}for('+kind+' x:sets){System.out.println(x.b()+","+x.b(f[0])+","+x.b(f[1])+","+x.hashCode()+","+'+flags+'.a(x));for('+kind+' y:sets)System.out.println(x.a(y)+","+x.b(y)+","+x.c(y).hashCode()+","+x.d(y).hashCode());}}}'
        expected=run_original(source,GROUPS).splitlines();p=Package();m=p.load('minecraft.feature_flags');f=[m.FeatureFlags.VANILLA,m.FeatureFlags.BUNDLE,m.FeatureFlags.TRADE_REBALANCE];sets=[m.FeatureFlagSet.of(*[f[i] for i in range(3) if mask&(1<<i)]) for mask in range(8)];actual=[]
        def line(values):return ','.join(str(v).lower() if isinstance(v,bool) else str(v) for v in values)
        for x in sets:
            actual.append(line([x.isEmpty(),x.contains(f[0]),x.contains(f[1]),x.hashCode(),m.FeatureFlags.isExperimental(x)]))
            for y in sets:actual.append(line([x.isSubsetOf(y),x.intersects(y),x.join(y).hashCode(),x.subtract(y).hashCode()]))
        self.assertEqual(actual,expected)

    def test_feature_element_original_contract_and_default_source_python2(self):
        p=Package();m=p.load('minecraft.feature_flags');evidence=verify(m.INTERFACE_CONTRACTS)
        (Path(__file__).parents[1]/'builds/feature_flags087_official_evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        identities=['net.minecraft.world.flag.FeatureElement','net.minecraft.world.flag.FeatureFlagSet','net.minecraft.world.flag.FeatureFlags']
        body='public class Run implements FeatureElement {public FeatureFlagSet requiredFeatures(){return FeatureFlagSet.of(FeatureFlags.VANILLA,FeatureFlags.BUNDLE);}public int run(){return isEnabled(FeatureFlags.DEFAULT_FLAGS)?99:(isEnabled(FeatureFlagSet.of(FeatureFlags.VANILLA,FeatureFlags.BUNDLE))?7:99);}}'
        original=body.replace('public class Run','class Run')
        for identity in identities:original=re.sub(r'\b'+identity.rsplit('.',1)[-1]+r'\b',native(identity),original)
        original=original.replace('requiredFeatures(','i(').replace('isEnabled(','a(').replace('.of(','.a(').replace('.VANILLA','.a').replace('.BUNDLE','.b').replace('.DEFAULT_FLAGS','.g')
        expected=run_original(original+'public class Probe {public static void main(String[] a){System.out.print(new Run().run());}}',GROUPS)
        execution.OfficialInterfaces086().execute(''.join('import '+i+';' for i in identities)+body,expected)

    def test_null_short_circuit_semantics_match_original(self):
        kind=native('net.minecraft.world.flag.FeatureFlagSet')
        source='public class Probe {public static void main(String[] a){'+kind+' e='+kind+'.a();System.out.print(e.a(('+kind+')null)+","+e.b(('+kind+')null)+","+(e.c(null)==null)+","+(e.d(null)==e));}}'
        expected=run_original(source,GROUPS);p=Package();m=p.load('minecraft.feature_flags');e=m.FeatureFlagSet.of()
        self.assertEqual(','.join(str(v).lower() for v in [e.isSubsetOf(None),e.intersects(None),e.join(None) is None,e.subtract(None) is e]),expected)
        lang=p.load('java_stdlib.lang')
        with self.assertRaises(lang.NullPointerException):e.contains(None)
        foreign=m.FeatureFlag(m._Universe('foreign'),0);other=m.FeatureFlagSet.of(foreign);normal=m.FeatureFlagSet.of(m.FeatureFlags.VANILLA)
        with self.assertRaises(lang.IllegalArgumentException):other.join(normal)
        with self.assertRaises(lang.IllegalArgumentException):other.subtract(normal)
        with self.assertRaises(lang.IllegalStateException):m.FeatureFlagSet.of(foreign,m.FeatureFlags.VANILLA)
        self.assertFalse(other.isSubsetOf(normal));self.assertFalse(other.intersects(normal))

if __name__=='__main__':unittest.main()
