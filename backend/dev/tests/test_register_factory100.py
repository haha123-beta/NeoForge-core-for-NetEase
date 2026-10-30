import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from translate_java import translate
from java_entity_signatures import generic_parents,ITEMS,BLOCKS,REGISTER,ITEM,BLOCK,HOLDER,contextual_factory_return

class RegisterFactory100(unittest.TestCase):
    def probe(self,body):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'Child.java').write_text('import net.minecraft.world.item.Item;public class Child extends Item {public Child(){super(new Item.Properties());}}')
            (root/'Run.java').write_text('import net.minecraft.world.item.Item;import net.neoforged.neoforge.registries.DeferredHolder;import net.neoforged.neoforge.registries.DeferredRegister;class Run {'+body+'}')
            result=translate(root,dry_run=True)
            return next(r for r in result['results'] if r['file']=='Run.java')

    def test_reviewed_specialization_preserves_declared_generic_superclass(self):
        self.assertEqual(generic_parents(ITEMS,lambda a,b:a==b),[REGISTER+'<'+ITEM+'>'])
        self.assertEqual(generic_parents(BLOCKS,lambda a,b:a==b),[REGISTER+'<'+BLOCK+'>'])
        row=self.probe('DeferredHolder<Item,Child> make(DeferredRegister<Item> reg){return reg.register("a",()->new Child());}')
        self.assertEqual(row['status'],'GENERATED_REVIEW_REQUIRED',row)

    def test_existing_holder_invariant_and_factory_bound_stay_strict(self):
        for body in ('DeferredHolder<Item,Item> bad(DeferredHolder<Item,Child> h){return h;}',
                     'DeferredHolder<Item,String> bad(DeferredRegister<Item> reg){return reg.register("a",()->"bad");}',
                     'DeferredHolder<Item,Child> bad(DeferredRegister<Item> reg){return reg.register("a",()->new Item(new Item.Properties()));}'):
            with self.subTest(body=body):self.assertEqual(self.probe(body)['status'],'MANUAL_REVIEW')
        record=dict(return_type=HOLDER+'<R,Child>',target_factory_bound='R')
        self.assertIsNone(contextual_factory_return(record,HOLDER+'<Other,Child>',lambda a,b:True))

if __name__=='__main__':unittest.main()
