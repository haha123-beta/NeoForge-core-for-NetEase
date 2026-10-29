import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from run_translation_job import run_job
from build_source_bundle import core_bundle, content_bundle
from harness import Package


class TranslationJobTests(unittest.TestCase):
    def configure(self, base, java, package=True):
        source = base / 'original'
        (source / 'demo').mkdir(parents=True)
        (source / 'demo/Main.java').write_text(java, encoding='utf-8')
        (source / 'META-INF').mkdir()
        (source / 'META-INF/neoforge.mods.toml').write_text(
            'modLoader="javafml"\nloaderVersion="[4,)"\nlicense="MIT"\n'
            '[[mods]]\nmodId="demo_mod"\nversion="1.0"\n', encoding='utf-8')
        config = {'input': 'original', 'output_root': 'outputs'}
        if package:
            config['distribution'] = {'pack_id': 'demo_content',
                'entrypoints': {'demo_mod': 'demo.Main:Main.start'}}
        path = base / 'job.json'
        path.write_text(json.dumps(config), encoding='utf-8')
        return path, source

    def test_conversion_packaging_and_original_static_entrypoint_activation(self):
        with tempfile.TemporaryDirectory() as directory:
            config, source = self.configure(Path(directory),
                'package demo; public class Main { public static void start(Object context) {} }')
            original = (source / 'demo/Main.java').read_bytes()
            report = run_job(config)
            self.assertEqual(report['status'], 'PACKAGED_REVIEW_REQUIRED')
            self.assertEqual(report['ready_mods'], 0)
            self.assertFalse(report['engine_verified'])
            output = Path(report['output'])
            self.assertTrue((output/'distribution/demo_content_behavior_pack/demo_contentScripts/modMain.py').exists())
            self.assertFalse((output/'distribution/demo_content_behavior_pack/NeoForgeCoreScripts').exists())
            self.assertEqual((source/'demo/Main.java').read_bytes(), original)
            core = core_bundle()
            content = content_bundle(output/'converted/original', {'demo_mod': 'demo.Main:Main.start'})
            pkg = Package()
            session = pkg.load('core.bundled_mods').BundledModSession(core['sources'], [content])
            try:
                self.assertIn('demo_mod', session.loader.contexts)
                self.assertRaises(ValueError, session._entrypoint, 'demo.Main:Main..start')
            finally:
                session.close()
            second = run_job(config)
            self.assertNotEqual(second['output'], report['output'])

    def test_incomplete_skips_packaging_and_preserves_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            config, source = self.configure(Path(directory),
                'package demo; class Main { synchronized long value(long x){return x+1L;} }')
            report = run_job(config)
            self.assertEqual(report['status'], 'TRANSLATION_INCOMPLETE')
            output = Path(report['output'])
            self.assertFalse((output/'distribution').exists())
            self.assertTrue((output/'converted/manual_review.txt').exists())
            self.assertTrue((output/'job_report.json').exists())

    def test_overlap_rejected_and_conversion_exception_logged(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            config, source = self.configure(base, 'package demo; class Main {}', False)
            with patch('run_translation_job.translate', side_effect=RuntimeError('conversion exploded')):
                report = run_job(config)
            self.assertEqual(report['status'], 'FAILED')
            self.assertIn('conversion exploded', (Path(report['output'])/'failures.log').read_text())
            config.write_text(json.dumps({'input': 'original', 'output_root': 'original/outputs'}))
            self.assertRaises(ValueError, run_job, config)
            self.assertFalse((source/'outputs').exists())


if __name__ == '__main__':
    unittest.main()
