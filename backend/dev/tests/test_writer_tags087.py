import os,sys,json,re,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from java_interface_oracle import verify
from java_official_probe import run_original
from test_network086 import GROUPS
from workspace_paths import SCRIPTS_ROOT
from java_frontend import api_index,parse_source
from java_codegen import generate,NeedsLowering
import test_official_interfaces086 as execution

class WriterTags087(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package=Package()
        for module in ('minecraft.block_extra','minecraft.block','minecraft.holder_sets','neoforge.registries','minecraft.writer_contracts'):cls.package.load(module)

    def test_all_public_block_tag_locations_against_original_jar(self):
        ref=Path(__file__).parents[1]/'references/checkpoint-0.8.7/block_tags_original.json'
        data=json.loads(ref.read_bytes());result=run_original(data['probe'],GROUPS)
        self.assertEqual(result,data['output']);self.assertEqual(len(data['fields']),184)
        tags=self.package.load('minecraft.block_extra').BlockTags
        from java_block_tag_data import BLOCK_TAG_LOCATIONS
        self.assertEqual(BLOCK_TAG_LOCATIONS,data['fields'])
        runtime=self.package.load('minecraft.block_tag_data').BLOCK_TAG_LOCATIONS
        self.assertEqual(runtime,BLOCK_TAG_LOCATIONS)
        for name,location in data['fields'].items():
            self.assertEqual(getattr(tags,name).location(),location,name)
            self.assertIs(tags.create(location),getattr(tags,name),name)

    def test_live_block_state_membership_and_reset(self):
        p=self.package;b=p.load('minecraft.block');tags=p.load('minecraft.block_extra').BlockTags;r=p.load('neoforge.registries').BUILT_IN_REGISTRIES.BLOCK;sets=p.load('minecraft.holder_sets').HolderSet
        a=b.Block();other=b.Block();r.put('writer_tags:a',a);r.put('writer_tags:b',other);holder=r._holder_for_value(a)
        state=a.defaultBlockState();self.assertFalse(state.isBlock(tags.SWORD_EFFICIENT))
        direct=sets.direct(holder);named=r.getOrCreateTag(tags.SWORD_EFFICIENT)
        r.bindTags({tags.SWORD_EFFICIENT:[holder]})
        self.assertTrue(state.isBlock(tags.SWORD_EFFICIENT));self.assertTrue(state.isBlock(named));self.assertTrue(state.isBlock(direct))
        self.assertFalse(other.defaultBlockState().isBlock(tags.SWORD_EFFICIENT));self.assertTrue(state.isBlock(a));self.assertFalse(state.isBlock(other))
        r.resetTags();self.assertFalse(state.isBlock(named));self.assertFalse(state.isBlock(tags.SWORD_EFFICIENT));self.assertTrue(state.isBlock(direct))

    def test_state_signatures_and_tag_constants_source_actual_python2(self):
        execution.OfficialInterfaces086().execute('''import net.minecraft.world.level.block.state.BlockState;import net.minecraft.tags.BlockTags;import java.lang.NullPointerException;
public class Run {boolean check(BlockState s){return s.is(BlockTags.SWORD_EFFICIENT);}public int run(){try{check(null);}catch(NullPointerException e){return 7;}return 99;}}''','7')
        known,_=api_index()
        for source in ['import net.minecraft.tags.BlockTags;class Run {Object x=BlockTags.INVENTED_TAG;}','import net.minecraft.world.level.block.state.BlockState;class Run {boolean f(BlockState s){return s.is("minecraft:stone");}}']:
            with self.subTest(source=source),self.assertRaises(NeedsLowering):generate(parse_source(source,known_types=known))

    def test_writer_and_enemy_full_instance_contracts(self):
        verify(self.package.load('minecraft.writer_contracts').INTERFACE_CONTRACTS)
        execution.OfficialInterfaces086().execute('import net.minecraft.world.entity.monster.Enemy;public class Run implements Enemy {public int run(){return Enemy.XP_REWARD_NONE+Enemy.XP_REWARD_SMALL+Enemy.XP_REWARD_MEDIUM+Enemy.XP_REWARD_LARGE+Enemy.XP_REWARD_HUGE+Enemy.XP_REWARD_BOSS;}}','88')

    def test_writer_forwarding_original_and_actual_python2(self):
        original='''class Run implements dde {int n=0;public boolean a(jd p,dtc s,int flags,int depth){n+=depth;return true;}public boolean a(jd p,boolean moving){return false;}public boolean a(jd p,boolean drop,bsr e,int depth){n+=depth;return true;}public int run(){dde w=this;w.a((jd)null,(dtc)null,3);w.b((jd)null,false);w.a((jd)null,true,(bsr)null);return n+(w.b((bsr)null)?999:1);}}public class Probe{public static void main(String[] a){System.out.print(new Run().run());}}'''
        expected=run_original(original,GROUPS);self.assertEqual(expected,'1537')
        source='''import net.minecraft.world.level.LevelWriter;import net.minecraft.core.BlockPos;import net.minecraft.world.level.block.state.BlockState;import net.minecraft.world.entity.Entity;
public class Run implements LevelWriter {int n=0;public boolean setBlock(BlockPos p,BlockState s,int flags,int depth){n+=depth;return true;}public boolean removeBlock(BlockPos p,boolean moving){return false;}public boolean destroyBlock(BlockPos p,boolean drop,Entity e,int depth){n+=depth;return true;}public int run(){LevelWriter w=this;w.setBlock(null,null,3);w.destroyBlock(null,false);w.destroyBlock(null,true,null);return n+(w.addFreshEntity(null)?999:1);}}'''
        execution.OfficialInterfaces086().execute(source,expected)
        # Two-argument default must still invoke an overridden three-argument
        # method, rather than skipping directly to the four-argument primitive.
        override=source.replace('public int run()', 'public boolean destroyBlock(BlockPos p,boolean drop,Entity e){n+=7;return false;}public int run()')
        execution.OfficialInterfaces086().execute(override,'527')

    def test_bonemeal_default_type_position_and_virtual_override(self):
        original='''class Growth implements dgb {public boolean b(dcz l,jd p,dtc s){return true;}public boolean a(dcw l,ayw r,jd p,dtc s){return true;}public void a(aqu l,ayw r,jd p,dtc s){}}class Spread extends Growth {public dgb.a au_(){return dgb.a.a;}}public class Probe {public static void main(String[] a){Growth g=new Growth();jd p=new jd(1,2,3);System.out.print(g.au_().name()+","+(g.a(p)==p)+","+(g.a((jd)null)==null)+","+new Spread().a(p).v());}}'''
        self.assertEqual(run_original(original,GROUPS),'GROWER,true,true,3')
        p=self.package;m=p.load('minecraft.writer_contracts');pos=p.load('minecraft.core').BlockPos;lang=p.load('java_stdlib.lang')
        class Growth(m.BonemealableBlock):pass
        g=Growth();location=pos(1,2,3)
        self.assertIs(g.getParticlePos(location),location);self.assertIsNone(g.getParticlePos(None));self.assertIs(g.getType(),m.BonemealableBlock.Type.GROWER)
        class Spread(Growth):
            def getType(self):return m.BonemealableBlock.Type.NEIGHBOR_SPREADER
        self.assertEqual(Spread().getParticlePos(location).getY(),3)
        with self.assertRaises(lang.NullPointerException):Spread().getParticlePos(None)
        source='''import net.minecraft.world.level.block.BonemealableBlock;import net.minecraft.world.level.LevelReader;import net.minecraft.world.level.Level;import net.minecraft.server.level.ServerLevel;import net.minecraft.core.BlockPos;import net.minecraft.world.level.block.state.BlockState;import net.minecraft.util.RandomSource;
public class Run implements BonemealableBlock {public boolean isValidBonemealTarget(LevelReader l,BlockPos p,BlockState s){return true;}public boolean isBonemealSuccess(Level l,RandomSource r,BlockPos p,BlockState s){return true;}public void performBonemeal(ServerLevel l,RandomSource r,BlockPos p,BlockState s){}public int run(){if(getParticlePos(null)!=null)return 99;return getType().ordinal();}}'''
        execution.OfficialInterfaces086().execute(source,'1')

if __name__=='__main__':unittest.main()
