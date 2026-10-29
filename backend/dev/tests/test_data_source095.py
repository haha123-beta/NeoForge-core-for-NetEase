"""Reject misleading version metadata and optional-reference semantic loss."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from data_only094 import validate_source,run
from recipe_data094 import Resolver,Unsupported,convert_recipe


class DataSource095(unittest.TestCase):
    def test_source_metadata_version_loader_and_overlays(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);meta=root/'pack.mcmeta'
            def check(data,info=None):
                meta.write_text(json.dumps(data),encoding='utf-8')
                return validate_source(root,info or {'platform':'NeoForge'})
            self.assertIsNone(check({'pack':{'pack_format':48,'description':'x'}}))
            for data in ({'pack':{'pack_format':15}}, {'pack':[]}, [],
                         {'pack':{'pack_format':48},'overlays':{'entries':[]}},
                         {'pack':{'pack_format':48,'supported_formats':[55,70]}}):
                with self.subTest(data=data),self.assertRaises(ValueError):check(data)
            with self.assertRaises(ValueError):check({'pack':{'pack_format':48}}, {'platform':'Forge'})
            meta.write_text('not json')
            with self.assertRaises(ValueError):validate_source(root,{'platform':'NeoForge'})

    def test_java_mixin_and_at_cannot_enter_data_only_lane(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'pack.mcmeta').write_text('{"pack":{"pack_format":48}}')
            for name in ('Business.class','Business.java','required.mixins.json','accesstransformer.cfg'):
                p=root/name;p.write_text('')
                with self.subTest(name=name),self.assertRaises(ValueError):validate_source(root,{'platform':'NeoForge'})
                p.unlink()

    def test_optional_existing_tag_must_validate_and_resolve_children(self):
        items={'minecraft:coal':{'max_stack_size':64},'sample:tool':{'max_stack_size':1}}
        for child in ({'values':['#sample:child']},{'values':['bad:id/../path']},
                      {'values':['sample:tool']},{'values':['#sample:missing']},{'invalid':True}):
            tags={'sample:root':{'values':['minecraft:coal',{'id':'#sample:child','required':False}]},'sample:child':child}
            with self.subTest(child=child),self.assertRaises(Unsupported):Resolver(items,tags).ingredient({'tag':'sample:root'})
        tags={'sample:root':{'values':['minecraft:coal',{'id':'#sample:missing','required':False}]}}
        resolver=Resolver(items,tags)
        self.assertEqual(resolver.ingredient({'tag':'sample:root'}),['minecraft:coal'])
        self.assertEqual(resolver.tag_evidence['sample:root'][0]['status'],'ABSENT_OPTIONAL')

    def test_source_crafting_category_uses_official_misc_fallback(self):
        items={'minecraft:coal':{'max_stack_size':64}}
        recipe={'type':'minecraft:crafting_shapeless','ingredients':[{'item':'minecraft:coal'}],'result':{'id':'minecraft:coal'}}
        for category in ('building','redstone','equipment','misc'):
            ir,targets=convert_recipe(dict(recipe,category=category),'sample:one',Resolver(items))
            self.assertEqual(ir['effective_category'],category);self.assertNotIn('codec_fallbacks',ir)
        for category in ('minicoal','made_up',None,3,{}):
            ir,targets=convert_recipe(dict(recipe,category=category),'sample:one',Resolver(items))
            self.assertEqual(ir['effective_category'],'misc');self.assertEqual(ir['codec_fallbacks'][0]['raw'],category)
            self.assertEqual(ir['raw']['category'],category)
        with self.assertRaises(Unsupported):convert_recipe(dict(recipe,group=3),'sample:one',Resolver(items))

    def test_optional_vanilla_item_missing_target_is_not_proven_source_absence(self):
        tags={'sample:root':{'values':['minecraft:coal',{'id':'minecraft:unmapped','required':False}]}}
        with self.assertRaises(Unsupported):
            Resolver({'minecraft:coal':{'max_stack_size':64}},tags).ingredient({'tag':'sample:root'})

    def test_unexported_tag_resource_prevents_whole_mod_complete_status(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);source=root/'source';source.mkdir();work=root/'work';work.mkdir()
            (source/'pack.mcmeta').write_text('{"pack":{"pack_format":48}}')
            recipe=source/'data/sample/recipe/coal.json';recipe.parent.mkdir(parents=True)
            recipe.write_text(json.dumps({'type':'minecraft:crafting_shapeless','ingredients':[{'item':'minecraft:coal'}],'result':{'id':'minecraft:coal'}}))
            tag=source/'data/sample/tags/item/extra.json';tag.parent.mkdir(parents=True);tag.write_text('{"values":["minecraft:coal"]}')
            # Stop before archive creation: inspection of the actual persisted report
            # is sufficient to show the native tag gap is no longer discarded.
            def stop(*args):raise RuntimeError('ARCHIVE_CHECKPOINT')
            with self.assertRaisesRegex(RuntimeError,'ARCHIVE_CHECKPOINT'):
                run(source,work,root/'out.zip',{'platform':'NeoForge','mods':[{'id':'sample'}]},stop,lambda *args:None)
            report=json.loads((work/'data_report.json').read_text(encoding='utf-8'))
            self.assertTrue(report['partial']);self.assertIn('data/sample/tags/item/extra.json',report['unconverted_non_recipe_content'])


if __name__=='__main__':unittest.main()
