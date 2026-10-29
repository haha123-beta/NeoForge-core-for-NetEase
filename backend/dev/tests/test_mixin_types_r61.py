import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from java_mixin_types import identity,descriptor_type,method_descriptor
from translate_java import translate
import test_mixin_weave_r55 as base

REFERENCE_CASE={'target':'package demo;public class Target {public static int run(Token t){return t.value;}}',
                'handlers':base.hook('run(Ldemo/Token;)I','RETURN','ci.setReturnValue(t.value+2);',True,'Token t, CallbackInfoReturnable<Integer> ci'),
                'use':'return Target.run(new Token());','expected':9,
                'extra':{'demo/Token.java':'package demo;public class Token {public int value=7;}'}}

class MixinTypeTests(unittest.TestCase):
    def test_known_reference_array_nested_and_unresolved_identity(self):
        owner={'package':'demo','imports':[]}
        unit={'_project_types':{'demo.Token':[{'attribute_chain':['Token']}],'demo.Outer.Inner':[{'attribute_chain':['Outer','Inner']}]},'known_api_types':['java.util.List']}
        self.assertEqual(descriptor_type('Token[]',owner,unit),'[Ldemo/Token;')
        self.assertEqual(descriptor_type('demo.Outer.Inner',owner,unit),'Ldemo/Outer$Inner;')
        self.assertEqual(identity('java.util.List<? extends Token>',owner,unit),'java.util.List<?extendsdemo.Token>')
        self.assertEqual(descriptor_type('java.util.List<?>',owner,unit),'Ljava/util/List;')
        for value in ('T','Missing','void[]','java.util.List<Missing>'):
            with self.assertRaises(ValueError):descriptor_type(value,owner,unit)
    def test_source_reference_parameter_capture_matches_jdk(self):
        case=REFERENCE_CASE
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'original';root.mkdir();files=base.fixture(root,case)
            report=translate(root,Path(folder)/'out')
            self.assertEqual((report['manual_review'],report['failed']),(0,0),report)
            self.assertEqual(base.previous.actual(Path(folder)/'out/original'),'9')
            self.assertEqual(base.oracle(root,files),'9')

if __name__=='__main__':unittest.main()
