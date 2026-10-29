import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run_translation_job import run_job
from build_source_bundle import core_bundle,content_bundle
from harness import Package
import test_native_mixin_lowering_r69 as previous

def fixture(root,prefix,fail=False):
    for name,body in previous.FILES.items():
        name=name.replace('nativecontent',prefix+'content').replace('nativehooks',prefix+'hooks')
        body=body.replace('nativecontent',prefix+'content').replace('nativehooks',prefix+'hooks').replace('native_menu_example',prefix+'_native_menu')
        if name.endswith('/Hooks.java'):
            body=body.replace('import '+prefix+'content.Audit;','import '+prefix+'content.Audit;import '+prefix+'content.Example;')
            start=body.index('{this.menuType=null;')
            body=body[:start]+body[start:].replace('{this.menuType=null;','{if(((Object)this) instanceof Example){this.menuType=null;',1).replace('Audit.seen=windowId;}','Audit.seen=windowId;}}',1)
            if fail:body=body.replace('Audit.seen=windowId;','throw new IllegalStateException("second owner failure");')
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body,encoding='utf-8')

class NativeOwnerTests(unittest.TestCase):
    def test_owners_match_original_instanceof_filter_and_close_independently(self):
        self.exercise(False)
    def test_failed_owner_does_not_remove_successful_owner_hook(self):
        self.exercise(True)
    def exercise(self,fail):
        with tempfile.TemporaryDirectory() as folder:
            contents=[]
            for prefix in ('a','b'):
                root=Path(folder)/prefix;root.mkdir();fixture(root,prefix,fail and prefix=='b')
                config=Path(folder)/(prefix+'.json');config.write_text(json.dumps({'input':str(root),'output_root':str(Path(folder)/'out'),'distribution':{'pack_id':prefix+'_native_menu_content'}}),encoding='utf-8')
                job=run_job(config);self.assertEqual(job['status'],'PACKAGED_REVIEW_REQUIRED',job)
                contents.append(content_bundle(Path(job['output'])/'converted'/prefix,job['discovered_entrypoints']))
            core=core_bundle();runtime=Package().load('core.source_modules').SourceModuleLoader(core['sources'])
            session=runtime.load('core.bundled_mods').BundledModSession(core['sources'],contents,runtime=runtime)
            try:
                results=session.loader.activate();self.assertTrue(results['a_native_menu']['ready'],results)
                hooks=runtime.load('neoforge.mixin_hooks')
                self.assertEqual(hooks.MixinHooks.count(),1 if fail else 2)
                a=runtime.load('acontent.Audit').Audit;b=runtime.load('bcontent.Audit').Audit
                self.assertEqual((a.tails,b.tails),(1,1))
                menu=runtime.load('minecraft.menu');token=menu.MenuType()
                self.assertIs(menu.AbstractContainerMenu(token,5).menuType,token)
                runtime.load('acontent.Example').Example(3);self.assertEqual((a.tails,b.tails),(2,1))
                session.loader.contexts['a_native_menu'].close()
                self.assertEqual(hooks.MixinHooks.count(),0 if fail else 1)
                runtime.load('acontent.Example').Example(4);self.assertEqual(a.tails,2)
                if not fail:
                    runtime.load('bcontent.Example').Example(6);self.assertEqual(b.tails,2)
                else:self.assertEqual(results['b_native_menu']['state'],'failed')
                session.close();self.assertEqual(hooks.MixinHooks.count(),0)
            finally:session.close();runtime.close()

if __name__=='__main__':unittest.main()
