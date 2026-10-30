import sys,unittest,tempfile,subprocess,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_interfaces082 as oracle
from java_unicode_prelex import translate as prelex,UnicodeInputError
from java_frontend import parse_source
from translate_java import translate

class Unicode099(unittest.TestCase):
    def test_strings_chars_comments_and_eligibility_execute_three_runtimes(self):
        source=r'''package use;public class Run {public int run(){
String a="\u043c\u043e\u0434";String b="\\u005a";
String c="\u005c\u005c\u006e";String d="\uuuu0041\101\s";
// ignored\u000a int value=7;
char x='\u0041';return a.length()+b.length()+c.length()+d.length()+value+x;}}'''
        oracle.Interfaces082().compare({'use/Run.java':source},'86')

    def test_escaped_keyword_and_nonrecursive_translation(self):
        oracle.Interfaces082().compare({'use/Run.java':r'package use;public cl\u0061ss Run {public int run(){return 7;}}'},'7')
        for source,expected in [(r'\u005cu005a','\\u005a'),(r'\\u005a',r'\\u005a'),(r'\u005c\u005a','\\Z'),(r'\\\u006e','\\\\n')]:
            self.assertEqual(prelex(source)[0],expected)

    def test_invalid_escapes_rejected_like_javac(self):
        for literal in [r'"\u00xz"',r'"\u005cu005a"',r'"\u000a"',r'"\u005c"',r'"\q"']:
            with self.subTest(literal=literal),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);p=root/'Run.java';p.write_text('class Run {String s='+literal+';}')
                report=translate(root,dry_run=True)
                self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(0,1,0),report)
                result=subprocess.run([str(oracle.JDK/'javac.exe'),str(p)],capture_output=True)
                self.assertNotEqual(result.returncode,0)

    def test_original_line_mapping_and_immutable_input(self):
        source=r'// x\u000a class Run {void value(){missing();}}'+'\n'
        ir=parse_source(source)
        self.assertIsNotNone(ir['unicode_preprocessing'])
        def walk(n):
            yield n
            for c in n.get('children',[]):yield from walk(c)
        self.assertTrue(all(n['line']==1 for n in walk(ir['tree']) if n['kind']=='method_invocation'))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'Run.java';p.write_text(source);before=p.read_bytes()
            report=translate(root,dry_run=True)
            self.assertEqual(report['results'][0]['line'],1)
            self.assertEqual(p.read_bytes(),before)

    def test_unicode_record_lowering_does_not_translate_twice(self):
        oracle.Interfaces082().compare({'use/Run.java':r'package use;record Value(String s){} public class Run {public int run(){Value v=new Value("\\u0041");return v.s().length();}}'},'6')

    def test_surrogate_pair_utf16_length_three_runtimes(self):
        oracle.Interfaces082().compare({'use/Run.java':r'package use;public class Run {public int run(){return "\uD83D\uDE00".length();}}'},'2')

    def test_unpaired_surrogate_and_mixin_composition_remain_explicit(self):
        with self.assertRaises(UnicodeInputError):prelex(r'\uD800')
        from java_mixin_plan import parse_weave_source,MixinPlanError
        with self.assertRaises(MixinPlanError):parse_weave_source(br'class Run {String s="\u0041";}','Run.java',[])

if __name__=='__main__':unittest.main()
