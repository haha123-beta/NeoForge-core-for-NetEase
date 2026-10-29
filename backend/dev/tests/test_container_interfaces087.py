import json,os,re,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from java_interface_oracle import verify
from java_official_probe import native,run_original
import test_official_interfaces086 as execution
from test_network086 import GROUPS
from translate_java import translate

BODY='public class Run implements Container {public int getContainerSize(){return 0;}public boolean isEmpty(){return true;}public ItemStack getItem(int i){return null;}public ItemStack removeItem(int i,int n){return null;}public ItemStack removeItemNoUpdate(int i){return null;}public void setItem(int i,ItemStack s){}public void setChanged(){}public boolean stillValid(Player p){return true;}public void clearContent(){}public int run(){return getMaxStackSize()+(canPlaceItem(0,null)?1:0)+(canTakeItem(this,0,null)?1:0)+countItem(null);}}'

class ContainerInterfaces087(unittest.TestCase):
    def test_new_callback_and_container_signatures_against_original_jar(self):
        package=Package();contracts={}
        for module in ('minecraft.container_contracts','minecraft.callback_contracts'):contracts.update(package.load(module).INTERFACE_CONTRACTS)
        self.assertEqual(len(contracts),22)
        evidence=verify(contracts)
        (Path(__file__).parents[1]/'builds/interfaces087_official_evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')

    def test_default_container_calls_original_jdk_and_actual_python2(self):
        original=BODY.replace('public class Run','class Run')
        for name,official in [('Container','net.minecraft.world.Container'),('ItemStack','net.minecraft.world.item.ItemStack'),('Player','net.minecraft.world.entity.player.Player')]:original=re.sub(r'\b'+name+r'\b',native(official),original)
        names={'getContainerSize':'b','isEmpty':'c','getItem':'a','removeItem':'a','removeItemNoUpdate':'b','setItem':'a','setChanged':'e','stillValid':'a','clearContent':'a','getMaxStackSize':'al_','canPlaceItem':'b','canTakeItem':'a','countItem':'a_'}
        for name,mapped in names.items():original=re.sub(r'\b'+name+r'\(',mapped+'(',original)
        # Obfuscated countItem and hasAnyMatching share a name; disambiguate null
        # without changing the original countItem invocation.
        original=original.replace('a_(null)','a_(('+native('net.minecraft.world.item.Item')+')null)')
        expected=run_original(original+'public class Probe {public static void main(String[] a){System.out.print(new Run().run());}}',GROUPS)
        self.assertEqual(expected,'101')
        execution.OfficialInterfaces086().execute('import net.minecraft.world.Container;import net.minecraft.world.item.ItemStack;import net.minecraft.world.entity.player.Player;'+BODY,expected)

    def test_all_abstract_methods_remain_required_and_no_renderer_success_stubs(self):
        package=Package();contracts={}
        for module in ('minecraft.container_contracts','minecraft.callback_contracts'):contracts.update(package.load(module).INTERFACE_CONTRACTS)
        for name in contracts:
            with self.subTest(interface=name),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'Run.java').write_text('class Run implements '+name+' {}')
                report=translate(root,dry_run=True)
                self.assertEqual((report['manual_review'],report['failed']),(1,0),report)

    def test_container_defaults_count_empty_filter_and_subclass_max(self):
        p=Package();contracts=p.load('minecraft.container_contracts');b=p.load('minecraft.block_entity');i=p.load('minecraft.item');sets=p.load('java_stdlib.util');l=p.load('java_stdlib.lang')
        a=i.Item();c=b.SimpleContainer(2);c.setItem(0,i.ItemStack(a,3))
        self.assertIsInstance(c,contracts.Container);self.assertEqual(c.countItem(a),3)
        selected=sets.JavaSet();selected.add(a)
        self.assertTrue(c.hasAnyOf(selected));self.assertFalse(c.hasAnyMatching(lambda stack:False))
        with self.assertRaises(l.NullPointerException):c.getMaxStackSize(None)
        class Limited(b.SimpleContainer):
            def getMaxStackSize(self,*args):
                return 2 if not args else contracts.Container.getMaxStackSize(self,*args)
        c=Limited(0);self.assertEqual(c.getMaxStackSize(i.ItemStack(a,5)),2)
        c=b.SimpleContainer(0);self.assertFalse(c.hasAnyMatching(None));self.assertFalse(c.hasAnyOf(None))

if __name__=='__main__':unittest.main()
