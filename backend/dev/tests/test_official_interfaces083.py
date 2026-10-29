import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from translate_java import translate
from build_source_bundle import collect_sources,core_bundle
from harness import Package
from workspace_paths import SCRIPTS_ROOT


class OfficialInterfaces083(unittest.TestCase):
    def test_original_java_interface_callback_and_abi_under_python2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';root.mkdir()
            text='import net.minecraft.client.gui.screens.recipebook.RecipeUpdateListener;interface Extra {default int value(){return 3;}} class Parent {public int n=1;} class Run extends Parent implements RecipeUpdateListener, Extra {public void recipesUpdated(){n+=value();}public net.minecraft.client.gui.screens.recipebook.RecipeBookComponent getRecipeBookComponent(){return null;}public int run(){RecipeUpdateListener listener=this;listener.recipesUpdated();return n;}}'
            (root/'Run.java').write_text(text)
            report=translate(root,Path(tmp)/'out')
            self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(1,0,0),report['results'])
            self.assertIn('neocore.runtime.RuntimeClasses@5',report['results'][0]['required_runtime_helpers'])
            sources=core_bundle()['sources'];sources.update(collect_sources(Path(tmp)/'out/source'))
            data={'loader_source':(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8'),'sources':sources,'module':'Run','class_name':'Run','expected':'4'}
            input=Path(tmp)/'probe.json';input.write_text(json.dumps(data),encoding='utf-8')
            run=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(Path(__file__).with_name('probe_interfaces082_python27.py')),str(input)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+'\n'+run.stderr)
            # Use the actual mapped vanilla interface, not a guessed contract stub.
            # The method name is read from official mappings below rather than assumed.
            mappings=(Path(r'D:\NeoCore工具\dev\references\minecraft-1.21.1/client_mappings.txt')).read_text(encoding='utf-8')
            block=mappings.split('net.minecraft.client.gui.screens.recipebook.RecipeUpdateListener -> ',1)[1].split('\n',2)
            native_name=block[0].rstrip(':')
            section=mappings.split('net.minecraft.client.gui.screens.recipebook.RecipeUpdateListener -> ',1)[1].split('\nnet.',1)[0]
            method=next(line.split(' -> ')[1].strip() for line in section.splitlines() if 'void recipesUpdated() -> ' in line)
            getter=next(line.split(' -> ')[1].strip() for line in section.splitlines() if ' getRecipeBookComponent() -> ' in line)
            book=mappings.split('net.minecraft.client.gui.screens.recipebook.RecipeBookComponent -> ',1)[1].split(':',1)[0]
            mapped=text.replace('import net.minecraft.client.gui.screens.recipebook.RecipeUpdateListener;','').replace('net.minecraft.client.gui.screens.recipebook.RecipeBookComponent',book).replace('RecipeUpdateListener',native_name).replace('recipesUpdated',method).replace('getRecipeBookComponent',getter)
            probe=root/'NeoCoreGoalProbe.java';probe.write_text(mapped+' public class NeoCoreGoalProbe {public static void main(String[] a){System.out.print(new Run().run());}}')
            jar=Path(r'D:\NeoCore工具\dev\references\minecraft-1.21.1/client.jar');classes=Path(tmp)/'classes';classes.mkdir();jdk=Path(r'E:\Java\jdk-21.0.10\bin')
            built=subprocess.run([str(jdk/'javac.exe'),'-cp',str(jar),'-d',str(classes),str(probe)],capture_output=True,text=True)
            self.assertEqual(built.returncode,0,built.stderr)
            launcher=jar.parent/'goal-jvm-probe'
            result=subprocess.run([str(jdk/'java.exe'),'-cp',str(launcher),'neocoreprobe.GoalProbeLauncher',str(jar),str(classes)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout,'4')

    def test_interface_contract_is_checked_not_stubbed(self):
        pkg=Package();classes=pkg.load('minecraft.runtime_classes').RuntimeClasses
        identity='net.minecraft.client.gui.screens.recipebook.RecipeUpdateListener'
        contract=classes.interfaceContracts()[identity];interface=classes.bindInterface(identity,contract)
        with self.assertRaises(TypeError):interface()
        contract['methods'][0]['return_type']='int'
        with self.assertRaises(RuntimeError):classes.bindInterface(identity,contract)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';root.mkdir();(root/'Run.java').write_text('import '+identity+';class Run implements RecipeUpdateListener {}')
            result=translate(root,dry_run=True)
            self.assertEqual(result['manual_review'],1);self.assertIn('Unimplemented abstract',result['results'][0]['reason'])


if __name__=='__main__':unittest.main()
