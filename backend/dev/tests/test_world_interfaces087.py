import json,os,re,sys,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from java_interface_oracle import verify
from java_official_probe import native,run_original
from test_network086 import GROUPS
import test_official_interfaces086 as execution

BODY='public class Run implements LevelHeightAccessor {public int getHeight(){return 384;}public int getMinBuildHeight(){return -64;}public int run(){return getMaxBuildHeight()+getSectionsCount()+getMinSection()+getMaxSection()+getSectionIndex(-65)+getSectionIndexFromSectionY(-3)+getSectionYFromSectionIndex(2)+(isOutsideBuildHeight(320)?1:0)+(isOutsideBuildHeight(-64)?999:0);}}'
class WorldInterfaces087(unittest.TestCase):
    def test_original_instance_contracts(self):
        module=Package().load('minecraft.world_contracts')
        evidence=verify(dict(module.INTERFACE_CONTRACTS,**module.GENERIC_INTERFACES))
        self.assertEqual(len(module.INTERFACE_CONTRACTS),4)
        (Path(__file__).parents[1]/'builds/world_interfaces087_official_evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')

    def test_source_default_dispatch_original_and_python2(self):
        original=BODY.replace('public class Run','class Run').replace('LevelHeightAccessor',native('net.minecraft.world.level.LevelHeightAccessor'))
        names={'getHeight':'J_','getMinBuildHeight':'I_','getMaxBuildHeight':'am','getSectionsCount':'an','getMinSection':'ao','getMaxSection':'ap','getSectionIndex':'e','getSectionIndexFromSectionY':'f','getSectionYFromSectionIndex':'g','isOutsideBuildHeight':'d'}
        for name,mapped in names.items():original=re.sub(r'\b'+name+r'\(',mapped+'(',original)
        expected=run_original(original+'public class Probe {public static void main(String[] a){System.out.print(new Run().run());}}',GROUPS)
        self.assertEqual(expected,'359')
        execution.OfficialInterfaces086().execute('import net.minecraft.world.level.LevelHeightAccessor;'+BODY,expected)

    def test_height_factory_negative_sections_bounds_overflow_and_null(self):
        p=Package();m=p.load('minecraft.world_contracts');core=p.load('minecraft.core');lang=p.load('java_stdlib.lang')
        h=m.LevelHeightAccessor.create(-64,384)
        self.assertEqual((h.getMaxBuildHeight(),h.getSectionsCount(),h.getMinSection(),h.getMaxSection()),(320,24,-4,20))
        self.assertTrue(h.isOutsideBuildHeight(core.BlockPos(0,-65,0)))
        self.assertFalse(h.isOutsideBuildHeight(core.BlockPos(0,-64,0)))
        self.assertTrue(h.isOutsideBuildHeight(core.BlockPos(0,320,0)))
        self.assertEqual(h.getSectionIndex(-65),-1)
        with self.assertRaises(lang.NullPointerException):h.isOutsideBuildHeight(None)
        h=m.LevelHeightAccessor.create(2147483647,1)
        self.assertEqual(h.getMaxBuildHeight(),-2147483648)

    def test_renderer_distance_data_default_and_override(self):
        p=Package();m=p.load('minecraft.world_contracts');core=p.load('minecraft.core');lang=p.load('java_stdlib.lang')
        class E(object):
            def getBlockPos(self):return core.BlockPos(0,0,0)
        class R(m.BlockEntityRenderer):
            def render(self,*args):raise AssertionError('Distance checks must not draw')
        r=R();e=E()
        self.assertFalse(r.shouldRenderOffScreen(e));self.assertEqual(r.getViewDistance(),64)
        self.assertTrue(r.shouldRender(e,core.Vec3(64.49,0.5,0.5)))
        self.assertFalse(r.shouldRender(e,core.Vec3(64.5,0.5,0.5)))
        class Short(R):
            def getViewDistance(self):return 2
        self.assertFalse(Short().shouldRender(e,core.Vec3(2.5,0.5,0.5)))
        with self.assertRaises(lang.NullPointerException):r.shouldRender(None,core.Vec3.ZERO)
        execution.OfficialInterfaces086().execute('import net.minecraft.client.renderer.blockentity.BlockEntityRenderer;import net.minecraft.world.level.block.entity.BlockEntity;import net.minecraft.client.renderer.MultiBufferSource;public class Run implements BlockEntityRenderer<BlockEntity> {public void render(BlockEntity e,float t,com.mojang.blaze3d.vertex.PoseStack p,MultiBufferSource b,int l,int o){}public int run(){return getViewDistance()+(shouldRenderOffScreen(null)?999:1);}}','65')

if __name__=='__main__':unittest.main()
