import hashlib,json,os,subprocess,sys,unittest,zipfile
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from java_official_probe import JDK
from java_platform_probe import run_original as run_platform_original
from test_network086 import GROUPS
from java_codegen import generate,NeedsLowering
from java_frontend import parse_source,api_index
from harness import Package
import test_official_interfaces086 as execution

IMPORTS='import net.minecraft.world.inventory.AbstractContainerMenu;import net.minecraft.world.inventory.MenuType;import net.minecraft.world.entity.player.Inventory;import net.minecraft.world.entity.player.Player;import net.minecraft.world.item.ItemStack;import net.minecraft.network.RegistryFriendlyByteBuf;import net.neoforged.neoforge.common.extensions.IMenuTypeExtension;import net.neoforged.neoforge.network.IContainerFactory;import net.minecraft.world.flag.FeatureFlags;'
SAMPLE='class Sample extends AbstractContainerMenu {int value;Sample(int id,Inventory inv,RegistryFriendlyByteBuf data){super(null,id);value=id;}public int value(){return value;}public boolean stillValid(Player p){return true;}public ItemStack quickMoveStack(Player p,int slot){return null;}}'
# Java fields and methods have distinct namespaces; keep this fixture independent
# of that separate lowering requirement.
SAMPLE=SAMPLE.replace('int value;','int saved;').replace('value=id;','saved=id;').replace('return value;','return saved;')

class MenuFactories087(unittest.TestCase):
    def test_pinned_original_sources_and_public_patched_supplier_binary(self):
        dev=Path(__file__).parents[1];source=dev/'references/neoforge-21.1.233-sources.jar'
        jar=Path(r'F:\PCL\.minecraft\libraries\net\neoforged\neoforge\21.1.233\neoforge-21.1.233-client.jar')
        p=subprocess.run([str(JDK/'javap.exe'),'-p','-s','-classpath',str(jar),'net.minecraft.world.inventory.MenuType$MenuSupplier'],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr);self.assertIn('public interface ',p.stdout);self.assertIn('create(int, net.minecraft.world.entity.player.Inventory)',p.stdout)
        with zipfile.ZipFile(source) as z:
            a=z.read('net/neoforged/neoforge/network/IContainerFactory.java').decode();b=z.read('net/neoforged/neoforge/common/extensions/IMenuTypeExtension.java').decode()
        self.assertIn('return create(p_create_1_, p_create_2_, null);',a);self.assertIn('new MenuType<>(factory, FeatureFlags.DEFAULT_FLAGS)',b)
        evidence={'source_jar_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'patched_client_sha256':hashlib.sha256(jar.read_bytes()).hexdigest(),'supplier_javap':p.stdout,'IContainerFactory':a,'IMenuTypeExtension':b,'limit':'Original platform declarations verified; this is not execution of the NeoForge loader or a game.'}
        (dev/'references/checkpoint-0.8.7/menu_interfaces_original.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')

    def test_static_generic_menu_factory_constructor_reference_actual_python2(self):
        source=IMPORTS+SAMPLE+'public class Run {public int run(){MenuType<Sample> t=IMenuTypeExtension.create(Sample::new);Sample a=t.create(7,null);Sample b=t.create(9,null,null);return a.value()+b.value()+(t.requiredFeatures().equals(FeatureFlags.DEFAULT_FLAGS)?1:99)+(t.isEnabled(FeatureFlags.DEFAULT_FLAGS)?1:99);}}'
        execution.OfficialInterfaces086().execute(source,'18')

    def test_original_platform_default_factory_executes_and_matches_python(self):
        source='import net.neoforged.neoforge.network.IContainerFactory;import net.minecraft.world.inventory.AbstractContainerMenu;public class Probe {public static void main(String[] a){IContainerFactory<AbstractContainerMenu> f=(id,inv,data)->{System.out.println(id+","+(data==null));return null;};f.create(3,null);f.create(5,null,null);}}'
        expected=run_platform_original(source,GROUPS).splitlines()
        p=Package();n=p.load('minecraft.network_contracts');fn=p.load('java_stdlib.function').Functional;actual=[]
        contract=n.specialize('net.neoforged.neoforge.network.IContainerFactory',['net.minecraft.world.inventory.AbstractContainerMenu'])
        def create(i,inv,data):actual.append(str(i)+','+str(data is None).lower());return None
        factory=fn.make(contract,create,3);factory.create(3,None);factory.create(5,None,None)
        self.assertEqual(actual,expected)

    def test_source_factory_default_two_arguments_and_typed_static_factory(self):
        source=IMPORTS+SAMPLE+'class Factory implements IContainerFactory<Sample> {public Sample create(int id,Inventory inv,RegistryFriendlyByteBuf data){return new Sample(id,inv,data);}}public class Run {public int run(){IContainerFactory<Sample> f=new Factory();Sample a=f.create(3,null);MenuType<Sample> t=IMenuTypeExtension.create(f);Sample b=t.create(5,null,null);return a.value()+b.value();}}'
        execution.OfficialInterfaces086().execute(source,'8')

    def test_native_factory_extra_data_default_and_supplier_fallback(self):
        p=Package();m=p.load('neoforge.menu_interfaces');menu=p.load('minecraft.menu');flags=p.load('minecraft.feature_flags');runtime=p.load('minecraft.runtime_classes').RuntimeClasses;fn=p.load('java_stdlib.function').Functional
        net=p.load('minecraft.network_contracts');bound=net.specialize(m.FACTORY,['net.minecraft.world.inventory.AbstractContainerMenu'])
        class Entry(menu.AbstractContainerMenu):
            def __init__(self,i,inv,data):menu.AbstractContainerMenu.__init__(self,None,i);self.saved=i;self.extra=data
            def quickMoveStack(self,player,index):return None
            def stillValid(self,player):return True
        calls=[];factory=fn.make(bound,lambda i,inv,data:calls.append((i,inv,data)) or Entry(i,inv,data),3)
        t=m.IMenuTypeExtension._nc_createType(factory);sent=object()
        self.assertEqual(t.create(2,None).saved,2);self.assertIs(t.create(4,None,sent).extra,sent)
        self.assertEqual(calls,[(2,None,None),(4,None,sent)]);self.assertIs(t.requiredFeatures(),flags.FeatureFlags.DEFAULT_FLAGS)
        self.assertIsInstance(t,m.IMenuTypeExtension);self.assertIsInstance(factory,m.MenuSupplier)
        supplier=fn.make(net.specialize(m.SUPPLIER,['net.minecraft.world.inventory.AbstractContainerMenu']),lambda i,inv:Entry(i+3,inv,None),2)
        self.assertEqual(menu.MenuType(supplier).create(2,None,sent).saved,5)

    def test_invalid_factory_bound_and_constructor_arity_remain_diagnostics(self):
        known,_=api_index()
        for source in [
            IMPORTS+'class Other {}class Run {Object run(){return IMenuTypeExtension.create(Other::new);}}',
            IMPORTS+'class Run {Object run(){IContainerFactory<String> f=null;return IMenuTypeExtension.create(f);}}',
            IMPORTS+SAMPLE+'class Run {Object run(){return IMenuTypeExtension.create(Run::new);}}']:
            with self.subTest(source=source),self.assertRaises(NeedsLowering):generate(parse_source(source,known_types=known))

if __name__=='__main__':unittest.main()
