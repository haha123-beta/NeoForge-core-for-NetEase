import os
import sys
import unittest
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from build_source_bundle import core_bundle, content_bundle
from probe_network_content_contract import run


class NetworkContentTests(unittest.TestCase):
    def test_independent_content_automatic_registration_native_roundtrip_unload(self):
        root = Path(__file__).resolve().parents[1]
        bundle = content_bundle(root / 'examples/network_roundtrip',
            {'network_roundtrip': 'example.network_roundtrip.Main:start'})
        sources = core_bundle()['sources']
        cls = Package().load('core.source_modules').SourceModuleLoader
        result = run(cls(sources), cls(sources), sources, bundle)
        self.assertEqual(result['requests'], 5)


if __name__ == '__main__': unittest.main()
