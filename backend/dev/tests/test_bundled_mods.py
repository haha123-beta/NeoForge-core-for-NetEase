import os
from pathlib import Path
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from build_source_bundle import core_bundle, content_bundle
module = Package().load('core.bundled_mods')


class BundledModTests(unittest.TestCase):
    def test_scope_cleanup_failure_still_closes_runtime_and_remains_visible(self):
        session = module.BundledModSession(core_bundle()['sources'], [])
        original = session.api_scope.close
        def fail_after_close():
            original()
            raise RuntimeError('scope teardown failed')
        session.api_scope.close = fail_after_close
        with self.assertRaisesRegex(RuntimeError, 'api_scope: scope teardown failed'):
            session.close()
        self.assertEqual(session.runtime.modules, {})
        with self.assertRaisesRegex(RuntimeError, 'scope teardown failed'):
            session.close()

    def test_original_packages_run_in_independent_source_bundles(self):
        root = Path(__file__).resolve().parents[1] / 'examples/multi_mod'
        names = ['neocore_example_addon', 'neocore_example_base']
        bundles = [content_bundle(root / name, {name: 'example.' + name + '.Main:start'}) for name in names]
        core = core_bundle()
        before = list(sys.path)
        session = module.BundledModSession(core['sources'], bundles)
        other = module.BundledModSession(core['sources'], bundles, 'CLIENT')
        try:
            self.assertTrue(all(row['ready'] for row in session.loader.activate().values()))
            other.loader.activate()
            self.assertEqual(session.loader.order, list(reversed(names)))
            self.assertIsNot(session.loader.contexts[names[0]].instance,
                             other.loader.contexts[names[0]].instance)
            events = session.runtime.load('core.content_events')
            driver = events.ContentTickDriver(session.loader, 'SERVER')
            for unused in range(30):
                driver.on_tick()
            self.assertEqual(session.loader.contexts[names[0]].instance['ticks'], 20)
            self.assertEqual(sys.path, before)
            self.assertNotIn('example.' + names[0] + '.Main', sys.modules)
            session.close()
            self.assertFalse(other.loader._closed)
        finally:
            session.close()
            other.close()


if __name__ == '__main__':
    unittest.main()
