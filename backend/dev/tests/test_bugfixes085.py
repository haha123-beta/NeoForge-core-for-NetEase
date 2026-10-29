import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from translate_java import translate
import test_interfaces082 as helpers
JDK=helpers.JDK

class BugFix085(unittest.TestCase):
    def test_functional_interface_default_method_jdk_and_real_python2(self):
        helpers.Interfaces082().compare({
            'api/Call.java':'package api;@FunctionalInterface public interface Call {int call(int x);default int twice(int x){return call(x)+call(x);}}',
            'use/Run.java':'package use;import api.Call;public class Run implements Call {public int call(int x){return x+1;}public int run(){return twice(3);}}'
        },'8')

    def test_invalid_sam_annotations_rejected_like_javac(self):
        for source in ('@FunctionalInterface interface Run {}','@FunctionalInterface @FunctionalInterface interface Run {int a();}','@FunctionalInterface interface Run {int a();int b();}', '@FunctionalInterface class Run {}', '@FunctionalInterface(x=1) interface Run {int a();}'):
            with self.subTest(source=source),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'source';root.mkdir();(root/'Run.java').write_text(source)
                report=translate(root,dry_run=True);self.assertEqual(report['manual_review'],1,report)
                run=subprocess.run([str(JDK/'javac.exe'),'-d',str(Path(tmp)/'classes'),str(root/'Run.java')],capture_output=True)
                self.assertNotEqual(run.returncode,0)

    def test_explicit_import_shadowing_and_annotation_runtime_use_stay_rejected(self):
        for source in ('import custom.FunctionalInterface;@FunctionalInterface interface Run {int a();}', '@FunctionalInterface interface Run {int a();}class Other {Class value=FunctionalInterface.class;}'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'Run.java').write_text(source)
                report=translate(root,dry_run=True);self.assertEqual(report['manual_review'],1,report)

    def test_generic_and_nested_parent_identity_does_not_erase_abi(self):
        cases=[('import net.minecraft.client.gui.screens.inventory.AbstractContainerScreen;class Run extends AbstractContainerScreen<String> {}','net.minecraft.client.gui.screens.inventory.AbstractContainerScreen','generic_superclass'),
               ('import net.minecraft.world.inventory.RecipeBookMenu;class Run extends RecipeBookMenu<String,String> {}','net.minecraft.world.inventory.RecipeBookMenu','generic_superclass'),
               ('import net.minecraft.world.entity.npc.VillagerTrades;class Run implements VillagerTrades.ItemListing {}','net.minecraft.world.entity.npc.VillagerTrades.ItemListing',None),
               ('class Run extends Enum<Run> {}','java.lang.Enum','generic_superclass')]
        for source,identity,category in cases:
            with self.subTest(identity=identity),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'demo';root.mkdir();(root/'Run.java').write_text('package demo;'+source)
                report=translate(Path(tmp),dry_run=True);row=report['results'][0]
                self.assertEqual(row['status'],'MANUAL_REVIEW')
                index=json.loads((Path(__file__).parents[1]/'java_import_index.json').read_text(encoding='utf-8'))
                if identity in index['runtime_interface_contracts']:self.assertIn('Unimplemented abstract interface method',row['reason'])
                else:self.assertIn(identity,row['reason'])
                self.assertNotIn('demo.'+identity.rsplit('.',1)[-1],row['reason'])
                if category:self.assertEqual(row['details']['category'],category);self.assertEqual(row['details']['resolved_name'],identity)

if __name__=='__main__':unittest.main()
