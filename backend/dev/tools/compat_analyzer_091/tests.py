"""Independent tests: JDK-produced binaries/javap, negatives, closure and HTML."""
import collections,copy,json,re,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
from classfile import read,descriptor,descriptor_types,mutf8,instructions,ClassFormatError
from abi import Index,archive_classes,build
from locking import numeric_range,verify,digest
from ranking import rank,scenario,closure
from reporting import write_html
from analysis import runtime_inventory

JDK=Path(r'E:\Java\jdk-21.0.10\bin')

class ClassReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='neocore_091_class_tests_');cls.root=Path(cls.tmp.name)
        source='''import java.util.function.IntSupplier;
interface Parent {default int answer(){return 7;}}
class Base {public long count=9;public Number covariant(){return 1;}}
public class Fixture extends Base implements Parent {
 static class Inner {} record Pair(int x,String text) {}
 @Override public Integer covariant(){return 2;}
 public int dense(int n){switch(n){case 1:return 10;case 2:return 20;case 3:return 30;default:return 0;}}
 public int sparse(int n){switch(n){case 1:return 1;case 1000:return 2;case 50000:return 3;default:return 0;}}
 public IntSupplier make(){return () -> answer()+dense(2);}
 public String concat(int x){return "value="+x;}
 public Object[] array(){return new String[]{"a","\\uD83D\\uDE00"};}
 public Object cloneArray(){return array().clone();}
 public static void main(String[] a){System.out.print(new Fixture().make().getAsInt());}
}'''
        path=cls.root/'Fixture.java';path.write_text(source,encoding='utf-8')
        result=subprocess.run([str(JDK/'javac.exe'),'-g','-encoding','UTF-8',str(path)],capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stderr)
        cls.raw=(cls.root/'Fixture.class').read_bytes();cls.row=read(cls.raw)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_jdk_exec_and_exact_javap_descriptors(self):
        actual=subprocess.run([str(JDK/'java.exe'),'-cp',str(self.root),'Fixture'],capture_output=True,text=True,check=True)
        self.assertEqual(actual.stdout,'27')
        output=subprocess.run([str(JDK/'javap.exe'),'-p','-s','-classpath',str(self.root),'Fixture'],capture_output=True,text=True,check=True).stdout
        expected=collections.Counter(re.findall(r'descriptor: (\S+)',output))
        self.assertEqual(expected,collections.Counter(r['descriptor'] for k in ('methods','fields') for r in self.row[k]))
        self.assertEqual((self.row['name'],self.row['superclass'],self.row['interfaces'],self.row['source_file']),('Fixture','Base',['Parent'],'Fixture.java'))
    def test_calls_match_javap_and_dynamic_handles_are_retained(self):
        output=subprocess.run([str(JDK/'javap.exe'),'-p','-c','-classpath',str(self.root),'Fixture'],capture_output=True,text=True,check=True).stdout
        expected=sum(bool(re.match(r'\s*\d+: invoke',line)) for line in output.splitlines())
        self.assertEqual(expected,sum(c['opcode'].startswith('invoke') for c in self.row['calls']))
        dynamic=[c for c in self.row['calls'] if 'dynamic' in c]
        owners={h['owner'] for c in dynamic for h in c['dynamic']['method_handles']}
        self.assertIn('java.lang.invoke.LambdaMetafactory',owners);self.assertIn('java.lang.invoke.StringConcatFactory',owners)
        self.assertTrue(any(h['name'].startswith('lambda$') for c in dynamic for h in c['dynamic']['method_handles']))
        self.assertTrue(all(c['line'] is not None for c in self.row['calls']))
    def test_inner_record_bridge_and_source_mapping(self):
        pair=read((self.root/'Fixture$Pair.class').read_bytes())
        self.assertEqual(pair['source_file'],'Fixture.java');self.assertEqual(pair['superclass'],'java.lang.Record')
        self.assertTrue(any(r['name']=='covariant' and r['access']&0x40 for r in self.row['methods']))
        self.assertIn('java.lang.String',pair['type_references'])
    def test_inherited_member_lookup_and_unknown_vs_missing(self):
        rows=[read(p.read_bytes()) for p in self.root.glob('*.class')]
        for row in rows:row['origin']={'artifact':'jdk_fixture'}
        index=Index({r['name']:r for r in rows})
        self.assertEqual(index.member('Fixture','answer','()I','method')['declaring_type'],'Parent')
        self.assertEqual(index.member('Fixture','count','J','field')['declaring_type'],'Base')
        self.assertEqual(index.member('Fixture','absent','()V','method')['status'],'UNKNOWN_HIERARCHY')
        index.classes['java.lang.Object']={'methods':[],'fields':[],'interfaces':[],'superclass':None,'origin':{}}
        self.assertEqual(index.member('Fixture','absent','()V','method')['status'],'MEMBER_NOT_FOUND')
        self.assertEqual(index.member('[Ljava.lang.Object;','clone','()Ljava/lang/Object;','method')['status'],'ARRAY_CLONE')
        self.assertEqual(index.member('Fixture','<init>','(J)V','method')['status'],'MEMBER_NOT_FOUND')
    def test_multi_release_selection_and_malformed_provider_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);jar=root/'versions.jar'
            with zipfile.ZipFile(jar,'w') as z:
                z.writestr('META-INF/MANIFEST.MF','Manifest-Version: 1.0\nMulti-Release: true\n')
                z.writestr('Fixture.class',self.raw)
                z.writestr('META-INF/versions/17/Fixture.class',self.raw.replace(b'Fixture.java',b'Fixture.javx'))
                z.writestr('META-INF/versions/25/Fixture.class',self.raw)
            selected=list(archive_classes(jar,21));self.assertEqual(len(selected),1);self.assertEqual(selected[0][2],17)
            self.assertEqual(read(selected[0][1])['source_file'],'Fixture.javx')
            wrong=root/'wrong.jar'
            with zipfile.ZipFile(wrong,'w') as z:z.writestr('Wrong.class',self.raw)
            artifact={'id':'test','path':str(wrong),'version':'1','role':'fixture','sha256':digest(wrong),'multi_release_target':21}
            with self.assertRaisesRegex(ValueError,'entry/name mismatch'):build({'artifacts':[artifact],'target':{}},root/'bad.gz')
    def test_truncation_wrong_magic_and_unknown_pool_tags_rejected(self):
        for raw in (b'',self.raw[:-1],b'BAD!'+self.raw[4:],self.raw[:10]+b'\x02'+self.raw[11:]):
            with self.subTest(length=len(raw)),self.assertRaises((ClassFormatError,ValueError)):read(raw)
    def test_modified_utf8_and_descriptor_negative_cases(self):
        self.assertEqual(mutf8(b'a\xc0\x80b'),'a\x00b')
        self.assertEqual(mutf8(b'\xed\xa0\xbd\xed\xb8\x80'),'\U0001f600')
        for raw in (b'\x00',b'\xc1\x81',b'\xf0\x9f\x98\x80',b'\xe0\x80'):
            with self.assertRaises(ClassFormatError):mutf8(raw)
        self.assertEqual(descriptor('(I[[Ljava/lang/String;)J'),{'parameters':['int','java.lang.String[][]'],'return_type':'long'})
        for value in ('V','[V','(V)V','(I','L;','(I)Vextra'):
            with self.assertRaises(ClassFormatError):descriptor(value)
    def test_wide_and_switch_operand_boundaries(self):
        self.assertEqual(list(instructions(bytes([196,132,1,44,255,255,177]))),[])
        for value in (bytes([196,178]),bytes([184,0]),bytes([170,0,0,0])+b'\0'*4+b'\0'*4+b'\xff'*4):
            with self.assertRaises(ClassFormatError):list(instructions(value))
        self.assertEqual(list(instructions(bytes([170,0,0,0])+b'\0'*16)),[])
    def test_generic_type_variable_names_are_not_invented_class_references(self):
        value='<LEVEL:Ljava/lang/Object;>(TLEVEL;)Ljava/util/Map<TLEVEL;Ljava/lang/String;>;'
        self.assertEqual(descriptor_types(value),['java.lang.Object','java.lang.String','java.util.Map'])
        self.assertEqual(descriptor_types('LOuter<Ljava/lang/String;>.Inner<TLEVEL;>;'),['Outer','Outer$Inner','java.lang.String'])

