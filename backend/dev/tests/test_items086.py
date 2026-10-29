import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from translate_java import translate
from build_source_bundle import core_bundle,collect_sources
from workspace_paths import SCRIPTS_ROOT
from java_official_probe import mapping
from harness import Package

class Items086(unittest.TestCase):
    def test_official_constructor_signatures_and_source_subclass_actual_python2(self):
        self.assertIn('void <init>(net.minecraft.world.item.Item$Properties)',mapping('net.minecraft.world.item.Item'))
        self.assertIn('void <init>(net.minecraft.world.level.block.Block,net.minecraft.world.item.Item$Properties)',mapping('net.minecraft.world.item.BlockItem'))
        files={'Thing.java':'package demo;import net.minecraft.world.item.Item;public class Thing extends Item {public Thing(){super(new Item.Properties().fireResistant().stacksTo(3));}public int count(){return getDefaultMaxStackSize();}}',
               'Placed.java':'package demo;import net.minecraft.world.item.BlockItem;import net.minecraft.world.item.Item;public class Placed extends BlockItem {public Placed(){super(null,new Item.Properties().stacksTo(7));}}',
               'Run.java':'package demo;import net.minecraft.world.item.Item;public class Run {public int run(){Thing a=new Thing();Placed b=new Placed();Item plain=new Item(new Item.Properties().stacksTo(4));if(b.getBlock()!=null)return 99;if(a.asItem()!=a)return 100;return a.count()+b.getDefaultMaxStackSize()+plain.getDefaultMaxStackSize();}}'}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';(root/'demo').mkdir(parents=True)
            for name,text in files.items():(root/'demo'/name).write_text(text)
            report=translate(root,Path(tmp)/'out');self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(3,0,0),report['results'])
            self.assertTrue(any('neocore.runtime.RuntimeClasses@6' in r['required_runtime_helpers'] for r in report['results']))
            sources=core_bundle()['sources'];sources.update(collect_sources(Path(tmp)/'out/source'))
            data={'loader_source':(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8'),'sources':sources,'module':'demo.Run','class_name':'Run','expected':'14'}
            path=Path(tmp)/'data.json';path.write_text(json.dumps(data),encoding='utf-8')
            run=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(Path(__file__).with_name('probe_interfaces082_python27.py')),str(path)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+'\n'+run.stderr)

    def test_property_snapshot_damage_invariant_and_identity(self):
        p=Package();item=p.load('minecraft.item');runtime=p.load('minecraft.runtime_classes').RuntimeClasses;l=p.load('java_stdlib.lang')
        props=item.ItemProperties().stacksTo(3);contract=runtime.contracts()['net.minecraft.world.item.Item'];cls=runtime.bind('net.minecraft.world.item.Item',contract);a=cls(props);props.stacksTo(9)
        self.assertEqual(a.getDefaultMaxStackSize(),3);self.assertIs(a.asItem(),a)
        self.assertEqual(a.hashCode(),l.System.identityHashCode(a));self.assertFalse(a.equals(cls(item.ItemProperties())))
        props=item.ItemProperties().durability(-1)
        self.assertEqual(props.getMaxStackSize(),1);self.assertFalse(props.isUnbreakable())
        with self.assertRaises(l.IllegalStateException):cls(props.stacksTo(2))
        with self.assertRaises(l.NullPointerException):cls(None)
        self.assertIsNone(cls(item.ItemProperties()).getCraftingRemainingItem())

    def test_wrong_constructor_storage_collision_and_world_apis_stay_rejected(self):
        sources=['import net.minecraft.world.item.Item;class Run extends Item {int properties;Run(){super(new Item.Properties());}}','import net.minecraft.world.item.Item;class Run extends Item {Run(){super(true);}}','import net.minecraft.world.item.BlockItem;class Run extends BlockItem {Run(){super(null,null);}void bad(){super.place(null);}}']
        for source in sources:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'Run.java').write_text(source);r=translate(root,dry_run=True);self.assertEqual((r['manual_review'],r['failed']),(1,0),r)

if __name__=='__main__':unittest.main()
