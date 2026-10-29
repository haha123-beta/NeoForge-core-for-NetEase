import hashlib,json,os,subprocess,sys,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from java_frontend import parse_source
from java_codegen import generate,NeedsLowering
from java_official_probe import JDK
import test_official_interfaces086 as execution

class Nullable087(unittest.TestCase):
    def test_original_declaration_and_runtime_retention(self):
        jar=Path(r'F:\PCL\.minecraft\libraries\com\google\code\findbugs\jsr305\3.0.2\jsr305-3.0.2.jar')
        p=subprocess.run([str(JDK/'javap.exe'),'-v','-p','-classpath',str(jar),'javax.annotation.Nullable'],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr);self.assertIn('methods: 0',p.stdout);self.assertIn('Ljava/lang/annotation/RetentionPolicy;.RUNTIME',p.stdout)
        evidence={'path':str(jar),'sha256':hashlib.sha256(jar.read_bytes()).hexdigest(),'javap':p.stdout,'limitation':'Runtime annotation metadata retained in report; reflective annotation objects are not implemented.'}
        (Path(__file__).parents[1]/'references/checkpoint-0.8.7/nullable_original.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')

    def test_metadata_and_actual_python2_null_roundtrip(self):
        source='import javax.annotation.Nullable;public class Run {@Nullable Object value;@Nullable Object echo(@Nullable Object o){return o;}public int run(){return echo(null)==null?7:99;}}'
        result=generate(parse_source(source));self.assertEqual(len(result['annotation_metadata']),3)
        self.assertTrue(all(r['retention']=='RUNTIME' and r['java_name']=='javax.annotation.Nullable' for r in result['annotation_metadata']))
        execution.OfficialInterfaces086().execute(source,'7')

    def test_runtime_values_and_invalid_elements_still_reject(self):
        for source in ['import javax.annotation.Nullable;class Run {Nullable x;}','import javax.annotation.Nullable;class Run {@Nullable(value=1) Object x;}']:
            with self.subTest(source=source),self.assertRaises(NeedsLowering):generate(parse_source(source))

if __name__=='__main__':unittest.main()
