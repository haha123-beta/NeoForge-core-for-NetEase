import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from translate_java import translate
from java_entity_signatures import contextual_factory_return,DEFERRED_ITEM,ITEM

class TargetFactory099(unittest.TestCase):
    def probe(self,body):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'Child.java').write_text('import net.minecraft.world.item.Item;public class Child extends Item {public Child(){super(new Item.Properties());}}')
            (root/'Run.java').write_text('import net.minecraft.world.item.Item;import net.neoforged.neoforge.registries.DeferredItem;import net.neoforged.neoforge.registries.DeferredRegister;class Run {static DeferredRegister.Items ITEMS=DeferredRegister.createItems("test");'+body+'}')
            result=translate(root,dry_run=True)
            return next(r for r in result['results'] if r['file']=='Run.java')

    def test_target_infers_parent_item_without_erasing_holder(self):
        row=self.probe('static DeferredItem<Item> VALUE=ITEMS.register("one",()->new Child());')
        self.assertEqual(row['status'],'GENERATED_REVIEW_REQUIRED',row)

    def test_existing_invariant_holder_does_not_become_covariant(self):
        row=self.probe('static DeferredItem<Item> wrong(DeferredItem<Child> old){return old;}')
        self.assertEqual(row['status'],'MANUAL_REVIEW',row)
        self.assertIn('invariant',row['reason'])

    def test_factory_cannot_narrow_or_cross_the_declared_bound(self):
        for body in ['static DeferredItem<Child> VALUE=ITEMS.register("one",()->new Item(new Item.Properties()));',
                     'static DeferredItem<String> VALUE=ITEMS.register("one",()->"bad");']:
            self.assertEqual(self.probe(body)['status'],'MANUAL_REVIEW')
        record=dict(return_type=DEFERRED_ITEM+'<Child>',target_factory_bound=ITEM)
        self.assertIsNone(contextual_factory_return(record,DEFERRED_ITEM+'<String>',lambda a,b:a==b))
        self.assertIsNone(contextual_factory_return({},DEFERRED_ITEM+'<'+ITEM+'>',lambda a,b:True))

    def test_diamond_keeps_context_and_explicit_arguments_remain_invariant(self):
        import test_interfaces082 as oracle
        oracle.Interfaces082().compare({'use/Run.java':'package use;import java.util.Map;import java.util.HashMap;public class Run {public int run(){Map<String,String> m=new HashMap<>();m.put("k","abc");return m.get("k").length();}}'},'3')
        for body in ['java.util.List<String> a=new java.util.ArrayList<Integer>();','java.util.Map<String,String> a=new java.util.HashMap<Integer,String>();']:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'Run.java').write_text('class Run {void run(){'+body+'}}')
                # Different erased implementation/interface names continue to
                # use the existing strict collection constructor contracts.
                report=translate(root,dry_run=True)
                self.assertEqual(report['manual_review'],1,report)

if __name__=='__main__':unittest.main()
