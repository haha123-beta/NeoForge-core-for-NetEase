import sys,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from translate_java import translate
from harness import Package


class NumericWorldTypes087(unittest.TestCase):
    def generate(self,body):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source';source.mkdir();(source/'Run.java').write_text(body,encoding='utf-8')
            report=translate(source,dry_run=True)
            self.assertEqual(report['failed'],0,report)
            self.assertEqual(report['manual_review'],0,report)
            from java_frontend import isolated_parse,api_index
            from java_codegen import generate
            known,_=api_index();ir=isolated_parse((source/'Run.java').read_bytes(),'Run.java',known)
            return generate(ir)['python_source']

    def test_java_binary_numeric_promotion_uses_exact_runtime_helpers(self):
        code=self.generate('public class Run {public static long div(long a,int b){return a/b;} public static double remap(double v,double a,double b){return (v-a)/(b-a);}}')
        self.assertIn('PrimitiveMath',code)
        math=Package().load('java_stdlib.primitives').PrimitiveMath
        self.assertEqual(math.binary('long','/',-7,2),-3)
        self.assertEqual(math.binary('long','/',-9223372036854775808,-1),-9223372036854775808)
        self.assertEqual(math.binary('double','/',math.binary('double','-',7.0,2.0),math.binary('double','-',4.0,2.0)),2.5)

    def test_existing_world_and_config_abi_drives_condition_types(self):
        body='''
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.Level;
import net.neoforged.fml.event.config.ModConfigEvent;
public class Run {
 public static int x(BlockPos p,int i){return p.getX()+i;}
 public static boolean side(Level level){return !level.isClientSide;}
 public static boolean config(ModConfigEvent.Loading e){return e.getConfig().getModId().equals("demo");}
}'''
        code=self.generate(body)
        self.assertIn("'isClientSide')()",code)
        self.assertIn("'getModId'",code)


if __name__=='__main__':unittest.main()