class GraphTests(unittest.TestCase):
    def test_at_inventory_does_not_mistake_local_names_for_runtime_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'sample.py').write_text('class A:\n FIELD=1\n def f(self):\n  localName=2\n  self.actual=3\n  class B:\n   def f(self):\n    self.other=4\nJAVA_MAP={"test.A":A}\n',encoding='utf-8')
            data=runtime_inventory(root);attrs=data['modules']['sample.py']['A']['observed_attribute_names']
            self.assertEqual(attrs,['FIELD','actual'])
    def fixture(self):
        files={'A.java':{'baseline_status':'MANUAL_REVIEW','measured_blockers':['a'],'static_requirements':['b'],'dependencies':[],'conditions':[]},
               'B.java':{'baseline_status':'GENERATED_REVIEW_REQUIRED','measured_blockers':[],'static_requirements':[],'dependencies':['A.java'],'conditions':[]}}
        nodes={k:{'category':'API_METADATA','repair_group':k,'files':['A.java'],'symbol':k,'summary':k} for k in ('a','b')}
        return {'files':files,'blocker_nodes':nodes}
    def test_set_synergy_unknown_frontier_and_no_measured_unlock_claim(self):
        g=self.fixture();one=scenario(g['files'],{'a'});both=scenario(g['files'],{'a','b'})
        self.assertEqual(one['diagnostic_only_manual_constraints_cleared'],['A.java'])
        self.assertEqual(one['all_observed_manual_requirements_cleared'],[])
        self.assertEqual(both['all_observed_manual_requirements_cleared'],['A.java'])
        self.assertIsNone(both['measured_new_generated']);self.assertFalse(both['measurement_performed'])
        self.assertEqual(both['generated_dependency_closure_scenario'],['B.java'])
        self.assertEqual(rank(g),rank(copy.deepcopy(g)))
        self.assertEqual(rank(g)['greedy_sets'][-1]['candidate_set'],['a','b'])
    def test_cycles_do_not_disappear_and_dependencies_are_not_double_counted(self):
        g=self.fixture();g['files']['A.java']['dependencies']=['B.java'];g['files']['B.java']['dependencies']=['A.java','A.java']
        self.assertEqual(closure(g['files'],{'a','b'}),set())
    def test_thirdparty_and_jvm_repairs_not_misrouted_to_core(self):
        g=self.fixture();g['blocker_nodes']['a']['category']='THIRD_PARTY_DEPENDENCY'
        g['blocker_nodes']['b']['category']='JVM_ASM_LIMIT'
        out=rank(g);self.assertFalse(any(c['eligible_for_092_core_repair'] for c in out['candidates']));self.assertEqual(out['greedy_sets'],[])
    def test_html_escapes_untrusted_mod_text_and_remains_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'report.html';g=self.fixture();row=g['files'].pop('A.java');row.update(unknowns=['UNKNOWN'],file='</pre><script>alert(1)</script>')
            g['files'][row['file']]=row
            g['files'].pop('B.java');g['blocker_nodes']['a'].update(symbol='<img onerror=bad>',summary='x')
            g['summary']={};g['limits']=['No execution']
            write_html(target,g,{'candidates':[],'greedy_sets':[]},{})
            text=target.read_text(encoding='utf-8');self.assertNotIn('<script>',text);self.assertIn('&lt;script&gt;',text)
            self.assertIn('Content-Security-Policy',text);self.assertNotIn('src="http',text)

