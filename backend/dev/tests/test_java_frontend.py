import os
import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from java_frontend import parse_source, scan


class JavaFrontendTests(unittest.TestCase):
    def test_modern_syntax_and_original_names_strings_comments(self):
        source = """package sample;
import java.util.Map;
import static java.util.Map.entry;
import java.util.*;
record Point(int x, int y) {}
class Demo {
  String text = "中文 box.is(1)"; // box.is(1)
  java.util.function.Function<Integer,Integer> fn = x -> x + 1;
  Runnable ref = this::run;
  void run() {}
  int test(Object value) {
    box.is(1);
    return switch(value) { case Point(int x, int y) -> x + y; default -> 0; };
  }
}
"""
        ir = parse_source(source, known_types={'java.util.Map'})
        self.assertEqual(ir['parse_status'], 'PARSED')
        self.assertEqual(ir['package'], 'sample')
        self.assertEqual(ir['source_utf8'], source)
        self.assertIn('record', ir['features'])
        self.assertIn('lambda', ir['features'])
        self.assertIn('method_reference', ir['features'])
        self.assertIn('switch_expression', ir['features'])
        self.assertIn('pattern_matching', ir['features'])
        self.assertEqual([row['name'] for row in ir['keyword_calls']], ['is'])
        self.assertEqual(ir['keyword_calls'][0]['line'], 12)
        self.assertEqual(ir['tree']['span'], [0, len(source.encode('utf-8'))])
        self.assertTrue(ir['imports'][0]['known_type_identity'])
        self.assertTrue(ir['imports'][1]['known_static_owner'])
        self.assertTrue(ir['imports'][2]['wildcard'])
        self.assertEqual(ir['codegen_status'], 'NOT_RUN')
        self.assertFalse(ir['engine_verified'])

    def test_qualified_record_pattern_preserves_original_reference(self):
        source = 'class Outer { record Point(int x) {} boolean f(Object value) { return value instanceof Outer.Point(int x); } }'
        ir = parse_source(source)
        self.assertEqual(ir['parse_status'], 'PARSED')
        self.assertEqual(ir['source_utf8'], source)
        self.assertTrue(ir['parser']['qualified_record_fix'])
        self.assertIn('pattern_matching', ir['features'])

    def test_worker_crash_is_reported_and_other_files_continue(self):
        from unittest.mock import patch
        import subprocess
        import java_frontend
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'A.java').write_text('class A {}')
            (root / 'B.java').write_text('class B {}')
            real_run = subprocess.run
            calls = []
            def interrupted(*args, **kwargs):
                calls.append(args)
                if len(calls) == 1:
                    return subprocess.CompletedProcess(args[0], -1073741819, b'', b'native access violation')
                return real_run(*args, **kwargs)
            with patch.object(java_frontend.subprocess, 'run', interrupted):
                report = scan(root, dry_run=True)
            self.assertEqual((report['failed'], report['parsed']), (1, 1))
            self.assertIn('-1073741819', report['results'][0]['error'])
            self.assertEqual(report['results'][1]['status'], 'PARSED')

    def test_batch_errors_dry_run_and_input_protection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'input'
            root.mkdir()
            good = root / 'Good.java'
            good.write_text('class Good {}', encoding='utf-8')
            (root / 'Bad.java').write_text('class Bad { void run( {', encoding='utf-8')
            output = Path(temporary) / 'result'
            dry = scan(root, output, dry_run=True)
            self.assertEqual((dry['files'], dry['parsed'], dry['syntax_errors']), (2, 1, 1))
            self.assertFalse(output.exists())
            result = scan(root, output)
            self.assertEqual(result['python_generated'], 0)
            self.assertTrue((output / 'ir/Good.json').is_file())
            self.assertTrue((output / 'summary.json').is_file())
            self.assertEqual(good.read_text(encoding='utf-8'), 'class Good {}')
            with self.assertRaises(ValueError):
                scan(root, output)
            with self.assertRaises(ValueError):
                scan(root, root / 'nested')


if __name__ == '__main__':
    unittest.main()
