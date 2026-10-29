import copy,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from resolution import Index,SHARED
from classfile import read
from refine import refine,calibrate
from bytecode_compare import observations
JDK=Path(r'E:\Java\jdk-21.0.10\bin')

def cls(name,parent=None,interfaces=(),methods=(),fields=(),access=1):
    return dict(name=name,superclass=parent,interfaces=list(interfaces),methods=list(methods),fields=list(fields),access=access,origin={})
def method(name='value',desc='()I',access=1):return dict(name=name,descriptor=desc,access=access)

class Resolution092(unittest.TestCase):
    def test_class_method_precedes_interface_default(self):
        i=Index({'Child':cls('Child','Base',['I']),'Base':cls('Base',methods=[method()]),'I':cls('I',methods=[method()],access=0x201)})
        self.assertEqual(i.member('Child','value','()I','method')['declaring_type'],'Base')
    def test_most_specific_default_not_first_breadth_match(self):
        rows={'Object':cls('Object'),'A':cls('A',methods=[method()],access=0x201),'B':cls('B',interfaces=['A'],methods=[method()],access=0x201),
              'C':cls('C','Object',['A','B'])}
        self.assertEqual(Index(rows).member('C','value','()I','method')['declaring_type'],'B')
    def test_conflict_and_unknown_do_not_guess(self):
        rows={'C':cls('C',interfaces=['A','B']),'A':cls('A',methods=[method()],access=0x201),'B':cls('B',methods=[method()],access=0x201)}
        self.assertEqual(Index(rows).member('C','value','()I','method')['status'],'DEFAULT_METHOD_CONFLICT')
        rows.pop('B');self.assertEqual(Index(rows).member('C','value','()I','method')['status'],'UNKNOWN_HIERARCHY')
    def test_constructor_never_inherited_and_field_interfaces_first(self):
        rows={'C':cls('C','B',['I']),'B':cls('B',methods=[method('<init>','(I)V')],fields=[method('x','I')]),
              'I':cls('I',fields=[method('x','I',0x19)],access=0x201)}
        self.assertEqual(Index(rows).member('C','<init>','(I)V','method')['status'],'MEMBER_NOT_FOUND')
        self.assertEqual(Index(rows).member('C','x','I','field')['declaring_type'],'I')
    def test_private_and_static_interface_methods_not_inherited(self):
        rows={'C':cls('C',interfaces=['I']),'I':cls('I',methods=[method(access=2),method('other',access=9)],access=0x201)}
        self.assertEqual(Index(rows).member('C','value','()I','method')['status'],'MEMBER_NOT_FOUND')
        self.assertEqual(Index(rows).member('C','other','()I','method')['status'],'MEMBER_NOT_FOUND')
    def test_access_is_explicitly_unverified(self):
        r=Index({'C':cls('C',methods=[method(access=4)])}).member('C','value','()I','method')
        self.assertEqual(r['access_check'],'NOT_PERFORMED');self.assertEqual(r['initialization'],'NOT_EXECUTED')

