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
from workspace_paths import DEV_ROOT
from probe_acceptance_r50_contract import run
from probe_stability_r49_contract import setup
import probe_network_content_contract as network


class AcceptanceR50Tests(unittest.TestCase):
    def test_shutdown_error_accounting_and_unicode_outer_boundary(self):
        self.assertEqual(len(run(Package().load, setup)), 11)

    def test_network_and_original_java_entity_share_one_core(self):
        with tempfile.TemporaryDirectory() as folder:
            job = Path(folder) / 'job.json'
            job.write_text(json.dumps({'input': str(DEV_ROOT / 'examples/runtime_entity'),
                'output_root': str(Path(folder) / 'output'),
                'distribution': {'pack_id': 'runtime_entity_content'}}), encoding='utf-8')
            report = run_job(job)
            self.assertEqual(report['status'], 'PACKAGED_REVIEW_REQUIRED', report)
            entity = content_bundle(Path(report['output']) / 'converted/runtime_entity', report['discovered_entrypoints'])
            source = core_bundle()['sources']
            packet = content_bundle(DEV_ROOT / 'examples/network_roundtrip', {'network_roundtrip': 'example.network_roundtrip.Main:start'})
            loader = Package().load('core.source_modules').SourceModuleLoader
            server, client = loader(source), loader(source)
            try:
                result = network.run(server, client, source, packet, [entity])
                self.assertEqual((result['requests'], result['replies']), (5, 5))
            finally: server.close(); client.close()


if __name__ == '__main__': unittest.main()
