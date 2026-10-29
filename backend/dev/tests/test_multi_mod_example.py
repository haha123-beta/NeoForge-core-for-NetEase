import os
from pathlib import Path
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
package = Package()
extracted = package.load('core.extracted_mods')
events = package.load('core.content_events')


class ExampleTests(unittest.TestCase):
    def test_distributed_example_end_to_end(self):
        root = Path(__file__).resolve().parents[1] / 'examples/multi_mod'
        names = ['neocore_example_addon', 'neocore_example_base']
        specs = [{'folder': str(root / name), 'entrypoints': {
            name: 'example.' + name + '.Main:start'}} for name in names]
        previous = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        session = None
        try:
            session = extracted.ExtractedModSession(specs, os, sys)
            self.assertEqual(session.loader.order, list(reversed(names)))
            self.assertTrue(all(row['ready'] for row in session.loader.activate().values()))
            states = [session.loader.contexts[name].instance for name in names]
            driver = events.ContentTickDriver(session.loader, 'SERVER')
            for unused in range(30):
                driver.on_tick()
            self.assertEqual([state['ticks'] for state in states], [20, 20])
            self.assertEqual(len(session.loader.registries['neocore:example']), 2)
            session.close()
            self.assertTrue(all(state['closed'] for state in states))
            self.assertNotIn('example.neocore_example_base.Main', sys.modules)
        finally:
            if session is not None:
                session.close()
            sys.dont_write_bytecode = previous


if __name__ == '__main__':
    unittest.main()
