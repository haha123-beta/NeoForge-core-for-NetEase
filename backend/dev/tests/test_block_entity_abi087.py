import json,os,re,subprocess,sys,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from java_official_probe import REF,JDK,mapping,native,run_original
from test_network086 import GROUPS
import test_official_interfaces086 as execution

class BlockEntityABI087(unittest.TestCase):
    def test_contract_constructor_and_all_methods_original(self):
        identity='net.minecraft.world.level.block.entity.BlockEntity'
        contract=Package().load('minecraft.runtime_classes').RuntimeClasses.contracts()[identity]
        text=mapping(identity)
        for row in contract['methods']:
            original_args=','.join(a.replace('HolderLookup.Provider','HolderLookup$Provider') for a in row['parameters'])
            self.assertIn(row['return_type']+' '+row['name']+'('+original_args+')',text)
        self.assertIn('<init>('+','.join(contract['constructors'][0])+')',text)
        p=subprocess.run([str(JDK/'javap.exe'),'-p','-s','-classpath',str(REF/'client.jar'),native(identity)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr);self.assertIn('public abstract class',p.stdout)

    def test_source_constructor_virtual_validation_and_lifecycle_original_python2(self):
        source='public class Run extends BlockEntity {public Run(){super(null,new BlockPos(1,2,3),null);}public boolean isValidBlockState(BlockState state){return true;}public int run(){if(hasLevel())return 99;setRemoved();int n=isRemoved()?7:99;clearRemoved();return n+(isRemoved()?99:0)+(getBlockState()==null?1:99);}}'
        original=source.replace('public class Run','class Run')
        for name,identity in [('BlockEntity','net.minecraft.world.level.block.entity.BlockEntity'),('BlockPos','net.minecraft.core.BlockPos'),('BlockState','net.minecraft.world.level.block.state.BlockState')]:original=re.sub(r'\b'+name+r'\b',native(identity),original)
        for a,b in [('isValidBlockState','b'),('hasLevel','m'),('setRemoved','aA_'),('isRemoved','o'),('clearRemoved','p'),('getBlockState','n')]:original=re.sub(r'\b'+a+r'\(',b+'(',original)
        expected=run_original(original+'public class Probe {public static void main(String[] a){System.out.print(new Run().run());}}',GROUPS)
        self.assertEqual(expected,'8')
        execution.OfficialInterfaces086().execute('import net.minecraft.world.level.block.entity.BlockEntity;import net.minecraft.core.BlockPos;import net.minecraft.world.level.block.state.BlockState;'+source,expected)

    def test_native_position_snapshot_and_cached_state_and_validation(self):
        p=Package();runtime=p.load('minecraft.runtime_classes').RuntimeClasses;be=p.load('minecraft.block_entity');core=p.load('minecraft.core');block=p.load('minecraft.block');lang=p.load('java_stdlib.lang')
        identity='net.minecraft.world.level.block.entity.BlockEntity';base=runtime.bind(identity,runtime.contracts()[identity])
        class Sample(base):
            def isValidBlockState(self,state):return True
        pos=core.MutableBlockPos(1,2,3);e=Sample(None,pos,None);pos.set(9,8,7)
        self.assertEqual(tuple(e.getBlockPos()),(1,2,3));self.assertFalse(e.hasLevel());self.assertIsNone(e.getBlockState())
        with self.assertRaises(lang.NullPointerException):Sample(None,None,None)
        b=block.Block();state=b.defaultBlockState();other=block.Block().defaultBlockState()
        kind=be.BlockEntityType(lambda pos,state:None,[b]);e=base(kind,pos,state)
        class World(object):
            def getBlockState(self,pos):raise AssertionError('getBlockState must return the cached state')
        e.setLevel(World());self.assertTrue(e.hasLevel());self.assertIs(e.getBlockState(),state)
        with self.assertRaises(lang.IllegalStateException):e.setBlockState(other)
        self.assertIs(e.getBlockState(),state)
        with self.assertRaises(lang.NullPointerException):kind.isValid(None)
        self.assertFalse(e.triggerEvent(1,2));self.assertFalse(e.onlyOpCanSetNbt())

    def test_generic_ticker_for_real_source_block_entity_subclass(self):
        source='class Custom extends BlockEntity {Custom(){super(null,new BlockPos(0,0,0),null);}public boolean isValidBlockState(BlockState state){return true;}}public class Run implements BlockEntityTicker<Custom> {int n=0;public void tick(Level level,BlockPos pos,BlockState state,Custom entity){n=n+1;}public int run(){BlockEntityTicker<Custom> t=this;t.tick(null,new BlockPos(0,0,0),null,new Custom());return n;}}'
        identities=['net.minecraft.world.level.block.entity.BlockEntity','net.minecraft.world.level.block.entity.BlockEntityTicker','net.minecraft.core.BlockPos','net.minecraft.world.level.block.state.BlockState','net.minecraft.world.level.Level']
        original=source.replace('public class Run','class Run')
        for identity in identities:original=re.sub(r'\b'+identity.rsplit('.',1)[-1]+r'\b',native(identity),original)
        original=original.replace('isValidBlockState(','b(')
        expected=run_original(original+'public class Probe {public static void main(String[] a){System.out.print(new Run().run());}}',GROUPS)
        execution.OfficialInterfaces086().execute(''.join('import '+i+';' for i in identities)+source,expected)

if __name__=='__main__':unittest.main()