class LockTests(unittest.TestCase):
    def test_version_ranges_and_malformed_versions(self):
        self.assertTrue(numeric_range('1.21.1','[1.21, 1.22)'))
        self.assertFalse(numeric_range('1.22','[1.21,1.22)'));self.assertTrue(numeric_range('4.0.42','[4,)'))
        self.assertTrue(numeric_range('1.21.0','[1.21]'))
        with self.assertRaises(ValueError):numeric_range('1.21.1','latest')
    def test_wrong_target_fails_before_any_inputs_are_accepted(self):
        with self.assertRaisesRegex(ValueError,'target version'):verify({'target':{'minecraft':'26.1'}})
    def test_tampered_file_fails_and_cli_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'data';p.write_bytes(b'changed')
            lock={'target':{'minecraft':'1.21.1','neoforge':'21.1.233','fml':'4.0.42','jdk':'21.0.10','namespace':'named'},
                  'inputs':{'test':{'path':str(p),'sha256':'0'*64}}}
            with self.assertRaisesRegex(ValueError,'hash mismatch'):verify(lock)
            config=root/'bad.json';config.write_text(json.dumps(lock))
            result=subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('cli.py')),'verify',str(config)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertIn('ANALYSIS_FAILED',result.stderr)

if __name__=='__main__':unittest.main()