class Evidence092(unittest.TestCase):
    def test_real_compiler_overloads_compared_to_original_class_without_anchors(self):
        import os
        from unittest.mock import patch
        from compiler_comparison import compare
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
        from translate_java import translate
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'C.java';classes=root/'classes';cfr=root/'cfr'
            source.write_text('package sample;public class C {static int f(int x){return 1;}static int f(Integer x){return 2;}public static int run(){return f(1)+f(Integer.valueOf(1));}}')
            probe=root/'Probe.java';probe.write_text('class Probe {public static void main(String[] args){System.out.print(sample.C.run());}}')
            subprocess.run([str(JDK/'javac.exe'),'-proc:none','-d',str(classes),str(source),str(probe)],check=True,capture_output=True)
            actual=subprocess.run([str(JDK/'java.exe'),'-cp',str(classes),'Probe'],check=True,capture_output=True,text=True).stdout
            self.assertEqual(actual,'3')
            subprocess.run([str(JDK/'java.exe'),'-cp',r'E:\EpicYSM_Workspace\Bytecode-Viewer-2.12.jar','org.benf.cfr.reader.Main',str(classes/'sample/C.class'),'--outputdir',str(cfr),'--silent','true'],check=True,capture_output=True)
            with patch.dict(os.environ,{'NEOCORE_OBSERVABILITY_DIR':str(root/'observations')}):a=translate(cfr,root/'a')
            with patch.dict(os.environ,{'NEOCORE_OBSERVABILITY_DIR':''}):b=translate(cfr,root/'b')
            self.assertEqual(a,b);self.assertEqual(a['generated_for_review'],1)
            self.assertEqual((root/'a/cfr/sample/C.py').read_bytes(),(root/'b/cfr/sample/C.py').read_bytes())
            events=[json.loads(s) for s in (root/'observations/events.jsonl').read_text(encoding='utf-8').splitlines()]
            import zipfile
            with zipfile.ZipFile(JDK.parent/'jmods/java.base.jmod') as z:
                official={n:read(z.read('classes/'+n.replace('.','/')+'.class'),code=False) for n in ('java.lang.Integer','java.lang.Number','java.lang.Object')}
            result=compare([read((classes/'sample/C.class').read_bytes())],official,events)
            matched=[r for r in result['observations'] if r['status']=='SAME_SYMBOL_OBSERVED_IN_SOURCEFILE_BYTECODE']
            self.assertTrue(any(r['unique_abi_symbol'][2]=='(I)I' for r in matched),result)
            self.assertTrue(any(r['unique_abi_symbol'][2]=='(Ljava/lang/Integer;)I' for r in matched),result)
            self.assertEqual(result['trusted_expression_anchors'],[]);self.assertEqual(result['production_descriptor_overrides'],0)
    def test_merged_generic_diagnostic_split_and_immutable(self):
        old='COMPILER_SEMANTICS:generic';files={}
        for n,t in [('a.java','p.A'),('b.java','p.B')]:
            files[n]=dict(baseline_diagnostic={'reason':'specific '+t,'line':2,'details':{'category':'generic_superclass','resolved_name':t}},measured_blockers=[old],static_requirements=[])
        g=dict(files=files,blocker_nodes={old:dict(category='COMPILER_SEMANTICS')});original=copy.deepcopy(g)
        result=refine(g);self.assertEqual(g,original);self.assertEqual(len(result['blocker_nodes']),2)
        for n in files:
            node=result['blocker_nodes'][result['files'][n]['measured_blockers'][0]]
            self.assertEqual(node['files'],[n]);self.assertEqual(node['evidence'][0]['reason'],files[n]['baseline_diagnostic']['reason'])
    def test_calibration_does_not_count_new_diagnostic_as_generation(self):
        old={'results':[dict(file='a',status='MANUAL_REVIEW',reason='old'),dict(file='b',status='GENERATED_REVIEW_REQUIRED',project_dependencies=['a'])]}
        new=copy.deepcopy(old);new['results'][0]['reason']='next'
        r=calibrate(old,new);self.assertEqual(r['FIRST_DIAGNOSTIC_REMOVED'],[]);self.assertEqual(r['FRONTIER_CHANGED_UNVERIFIED'],['a']);self.assertEqual(r['NEWLY_GENERATED'],[])
        self.assertEqual(r['GENERATED_DEPENDENCY_CLOSED'],[]);self.assertIsNone(r['ALL_KNOWN_REQUIREMENTS_CLEARED'])
    def test_calibration_never_counts_regression_or_wording_as_fixed(self):
        old={'results':[dict(file='a',status='GENERATED_REVIEW_REQUIRED'),dict(file='b',status='MANUAL_REVIEW',reason='generic parent missing')]}
        new={'results':[dict(file='a',status='MANUAL_REVIEW',reason='new guard'),dict(file='b',status='MANUAL_REVIEW',reason='generic ancestor requires review')]}
        r=calibrate(old,new);self.assertEqual(r['FIRST_DIAGNOSTIC_REMOVED'],[])
        self.assertEqual(r['FRONTIER_CHANGED_UNVERIFIED'],['b']);self.assertEqual(r['NEWLY_GENERATED'],[])
    def test_transitive_closure_and_cycle_not_counted(self):
        old={'results':[dict(file='a',status='MANUAL_REVIEW'),dict(file='b',status='GENERATED_REVIEW_REQUIRED',project_dependencies=['a'])]}
        new=copy.deepcopy(old);new['results'][0]=dict(file='a',status='GENERATED_REVIEW_REQUIRED')
        r=calibrate(old,new);self.assertEqual(r['GENERATED_DEPENDENCY_CLOSED'],['a','b'])
        new['results'][0]['project_dependencies']=['b'];self.assertEqual(calibrate(old,new)['GENERATED_DEPENDENCY_CLOSED'],[])
    def test_similar_names_lines_and_order_never_create_anchors(self):
        row=dict(name='C',calls=[dict(opcode='invokevirtual',line=1,target=dict(owner='C',name='f',descriptor='(I)V'))])
        r=observations([row],[('C','f','(J)V')]);self.assertEqual(r['trusted_expression_anchors'],[])
        self.assertEqual(len(r['compiler_only_symbols']),1);self.assertEqual(r['production_descriptor_overrides'],0)

