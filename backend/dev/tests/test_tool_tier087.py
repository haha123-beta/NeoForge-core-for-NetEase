import json,os,sys,unittest,tempfile,subprocess,hashlib
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from java_interface_oracle import verify
from java_official_probe import run_original
from test_network086 import GROUPS
from java_frontend import parse_source,api_index
from java_codegen import generate,NeedsLowering
import test_official_interfaces086 as execution
from build_source_bundle import core_bundle
from workspace_paths import SCRIPTS_ROOT

class ToolTier087(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package=Package()
        for name in ("minecraft.tool_rules","minecraft.block","neoforge.registries","minecraft.block_extra","minecraft.registries","minecraft.holder_sets"):
            cls.package.load(name)

    def test_tier_original_contract_and_real_registry_bootstrap_default_data(self):
        p=self.package;m=p.load('minecraft.tool_rules');verify(m.INTERFACE_CONTRACTS)
        ref=Path(__file__).parents[1]/'references/checkpoint-0.8.7'
        result=run_original((ref/'tier_default_probe.java.txt').read_text(encoding='utf-8'),GROUPS+('com.google.guava:failureaccess',))
        self.assertEqual(result,'RESULT:2,1.0,1,true,false,3.5,true')
        class Tier(m.Tier):
            def getIncorrectBlocksForDrops(self):return None
            def getSpeed(self):return 3.5
        tool=Tier().createToolProperties(None);rules=tool.rules()
        actual=[rules.size(),tool.defaultMiningSpeed(),tool.damagePerBlock(),rules.get(0).speed().isEmpty(),rules.get(0).correctForDrops().get().booleanValue(),rules.get(1).speed().get().floatValue(),rules.get(1).correctForDrops().get().booleanValue()]
        self.assertEqual('RESULT:'+','.join(str(v).lower() if isinstance(v,bool) else str(v) for v in actual),result)

    def test_named_registry_bind_reload_and_reset_match_original(self):
        ref=Path(__file__).parents[1]/'references/checkpoint-0.8.7'
        result=run_original((ref/'tag_registry_probe.java.txt').read_text(encoding='utf-8'),GROUPS)
        p=self.package;reg=p.load('neoforge.registries');tags=p.load('minecraft.registries');r=reg.Registry('demo:r');r.put('demo:a','a');h=r._holder_for_value('a');tag=tags.TagKey.create('demo:r','demo:t');named=r.getOrCreateTag(tag)
        actual=['RESULT:'+str(named.size())+','+str(named.contains(h)).lower()]
        r.bindTags({tag:[h]});actual.append('RESULT:'+str(named.size())+','+str(named.contains(h)).lower()+','+named.get(0).value())
        r.bindTags({});actual.append('RESULT:'+str(named.size())+','+str(named.contains(h)).lower())
        r.resetTags();actual.append('RESULT:'+str(named.size())+','+str(named.contains(h)).lower());actual.append('NULL:'+str(r.getOrCreateTag(None).size()))
        self.assertEqual('\n'.join(actual),result)

    def test_live_rule_order_speed_and_drop_are_independent(self):
        p=self.package;m=p.load('minecraft.tool_rules');b=p.load('minecraft.block');reg=p.load('neoforge.registries').BUILT_IN_REGISTRIES.BLOCK;tags=p.load('minecraft.block_extra').BlockTags
        class Tier(m.Tier):
            def getIncorrectBlocksForDrops(self):return tags.INCORRECT_FOR_NETHERITE_TOOL
            def getSpeed(self):return 3.5
        tool=Tier().createToolProperties(tags.MINEABLE_WITH_PICKAXE);a=b.Block();c=b.Block();reg.put('demo:a',a);reg.put('demo:c',c);ha=reg._holder_for_value(a);hc=reg._holder_for_value(c)
        reg.bindTags({tags.INCORRECT_FOR_NETHERITE_TOOL:[ha],tags.MINEABLE_WITH_PICKAXE:[ha,hc]})
        self.assertFalse(tool.isCorrectForDrops(a.defaultBlockState()));self.assertTrue(tool.isCorrectForDrops(c.defaultBlockState()))
        self.assertEqual(tool.getMiningSpeed(a.defaultBlockState()),3.5)
        reg.bindTags({tags.MINEABLE_WITH_PICKAXE:[hc]});self.assertEqual(tool.getMiningSpeed(a.defaultBlockState()),1.0)
        reg.resetTags();self.assertEqual(tool.getMiningSpeed(c.defaultBlockState()),1.0);self.assertFalse(tool.isCorrectForDrops(c.defaultBlockState()))
        self.assertEqual(tags.MINEABLE_WITH_PICKAXE.location(),'minecraft:mineable/pickaxe')

    def test_source_tier_default_and_implicit_float_constants_actual_python2(self):
        source='import net.minecraft.world.item.Tier;import net.minecraft.world.item.component.Tool;import net.minecraft.world.item.crafting.Ingredient;import net.minecraft.tags.TagKey;import net.minecraft.tags.BlockTags;import net.minecraft.world.level.block.Block;public class Run implements Tier {public int getUses(){return -1;}public float getSpeed(){return Float.POSITIVE_INFINITY;}public float getAttackDamageBonus(){return 0.0f;}public TagKey<Block> getIncorrectBlocksForDrops(){return BlockTags.INCORRECT_FOR_NETHERITE_TOOL;}public int getEnchantmentValue(){return 0;}public Ingredient getRepairIngredient(){return null;}public int run(){Tool t=createToolProperties(BlockTags.MINEABLE_WITH_PICKAXE);return t.rules().size()+t.damagePerBlock();}}'
        execution.OfficialInterfaces086().execute(source,'3')

    def test_direct_holder_and_set_equality_null_and_array_flattening(self):
        p=self.package;sets=p.load('minecraft.holder_sets');h=p.load('minecraft.registries').Holder;lang=p.load('java_stdlib.lang')
        self.assertIsNone(h.direct(None).value());self.assertTrue(h.direct(None).isBound())
        a=h.direct(lang.JavaString('a'));b=h.direct(lang.JavaString('a'))
        self.assertTrue(a.equals(b));self.assertEqual(a.hashCode(),97)
        direct=sets.HolderSet.direct(a,a);self.assertEqual(direct.size(),2);self.assertTrue(direct.contains(b))
        with self.assertRaises(lang.NullPointerException):direct.contains(None)
        with self.assertRaises(lang.NullPointerException):sets.HolderSet.direct(None)
        items=p.load('minecraft.item');array=p.load('java_stdlib.java_arrays').JavaArray('net.minecraft.world.level.ItemLike',1,[items.Item()],p.load('minecraft.official_interfaces').ItemLike)
        ingredient=p.load('minecraft.crafting').Ingredient.of(array)
        self.assertTrue(ingredient.test(items.ItemStack(array[0],1)))

    def test_codecs_and_unimplemented_formatting_do_not_silently_generate(self):
        known,_=api_index()
        for source in ['import net.minecraft.world.item.component.Tool;class Run {Object x=Tool.CODEC;}','import net.minecraft.world.item.component.Tool;class Run {String f(Tool t){return t.toString();}}']:
            with self.subTest(source=source),self.assertRaises(NeedsLowering):generate(parse_source(source,known_types=known))

    def test_live_rules_in_actual_python2_source_module_loader(self):
        body='''from minecraft.tool_rules import Tier
from minecraft.block import Block
from minecraft.block_extra import BlockTags
from neoforge.registries import BUILT_IN_REGISTRIES
class DemoTier(Tier):
    def getUses(self):return 1
    def getSpeed(self):return 3.5
    def getAttackDamageBonus(self):return 0.0
    def getIncorrectBlocksForDrops(self):return BlockTags.INCORRECT_FOR_NETHERITE_TOOL
    def getEnchantmentValue(self):return 0
    def getRepairIngredient(self):return None
class Run(object):
    def run(self):
        r=BUILT_IN_REGISTRIES.BLOCK
        a=Block();b=Block();r.put('demo:a',a);r.put('demo:b',b)
        t=DemoTier().createToolProperties(BlockTags.MINEABLE_WITH_PICKAXE)
        r.bindTags({BlockTags.INCORRECT_FOR_NETHERITE_TOOL:[r._holder_for_value(a)],BlockTags.MINEABLE_WITH_PICKAXE:[r._holder_for_value(a),r._holder_for_value(b)]})
        answer=str(t.getMiningSpeed(a.defaultBlockState()))+','+str(t.isCorrectForDrops(a.defaultBlockState())).lower()+','+str(t.isCorrectForDrops(b.defaultBlockState())).lower()
        r.resetTags()
        return answer+','+str(t.getMiningSpeed(b.defaultBlockState()))
'''
        sources=core_bundle()['sources'];sources['NativeToolProbe']={'source':body,'is_package':False,'origin':'NativeToolProbe.py','sha256':hashlib.sha256(body.encode('utf-8')).hexdigest()}
        data={'loader_source':(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8'),'sources':sources,'module':'NativeToolProbe','class_name':'Run','expected':'3.5,false,true,1.0'}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'probe.json';path.write_text(json.dumps(data),encoding='utf-8')
            p=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(Path(__file__).with_name('probe_interfaces082_python27.py')),str(path)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stdout+'\n'+p.stderr)

    def test_rule_and_tool_record_hash_equality_float_bits_against_original(self):
        ref=Path(__file__).parents[1]/'references/checkpoint-0.8.7'
        expected=run_original((ref/'tool_records_probe.java.txt').read_text(encoding='utf-8'),GROUPS+('com.google.guava:failureaccess',)).splitlines()
        p=self.package;m=p.load('minecraft.tool_rules');sets=p.load('minecraft.holder_sets');util=p.load('java_stdlib.util');lang=p.load('java_stdlib.lang');actual=[]
        for f in [0.0,-0.0,float('nan'),float('inf'),0.1]:
            rule=m.Rule(sets.HolderSet.empty(),util.Optional.of(lang.Float(m._float(f))),util.Optional.of(lang.Boolean.valueOf(False)))
            other=m.Rule(sets.HolderSet.empty(),util.Optional.of(lang.Float(m._float(f))),util.Optional.of(lang.Boolean.valueOf(False)))
            tool=m.Tool(util.ImmutableList([rule]),f,2);other_tool=m.Tool(util.ImmutableList([other]),f,2)
            self.assertIsInstance(rule,p.load('java_stdlib.records').RecordBase)
            self.assertIsInstance(tool,p.load('java_stdlib.records').RecordBase)
            with self.assertRaises(AttributeError):tool._speed=4.0
            with self.assertRaises(AttributeError):rule._speed=None
            actual.append('RESULT:'+str(rule.hashCode())+','+str(rule.equals(other)).lower()+','+str(tool.hashCode())+','+str(tool.equals(other_tool)).lower())
        self.assertEqual(actual,expected)

if __name__=='__main__':unittest.main()
