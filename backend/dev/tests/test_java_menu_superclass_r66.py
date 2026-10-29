import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from translate_java import translate
from build_source_bundle import core_bundle,collect_sources
from harness import Package

SOURCE='''package menus;
import net.minecraft.world.inventory.AbstractContainerMenu;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
public class Example extends AbstractContainerMenu {
 public int seen=0;
 public Example(int id){super(null,id);seen=getStateId()+3;}
 public boolean stillValid(Player player){return true;}
 public ItemStack quickMoveStack(Player player,int index){return null;}
 public int run(){return seen+incrementStateId();}
}'''

class MenuSuperclassTests(unittest.TestCase):
    def generate(self,source=SOURCE,caller=None):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'original';(root/'menus').mkdir(parents=True)
            (root/'menus/Example.java').write_text(source,encoding='utf-8')
            if caller:(root/'menus/Caller.java').write_text(caller,encoding='utf-8')
            report=translate(root,Path(folder)/'out')
            return report,collect_sources(Path(folder)/'out/original')
    def test_menu_constructor_fields_methods_and_independent_instances(self):
        report,sources=self.generate();self.assertEqual((report['manual_review'],report['failed']),(0,0),report)
        self.assertIn('neocore.runtime.RuntimeClasses@4',report['results'][0]['required_runtime_helpers'])
        all_sources=core_bundle()['sources'];all_sources.update(sources)
        runtime=Package().load('core.source_modules').SourceModuleLoader(all_sources)
        api=runtime.load('core.java_api');scope=api.JavaApiImports(runtime).install(api.collect_java_api())
        try:
            cls=runtime.load('menus.Example').Example;a=cls(7);b=cls(9)
            self.assertEqual((a.run(),a.run(),b.run()),(4,5,4))
            self.assertEqual((a.containerId,b.containerId),(7,9))
            self.assertTrue(a.stillValid(None));self.assertIsNone(a.quickMoveStack(None,0))
            a.removed(None);self.assertTrue(a.isRemoved());self.assertFalse(b.isRemoved())
        finally:scope.close();runtime.close()
    def test_abstract_methods_and_wrong_constructor_are_not_accepted(self):
        for source in (SOURCE.replace('public boolean stillValid(Player player){return true;}',''),SOURCE.replace('super(null,id)','super(null,true)')):
            report,_=self.generate(source);self.assertGreater(report['manual_review'],0)
    def test_other_file_receiver_retains_runtime_parent_methods(self):
        caller='''package menus;public class Caller {
 public static int advance(Example menu){menu.suppressRemoteUpdates();menu.resumeRemoteUpdates();return menu.incrementStateId()+menu.getItems().size();}
}'''
        report,sources=self.generate(caller=caller)
        self.assertEqual((report['manual_review'],report['failed']),(0,0),report)
        all_sources=core_bundle()['sources'];all_sources.update(sources)
        runtime=Package().load('core.source_modules').SourceModuleLoader(all_sources)
        api=runtime.load('core.java_api');scope=api.JavaApiImports(runtime).install(api.collect_java_api())
        try:
            menu=runtime.load('menus.Example').Example(7)
            caller=runtime.load('menus.Caller').Caller
            self.assertEqual((caller.advance(menu),caller.advance(menu)),(1,2))
        finally:scope.close();runtime.close()

if __name__=='__main__':unittest.main()