class Jdk092(unittest.TestCase):
    def test_real_jdk_bridge_defaults_super_overloads_fields_and_dynamic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'Fixture.java'
            p.write_text('''import java.util.function.IntSupplier;
interface Value {default int value(){return 5;}}
public class Fixture extends Base implements Value {
 int field=11;public Fixture(){}public Fixture(int x){field=x;}
 public Integer covariant(){return 2;}
 static int pick(int x){return 13;}static int pick(Integer x){return 17;}
 int run(){IntSupplier a=this::value;IntSupplier b=()->super.value();return a.getAsInt()+b.getAsInt()+pick(1)+pick(Integer.valueOf(1))+field+super.field;}
 public static void main(String[] args){System.out.print(new Fixture().run());}}
''',encoding='utf-8')
            def run(*args):return subprocess.run(list(args),capture_output=True,text=True,encoding='utf-8',check=True).stdout
            base=root/'Base.java';base.write_text('public class Base {int field=3;public int value(){return 7;}public Number covariant(){return 1;}}')
            run(str(JDK/'javac.exe'),'-g','-d',str(root),str(p),str(base))
            self.assertEqual(run(str(JDK/'java.exe'),'-cp',str(root),'Fixture'),'58')
            rows=[read(f.read_bytes()) for f in root.glob('*.class')]
            for r in rows:r['origin']={}
            fixture=next(r for r in rows if r['name']=='Fixture')
            self.assertTrue(any(m['access']&0x40 for m in fixture['methods']))
            refs=[c['target'] for c in fixture['calls'] if 'target' in c]
            self.assertTrue(any(c['name']=='pick' and c['descriptor']=='(I)I' for c in refs))
            self.assertTrue(any(c['name']=='pick' and c['descriptor']=='(Ljava/lang/Integer;)I' for c in refs))
            self.assertTrue(any(c['opcode']=='invokedynamic' for c in fixture['calls']))
            self.assertTrue(any(c['opcode']=='invokespecial' and c.get('target',{}).get('owner')=='Base' for c in fixture['calls']))
            javap=run(str(JDK/'javap.exe'),'-p','-c','-s','-classpath',str(root),'Fixture')
            self.assertIn('invokeinterface',javap);self.assertIn('invokedynamic',javap)
            index=Index({r['name']:r for r in rows});self.assertEqual(index.member('Fixture','value','()I','method')['declaring_type'],'Base')
            cfr=root/'cfr';run(str(JDK/'java.exe'),'-cp',r'E:\EpicYSM_Workspace\Bytecode-Viewer-2.12.jar','org.benf.cfr.reader.Main',str(root/'Fixture.class'),'--outputdir',str(cfr),'--silent','true')
            self.assertTrue((cfr/'Fixture.java').exists())
            self.assertEqual(observations(rows)['trusted_expression_anchors'],[])

if __name__=='__main__':unittest.main()
