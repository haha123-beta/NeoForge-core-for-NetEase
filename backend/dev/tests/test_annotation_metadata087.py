import os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from java_frontend import parse_source,api_index
from java_codegen import generate,NeedsLowering
from test_official_interfaces086 import OfficialInterfaces086

class AnnotationMetadata087(unittest.TestCase):
    def generate(self,body):
        known,_=api_index();return generate(parse_source(body,known_types=known))

    def test_nested_import_and_full_annotation_identities_preserve_metadata(self):
        for prefix,annotation in [('import org.jetbrains.annotations.ApiStatus;','ApiStatus.Internal'),('import org.jetbrains.annotations.ApiStatus.Internal;','Internal'),('','org.jetbrains.annotations.ApiStatus.Internal')]:
            source=prefix+'@'+annotation+' public class Run {@org.jetbrains.annotations.ApiStatus.Experimental public int run(){return 9;}}'
            row=self.generate(source)
            self.assertEqual([a['retention'] for a in row['annotation_metadata']],['CLASS','CLASS'])
            self.assertEqual(row['annotation_metadata'][0]['java_name'],'org.jetbrains.annotations.ApiStatus.Internal')
            self.assertEqual(row['required_api_types'],[])
            OfficialInterfaces086().execute(source,'9')

    def test_deprecated_is_retained_without_blocking_method_body(self):
        row=self.generate('@Deprecated(since="1",forRemoval=true) public class Run {public int run(){return 4;}}')
        self.assertEqual(row['annotation_metadata'][0]['strategy'],'DEPRECATION_METADATA_ONLY');self.assertEqual(row['annotation_metadata'][0]['retention'],'RUNTIME')

    def test_runtime_use_unknown_annotations_and_runtime_side_effects_still_reject(self):
        for source in ['import org.jetbrains.annotations.ApiStatus;class Run {Object value=ApiStatus.Internal.class;}','import org.jetbrains.annotations.ApiStatus;@ApiStatus.Internal("bad") class Run {}','class Run {@org.jetbrains.annotations.ApiStatus.Internal void f(int x){} void g(@org.jetbrains.annotations.ApiStatus.Experimental int n){}}','@other.Magic class Run {}','import net.neoforged.api.distmarker.OnlyIn;@OnlyIn(net.neoforged.api.distmarker.Dist.CLIENT) class Run {}']:
            with self.subTest(source=source),self.assertRaises(NeedsLowering):self.generate(source)

if __name__=='__main__':unittest.main()
