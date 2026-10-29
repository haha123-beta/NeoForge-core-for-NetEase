import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from build_resources import build
from mod_compat_audit import audit


class ResourceTests(unittest.TestCase):
    def test_preserves_source_and_reports_unsupported_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'input'
            language = source / 'assets/demo/lang/en_us.json'
            language.parent.mkdir(parents=True)
            language.write_text(json.dumps({'demo.title': 'Demo', 'demo.format': '%s'}))
            model = source / 'assets/demo/models/item.json'
            model.parent.mkdir(parents=True)
            model.write_text('{}')
            before = {str(p.relative_to(source)): p.read_bytes() for p in source.rglob('*') if p.is_file()}
            report = build(source, root / 'out', 'demo')
            self.assertEqual(report['status'], 'partial')
            self.assertEqual(len(report['issues']), 2)
            self.assertEqual((root / 'out/texts/en_US.lang').read_text(), 'demo.title=Demo\n')
            self.assertEqual(before, {str(p.relative_to(source)): p.read_bytes() for p in source.rglob('*') if p.is_file()})
            with self.assertRaises(ValueError):
                build(source, root / 'out', 'demo')
            with self.assertRaises(ValueError):
                build(source, source / 'out', 'demo')

    def test_conflicting_names_fail_before_output_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for namespace in ('one', 'two'):
                path = root / 'input/assets' / namespace / 'lang/en_us.json'
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps({'same.key': namespace}))
            with self.assertRaises(ValueError):
                build(root / 'input', root / 'out', 'demo')
            self.assertFalse((root / 'out').exists())

    def test_audit_ignores_comment_and_literal_markers(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'Demo.java'
            source.write_text('// @Mixin\nString x = "@Inject .is()";\n@Mixin(Target.class)\nclass Demo {}')
            report = audit(temp)
            self.assertEqual(len(report['findings']), 1)
            self.assertEqual(report['findings'][0]['line'], 3)


if __name__ == '__main__':
    unittest.main()
