import json,os,re,sys,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from java_interface_oracle import verify
from java_generic_contracts import proves_bound,specialize
from java_frontend import parse_source,api_index
from java_project_types import add_unit
from java_official_probe import native,run_original
import test_official_interfaces086 as execution

class GenericInterfaces087(unittest.TestCase):
    def test_generic_original_contracts_and_deep_runtime_substitution_match(self):
        p=Package();c=p.load('minecraft.callback_contracts').GENERIC_INTERFACES
        evidence=verify(c);self.assertEqual(len(c),4)
        (Path(__file__).parents[1]/'builds/generic_interfaces087_official_evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        runtime=p.load('minecraft.network_contracts')
        for identity,arguments in [
            ('net.minecraft.client.renderer.entity.EntityRendererProvider',['net.minecraft.world.entity.Entity']),
            ('net.minecraft.world.level.entity.EntityTypeTest',['java.lang.Object','java.lang.String'])]:
            self.assertEqual(specialize(c[identity],arguments),runtime.specialize(identity,arguments))
        row=specialize(c['net.minecraft.world.level.entity.EntityTypeTest'],['java.lang.Object','java.lang.String'])
        self.assertEqual(row['methods'][1]['return_type'],'java.lang.Class<? extends java.lang.Object>')

    def test_declared_native_and_cross_package_source_bounds_without_loading_mods(self):
        known,_=api_index();index={}
        ir=parse_source('package other;import net.minecraft.world.level.block.entity.AbstractFurnaceBlockEntity;abstract class Furnace extends AbstractFurnaceBlockEntity {}','other/Furnace.java',known)
        add_unit(index,ir)
        self.assertTrue(proves_bound('other.Furnace','net.minecraft.world.level.block.entity.BlockEntity',{'package':'use','imports':[]},index))
        self.assertFalse(proves_bound('other.Furnace','net.minecraft.world.entity.Entity',{'package':'use','imports':[]},index))
        self.assertTrue(proves_bound('net.minecraft.world.entity.projectile.AbstractArrow','net.minecraft.world.entity.Entity',{},{}))
        self.assertFalse(proves_bound('java.lang.String','net.minecraft.world.level.block.entity.BlockEntity',{},{}))

    def test_generic_interface_variable_calls_actual_python2_and_original(self):
        source='public class Run implements EntityTypeTest<Object,String> {public String tryCast(Object o){return (String)o;}public Class<? extends Object> getBaseClass(){return null;}public int run(){EntityTypeTest<Object,String> t=this;return t.tryCast("yes").length();}}'
        original=source.replace('public class Run','class Run').replace('EntityTypeTest',native('net.minecraft.world.level.entity.EntityTypeTest'))
        original=re.sub(r'\btryCast\(', 'a(',original);original=re.sub(r'\bgetBaseClass\(', 'a(',original)
        expected=run_original(original+'public class Probe {public static void main(String[] a){System.out.print(new Run().run());}}')
        self.assertEqual(expected,'3')
        execution.OfficialInterfaces086().execute('import net.minecraft.world.level.entity.EntityTypeTest;'+source,expected)

    def test_menu_access_typed_variable_actual_python2(self):
        execution.OfficialInterfaces086().execute('import net.minecraft.client.gui.screens.inventory.MenuAccess;import net.minecraft.world.inventory.AbstractContainerMenu;public class Run implements MenuAccess<AbstractContainerMenu> {public AbstractContainerMenu getMenu(){return null;}public int run(){MenuAccess<AbstractContainerMenu> x=this;return x.getMenu()==null?7:99;}}','7')

if __name__=='__main__':unittest.main()
