import os,re,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from java_official_probe import native,run_original
from test_network086 import GROUPS
from java_frontend import parse_source
from java_codegen import generate,NeedsLowering
from harness import Package
import test_official_interfaces086 as execution

class NativeSam087(unittest.TestCase):
    def compare(self,source,identities,replacements=()):
        original=source.replace('public class Run','class Run')
        for identity in identities:original=original.replace('import '+identity+';','')
        for identity in identities:original=re.sub(r'\b'+identity.rsplit('.',1)[-1]+r'\b',native(identity),original)
        for a,b in replacements:original=original.replace(a,b)
        expected=run_original(original+'public class Probe {public static void main(String[] a){System.out.print(new Run().run());}}',GROUPS)
        execution.OfficialInterfaces086().execute(source,expected)
        return expected

    def test_native_menu_constructor_lambda_context_and_call(self):
        identities=['net.minecraft.world.inventory.MenuConstructor','net.minecraft.world.inventory.AbstractContainerMenu']
        source=''.join('import '+i+';' for i in identities)+'public class Run {int n=0;public int run(){MenuConstructor c=(id,inv,player)->{n=id;return null;};AbstractContainerMenu m=c.createMenu(7,null,null);return n+(m==null?1:99);}}'
        self.assertEqual(self.compare(source,identities),'8')

    def test_native_menu_constructor_bound_method_reference(self):
        identities=['net.minecraft.world.inventory.MenuConstructor','net.minecraft.world.inventory.AbstractContainerMenu','net.minecraft.world.entity.player.Inventory','net.minecraft.world.entity.player.Player']
        source=''.join('import '+i+';' for i in identities)+'public class Run {int n=0;public AbstractContainerMenu create(int id,Inventory inv,Player p){n=id;return null;}public int run(){MenuConstructor c=this::create;c.createMenu(4,null,null);return n;}}'
        self.assertEqual(self.compare(source,identities),'4')

    def test_generic_ticker_lambda_reference_types_and_primitive_context(self):
        identities=['net.minecraft.world.level.block.entity.BlockEntityTicker','net.minecraft.world.level.block.entity.BlockEntity','net.minecraft.core.BlockPos']
        source=''.join('import '+i+';' for i in identities)+'public class Run {int n=0;public int run(){BlockEntityTicker<BlockEntity> t=(level,pos,state,entity)->{n=n+1;};t.tick(null,new BlockPos(1,2,3),null,null);return n;}}'
        self.assertEqual(self.compare(source,identities),'1')

    def test_generic_constructor_reference_is_lazy_and_proves_return_bound(self):
        identities=['net.minecraft.client.gui.screens.inventory.MenuAccess','net.minecraft.world.inventory.AbstractContainerMenu','net.minecraft.world.entity.player.Player','net.minecraft.world.item.ItemStack']
        source=''.join('import '+i+';' for i in identities)+'class Sample extends AbstractContainerMenu {Sample(){super(null,1);}public boolean stillValid(Player p){return true;}public ItemStack quickMoveStack(Player p,int i){return null;}}public class Run {public int run(){MenuAccess<Sample> a=Sample::new;return a==null?99:7;}}'
        # Compile and execute the real interface/constructor-reference creation.
        self.assertEqual(self.compare(source,identities,[('stillValid(','b('),('quickMoveStack(','b(')]),'7')

    def test_nonfunctional_wrong_parameter_and_wrong_method_return_reject(self):
        for source in [
          'import net.minecraft.world.level.entity.EntityTypeTest;class Run {EntityTypeTest<Object,String> t=x->null;}',
          'import net.minecraft.world.inventory.MenuConstructor;class Run {MenuConstructor t=(String id,net.minecraft.world.entity.player.Inventory i,net.minecraft.world.entity.player.Player p)->null;}',
          'import net.minecraft.world.inventory.MenuConstructor;class Run {MenuConstructor t=(id,i,p)->1;}',
          'import net.minecraft.world.inventory.MenuConstructor;class Run {int wrong(int id,net.minecraft.world.entity.player.Inventory i,net.minecraft.world.entity.player.Player p){return 1;}MenuConstructor t=this::wrong;}']:
            with self.subTest(source=source),self.assertRaises(NeedsLowering):generate(parse_source(source))

if __name__=='__main__':unittest.main()
