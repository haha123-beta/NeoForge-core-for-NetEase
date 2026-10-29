import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from translate_java import translate
from run_translation_job import run_job
from build_source_bundle import core_bundle,content_bundle
from harness import Package

FILES={
'META-INF/neoforge.mods.toml':'modLoader="javafml"\nloaderVersion="[4,)"\nlicense="MIT"\n[[mods]]\nmodId="native_menu_example"\nversion="1"\n[[mixins]]\nconfig="native.mixins.json"\n',
'native.mixins.json':json.dumps({'required':True,'package':'nativehooks','mixins':['Hooks']}),
'nativecontent/Audit.java':'package nativecontent;public class Audit {public static int tails=0;public static int seen=0;}',
'nativecontent/Example.java':'''package nativecontent;
import net.minecraft.world.inventory.AbstractContainerMenu;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
public class Example extends AbstractContainerMenu {
 public int body=0;
 public Example(int id){super(null,id);body=Audit.tails;}
 public boolean stillValid(Player p){return true;}
 public ItemStack quickMoveStack(Player p,int index){return null;}
}''',
'nativecontent/Main.java':'''package nativecontent;import net.neoforged.fml.common.Mod;
@Mod("native_menu_example") public class Main {public Example menu=new Example(7);public int seen=Audit.tails;public Main(){}}''',
'nativehooks/Hooks.java':'''package nativehooks;
import nativecontent.Audit;
import net.minecraft.world.inventory.AbstractContainerMenu;
import net.minecraft.world.inventory.MenuType;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mutable;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
@Mixin(AbstractContainerMenu.class) public class Hooks {
 @Shadow @Final @Mutable private MenuType<?> menuType;
 @Inject(method="<init>",at=@At("TAIL"))
 private void onInit(MenuType<?> type,int windowId,CallbackInfo ci){this.menuType=null;Audit.tails=Audit.tails+1;Audit.seen=windowId;}
}'''}

def fixture(root):
    for name,text in FILES.items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')

class NativeMixinTests(unittest.TestCase):
    def test_native_handler_is_compiled_registered_before_entry_and_removed_on_close(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'original';root.mkdir();fixture(root)
            config=Path(folder)/'job.json';config.write_text(json.dumps({'input':str(root),'output_root':str(Path(folder)/'out'),'distribution':{'pack_id':'native_menu_content'}}),encoding='utf-8')
            job=run_job(config);self.assertEqual(job['status'],'PACKAGED_REVIEW_REQUIRED',job)
            content=content_bundle(Path(job['output'])/'converted/original',job['discovered_entrypoints']);core=core_bundle()
            self.assertEqual(content['mods'][0]['runtime_mixin_bindings'][0]['handler'],'onInit')
            runtime=Package().load('core.source_modules').SourceModuleLoader(core['sources'])
            session=runtime.load('core.bundled_mods').BundledModSession(core['sources'],[content],runtime=runtime)
            try:
                results=session.loader.activate();self.assertTrue(results['native_menu_example']['ready'],results)
                state=session.loader.contexts['native_menu_example'].instance
                self.assertEqual((state.menu.containerId,state.menu.body,state.seen),(7,1,1))
                hooks=runtime.load('neoforge.mixin_hooks');self.assertEqual(hooks.MixinHooks.count(),1)
                original_type=runtime.load('minecraft.menu').MenuType()
                obj=runtime.load('minecraft.menu').AbstractContainerMenu(original_type,8)
                self.assertIsNone(obj.menuType)
                self.assertEqual(runtime.load('nativecontent.Audit').Audit.seen,8)
                session.close();self.assertEqual(hooks.MixinHooks.count(),0)
                obj=runtime.load('minecraft.menu').AbstractContainerMenu(original_type,9);self.assertIs(obj.menuType,original_type)
            finally:session.close();runtime.close()

if __name__=='__main__':unittest.main()
