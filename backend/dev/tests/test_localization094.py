import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build_localization import build
class Localization094Tests(unittest.TestCase):
    def fixture(self,root,locale,entries):
        p=root/'assets/sample/lang'/(locale+'.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(entries),encoding='utf-8')
    def run_build(self,root):
        return build(root,{'item.sample.one':['item.sample:one.name']},lambda name:(root/name).read_bytes())
    def test_source_language_fallback_resolves_chinese_client_without_inventing_translation(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self.fixture(root,'en_us',{'item.sample.one':'Original Name'})
            result=self.run_build(root)
            self.assertEqual(result['files']['resource/texts/zh_CN.lang'],b'item.sample:one.name=Original Name\n')
            self.assertEqual(result['fallbacks'],[{'locale':'zh_CN','key':'item.sample:one.name','source_locale':'en_US'}])
    def test_actual_translation_has_priority(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self.fixture(root,'en_us',{'item.sample.one':'One'});self.fixture(root,'zh_cn',{'item.sample.one':'Chinese source'})
            result=self.run_build(root);self.assertEqual(result['fallbacks'],[])
            self.assertIn(b'Chinese source',result['files']['resource/texts/zh_CN.lang'])
    def test_unknown_keys_are_not_silently_dropped(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self.fixture(root,'en_us',{'unsupported.key':'Unknown'})
            self.assertTrue(self.run_build(root)['issues'])
    def test_newline_injection_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self.fixture(root,'en_us',{'item.sample.one':'One\nother=Override'})
            with self.assertRaises(ValueError):self.run_build(root)
if __name__=='__main__':unittest.main()
