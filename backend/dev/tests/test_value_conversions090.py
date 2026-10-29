"""Java 21 / generated Python 3 / real Python 2 scalar ABI oracles."""
import os,sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_interfaces082 as oracle
from harness import Package
from translate_java import translate

class Values090(unittest.TestCase):
    def compare(self,body,expected):
        oracle.Interfaces082().compare({'use/Run.java':'package use;public class Run {'+body+'}'},expected)

    def test_eight_scalar_boxing_unboxing_widening(self):
        self.compare('''static long take(long n){return n;}
          public int run(){byte b=3;short s=4;char c='A';
          Byte bb=b;Short ss=s;Character cc=c;Integer ii=5;Long ll=6L;
          Float ff=1.25f;Double dd=2.5;Boolean flag=true;
          long wide=bb;double decimal=ff;
          if(!flag)return 99;if(decimal!=1.25)return 98;
          if(cc!='A')return 97;return (int)(take(ll)+wide+ss+ii+dd);}
        ''','20')

    def test_required_boxing_caches_and_constructor_identity(self):
        self.compare('''public int run(){Integer a=7;Integer b=7;
          Long c=7L;Long d=7L;Byte e=(byte)7;Byte f=(byte)7;
          Short g=(short)7;Short h=(short)7;Character i='A';Character j='A';
          Boolean k=true;Boolean l=true;
          if(a!=b || c!=d || e!=f || g!=h || i!=j || k!=l)return 99;
          Integer x=new Integer(7);Integer y=new Integer(7);
          if(x==y || x==a)return 98;return 7;}
        ''','7')

    def test_numeric_casts_and_utf16(self):
        self.compare('''public int run(){double z=0.0;double nan=z/z;double inf=1.0/z;
          if((int)nan!=0)return 91;if((int)inf!=2147483647)return 92;
          if((int)(-inf)!=-2147483648)return 93;
          if((long)inf!=9223372036854775807L)return 94;
          if((byte)inf!=-1 || (short)inf!=-1 || (int)(char)inf!=65535)return 95;
          if((int)(char)-1!=65535 || (byte)257!=1)return 96;
          float f=(float)16777217;double d=f;if(d!=16777216.0)return 97;
          char ch='A';return ch+1;}
        ''','66')

    def test_large_long_to_float_rounds_once_and_float_overflow_is_infinite(self):
        self.compare('''public int run(){long x=4611686293305294849L;float rounded=x;
          if(rounded!=4611686568183201792.0f)return 99;
          float large=3.0e38f;float inf=large*2.0f;if(inf<=large)return 98;
          char newline='\\n';char octal='\\101';if(newline!=10)return 97;
          if(octal!='A')return 96;return 7;}
        ''','7')

    def test_supplier_read_projection_preserves_extends_and_raw_erasure(self):
        from java_library_signatures import resolve
        for owner,result in [('java.util.function.Supplier<?extendsjava.lang.Integer>','java.lang.Integer'),
                             ('java.util.function.Supplier<?superjava.lang.Integer>','java.lang.Object'),
                             ('java.util.function.Supplier<?>','java.lang.Object'),
                             ('java.util.function.Supplier','java.lang.Object')]:
            self.assertEqual(resolve(owner,'get',0,[],lambda x:x)['return_type'],result)
            with self.assertRaises(ValueError):resolve(owner,'get',1,['int'],lambda x:x)

    def test_wrong_wrapper_null_number_and_instanceof(self):
        self.compare('''public int run(){int n=0;Object a=(byte)3;Object b=3;
          if(a instanceof Integer)return 91;
          if(!(a instanceof Byte) || !(a instanceof Number))return 92;
          if(b instanceof Byte)return 93;
          try{int wrong=(Integer)a;return 94;}catch(ClassCastException e){n=3;}
          Integer nil=null;try{long bad=nil;return 95;}catch(NullPointerException e){n=n+4;}
          Boolean flag=true;if(flag!=true || flag==false)return 96;
          return n;}
        ''','7')

    def test_overload_strict_widening_precedes_boxing(self):
        self.compare('''static int pick(long n){return 1;}
          static int pick(Integer n){return 99;}
          static int wide(double n){return 2;}
          static int wide(Object n){return 3;}
          public int run(){Integer value=7;return pick(7)+wide(value);}
        ''','4')

    def test_reference_array_checks_java_wrapper_identity(self):
        self.compare('''public int run(){Integer[] values=new Integer[1];Object[] a=values;
          try{a[0]=(byte)3;return 99;}catch(ArrayStoreException e){return 7;}}
        ''','7')

    def test_nested_array_checks_java_wrapper_identity(self):
        self.compare('''public int run(){Integer[][] a=new Integer[1][];Object[] erased=a;
          Byte[] b=new Byte[1];try{erased[0]=b;return 99;}catch(ArrayStoreException e){return 7;}}
        ''','7')

    def test_method_references_adapt_scalar_arguments_and_results(self):
        oracle.Interfaces082().compare({'use/Run.java':'''package use;
          import java.util.function.Supplier;import java.util.function.Function;
          public class Run {static long constant(){return 7L;}
          static long twice(long n){return n*2L;}
          public int run(){Supplier<Long> s=Run::constant;Function<Long,Long> f=Run::twice;
            long value=s.get();return (int)(value+f.apply(7L));}}
        '''},'21')

    def test_config_long_double_factories_in_real_python2(self):
        import json,subprocess
        from build_source_bundle import collect_sources
        from workspace_paths import SCRIPTS_ROOT
        from java_config_signatures import resolve,PREFIX
        with self.assertRaises(ValueError):resolve(PREFIX+'Builder','defineInRange',4,['java.lang.String','boolean','int','int'])
        source='''package use;import net.neoforged.neoforge.common.ModConfigSpec;
          public class Run {public int run(){ModConfigSpec.Builder b=new ModConfigSpec.Builder();
          ModConfigSpec.LongValue lv=b.defineInRange("l",7L,0L,9L);
          ModConfigSpec.DoubleValue dv=b.defineInRange("d",1.25,0,9);
          long n=lv.get();double d=dv.get();
          if(lv.getAsLong()!=7L || dv.getAsDouble()!=1.25)return 99;
          if(n!=7L || d!=1.25)return 98;return 7;}}
        '''
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'source';(src/'use').mkdir(parents=True);(src/'use/Run.java').write_text(source)
            report=translate(src,root/'out')
            self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(1,0,0),report)
            sources=collect_sources(root/'out/source');pkg=Package()
            self.assertIn('use.Run',sources,report)
            runtime=pkg.load('core.source_modules').SourceModuleLoader(sources)
            api=pkg.load('core.java_api');scope=api.JavaApiImports(runtime).install(api.collect_java_api())
            try:self.assertEqual(runtime.load('use.Run').Run().run(),7)
            finally:scope.close();runtime.close()
            all_sources=collect_sources(SCRIPTS_ROOT);all_sources.update(sources)
            data={'loader_source':(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8'),'sources':all_sources,'module':'use.Run','class_name':'Run','expected':'7'}
            probe=root/'probe.json';probe.write_text(json.dumps(data),encoding='utf-8')
            result=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(Path(__file__).with_name('probe_interfaces082_python27.py')),str(probe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        config=Package().load('neoforge.config')
        self.assertFalse(issubclass(config.LongValue,config.IntValue))
        self.assertFalse(hasattr(config.LongValue,'getAsInt'))

    def test_disallowed_invocation_narrowing_is_reviewed(self):
        for formal,actual in [('Byte','1'),('int','1L'),('byte','new Integer(1)')]:
            with self.subTest(formal=formal),tempfile.TemporaryDirectory() as tmp:
                src=Path(tmp)/'src';src.mkdir()
                (src/'Run.java').write_text('class Run {static void call('+formal+' x){}void run(){call('+actual+');}}')
                report=translate(src,dry_run=True)
                self.assertEqual(report['manual_review'],1,report)

    def test_helpers_exact_identity_boundaries_and_hashes(self):
        p=Package();f=p.load('java_stdlib.function').Functional;l=p.load('java_stdlib.lang')
        for kind,value in [('byte',7),('short',7),('int',7),('long',7),('char','A'),('boolean',True)]:
            boxed=f.box(kind,value)
            self.assertIs(boxed,f.box(kind,value));self.assertEqual(f.unbox(kind,boxed),value)
        for wrong in (l.Byte(1),l.Short(1),True,1):
            with self.assertRaises(l.ClassCastException):f.castReference(wrong,l.Integer)
        with self.assertRaises(l.NullPointerException):f.unbox('long',None)
        for kind,value in [('byte',128),('int',2147483648),('long',9223372036854775808),('boolean',1),('char','ab')]:
            with self.assertRaises(l.ClassCastException):f.box(kind,value)
        self.assertFalse(l.Integer(1).equals(l.Byte(1)))
        self.assertFalse(l.Float(0.0).equals(l.Float(-0.0)))
        self.assertTrue(l.Double(float('nan')).equals(l.Double(float('nan'))))
        self.assertEqual(l.Integer(-1).hashCode(),-1)
        self.assertEqual(l.Long(4294967296).hashCode(),1)
        self.assertEqual(l.Float(-0.0).hashCode(),-2147483648)
        self.assertEqual(l.Double(-0.0).hashCode(),-2147483648)

if __name__=='__main__':unittest.main()
