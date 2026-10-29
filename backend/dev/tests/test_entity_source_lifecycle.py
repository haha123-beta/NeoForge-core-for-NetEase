import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from build_source_bundle import core_bundle, content_bundle
from run_translation_job import run_job
from probe_entity_superclass_contract import run
from workspace_paths import DEV_ROOT


class EntitySourceLifecycleTests(unittest.TestCase):
    def test_original_java_factory_spawn_ticks_save_restore_cancel_and_close(self):
        original = DEV_ROOT / 'examples/runtime_entity'
        before = {p.relative_to(original).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in original.rglob('*') if p.is_file()}
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'job.json'
            config.write_text(json.dumps({'input': str(original), 'output_root': str(Path(folder) / 'out'),
                'distribution': {'pack_id': 'runtime_entity_content'}}), encoding='utf-8')
            report = run_job(config)
            self.assertEqual(report['status'], 'PACKAGED_REVIEW_REQUIRED', report)
            bundle = content_bundle(Path(report['output']) / 'converted/runtime_entity', report['discovered_entrypoints'])
            session = Package().load('core.bundled_mods').BundledModSession(core_bundle()['sources'], [bundle])
            try:
                self.assertTrue(session.loader.activate()['runtime_entity_example']['ready'])
                result = run(session.runtime, session)
                self.assertEqual(result['restored_value_after_tick'], 108)
            finally: session.close()
            self.assertEqual(session.loader.results['runtime_entity_example']['state'], 'unloaded')
        self.assertEqual(before, {p.relative_to(original).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in original.rglob('*') if p.is_file()})


if __name__ == '__main__': unittest.main()
