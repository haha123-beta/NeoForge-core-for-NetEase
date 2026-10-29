import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recipe_data094 import Resolver,Unsupported,convert_recipe,convert_tree
from build_distribution import build_data
ITEMS={name:{'target_id':name,'max_stack_size':64} for name in ('minecraft:coal','minecraft:diamond','minecraft:flint')}
SIMPLE={'type':'minecraft:crafting_shapeless','ingredients':[{'item':'minecraft:coal'}], 'result':{'id':'minecraft:diamond','count':1}}
class RecipeData094Tests(unittest.TestCase):
    def emit(self,data,**kwargs):return convert_recipe(data,'sample:one',Resolver(ITEMS),**kwargs)
    def test_shaped_preserves_spaces_symbols_quantity(self):
        data={'type':'minecraft:crafting_shaped','pattern':['##',' #'],'key':{'#':{'item':'minecraft:coal'}},'result':{'id':'minecraft:diamond','count':2}}
        ir,targets=self.emit(data);body=targets[0]['minecraft:recipe_shaped']
        self.assertEqual(body,{'description':{'identifier':'sample:one'},'tags':['crafting_table'], 'pattern':['##',' #'],'key':{'#':{'item':'minecraft:coal'}},'result':{'item':'minecraft:diamond','count':2}})
        self.assertEqual(ir['raw'],data)
    def test_shapeless_keeps_duplicate_slots(self):
        data=copy.deepcopy(SIMPLE);data['ingredients']*=3
        body=self.emit(data)[1][0]['minecraft:recipe_shapeless'];self.assertEqual(body['ingredients'],[{'item':'minecraft:coal'}]*3)
    def test_or_ingredients_are_complete_explicit_variants(self):
        data=copy.deepcopy(SIMPLE);data['ingredients']=[[{'item':'minecraft:coal'},{'item':'minecraft:flint'}]]
        targets=self.emit(data)[1]
        self.assertEqual({t['minecraft:recipe_shapeless']['ingredients'][0]['item'] for t in targets},{'minecraft:coal','minecraft:flint'})
        self.assertEqual(len(targets),2)
    def test_stonecutter_has_single_ingredient_and_correct_workstation(self):
        data={'type':'minecraft:stonecutting','ingredient':{'item':'minecraft:coal'},'result':{'id':'minecraft:diamond','count':2}}
        body=self.emit(data)[1][0]['minecraft:recipe_shapeless'];self.assertEqual(body['tags'],['stonecutter']);self.assertEqual(len(body['ingredients']),1)
    def test_time_experience_and_smithing_state_cannot_be_dropped(self):
        for kind in ('minecraft:smelting','minecraft:smithing'):
            with self.subTest(kind=kind),self.assertRaises(Unsupported):self.emit(dict(SIMPLE,type=kind,experience=0.5,cookingtime=100))
    def test_unknown_semantic_fields_and_old_result_format_fail(self):
        for data in (dict(SIMPLE,conditions=[]),dict(SIMPLE,result={'item':'minecraft:diamond'})):
            with self.assertRaises(Unsupported):self.emit(data)
    def test_bad_quantities_shapes_and_ingredients_fail(self):
        for data in (dict(SIMPLE,ingredients=[]),dict(SIMPLE,result={'id':'minecraft:diamond','count':True}),dict(SIMPLE,result={'id':'minecraft:diamond','count':65}),dict(SIMPLE,result={'id':'bad:id/../x'}),dict(SIMPLE,ingredients=[{'item':'other:missing'}])):
            with self.assertRaises(Unsupported):self.emit(data)
        with self.assertRaises(Unsupported):self.emit({'type':'minecraft:crafting_shaped','pattern':['#'],'key':{},'result':{'id':'minecraft:diamond'}})
    def test_unknown_and_cyclic_tags_fail_and_optional_members_are_explicit(self):
        with self.assertRaises(Unsupported):Resolver(ITEMS).ingredient({'tag':'sample:missing'})
        with self.assertRaises(Unsupported):Resolver(ITEMS,{'sample:a':{'values':['#sample:a']}}).ingredient({'tag':'sample:a'})
        resolver=Resolver(ITEMS,{'sample:a':{'values':['minecraft:coal',{'id':'other:missing','required':False}]}})
        self.assertEqual(resolver.ingredient({'tag':'sample:a'}),['minecraft:coal']);self.assertTrue(resolver.tag_evidence)
    def test_stateful_ingredient_is_blocked_without_damage_contract(self):
        resolver=Resolver({'minecraft:sword':{'max_stack_size':1,'is_block':False}})
        with self.assertRaises(Unsupported):resolver.ingredient({'item':'minecraft:sword'})
    def test_variant_explosion_is_not_silently_truncated(self):
        data=copy.deepcopy(SIMPLE);data['ingredients']=[[{'item':'minecraft:coal'},{'item':'minecraft:flint'}]]*9
        with self.assertRaises(Unsupported):self.emit(data)
    def test_version_and_partial_denominators_and_raw_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            for path,data in [('data/sample/recipe/one.json',SIMPLE),('data/sample/recipes/one.json',SIMPLE),('data/sample/recipe/missing.json',dict(SIMPLE,result={'id':'other:missing'}))]:
                p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data))
            result=convert_tree(root,{'items':ITEMS});self.assertEqual(result['report']['input_recipes'],3)
            self.assertEqual(result['report']['active_recipes'],2);self.assertEqual(len(result['files']),1)
            self.assertEqual(result['report']['status_counts'],{'CONVERTED_REVIEW_REQUIRED':1,'MISSING_EXTERNAL_DEPENDENCY':1,'VERSION_NOT_APPLICABLE':1})
            self.assertTrue(result['report']['path_id_overlaps'])
            with self.assertRaises(ValueError):convert_tree(root,{'items':ITEMS},'1.20.1')
    def test_output_identity_collision_blocks_both_sources(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);data=dict(SIMPLE,ingredients=[[{'item':'minecraft:coal'},{'item':'minecraft:flint'}]])
            for path,value in [('data/sample/recipe/one.json',data),('data/sample/recipe/one/nc_variant_0.json',SIMPLE)]:
                p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))
            result=convert_tree(root,{'items':ITEMS});self.assertFalse(result['files']);self.assertEqual(result['report']['status_counts'],{'OUTPUT_CONFLICT':2})
    def test_data_pack_reuses_manifest_writer_and_contains_no_fake_python(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);native={'format_version':'1.12','minecraft:recipe_shapeless':{
                'description':{'identifier':'sample:one'},'tags':['crafting_table'],
                'ingredients':[{'item':'minecraft:coal'}],'result':{'item':'minecraft:diamond','count':1}}}
            files={'behavior/netease_recipes/sample/one.json':json.dumps(native).encode()}
            result=build_data(root/'out','sample',files,{'input_recipes':2,'active_recipes':2,'status_counts':{'blocked':1}},True)
            self.assertFalse(list((root/'out').rglob('*.py')));self.assertEqual(result['core_modules'],0)
            manifest=json.loads(next((root/'out').rglob('manifest.json')).read_text())
            self.assertIn('PARTIAL',manifest['header']['name']);self.assertEqual(manifest['dependencies'],[])
if __name__=='__main__':unittest.main()
