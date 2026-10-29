import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
package = Package()
loader = package.load('core.translated_loader')
events = package.load('core.content_events')


class ContentEventTests(unittest.TestCase):
    def test_both_sides_twenty_ticks_and_closed_session(self):
        for side in ('SERVER', 'CLIENT'):
            seen = []
            def start(ctx):
                ctx.game_bus.subscribe(lambda event: seen.append((ctx.mod_id, type(event).__name__)))
            manager = loader.TranslatedModLoader(lambda path: start, side=side)
            manager.load({'schema_version': 1, 'mods': [
                {'mod_id': 'one', 'entrypoint': 'start'},
                {'mod_id': 'two', 'entrypoint': 'start'}]})
            manager.activate()
            driver = events.ContentTickDriver(manager, side)
            for unused in range(30):
                driver.on_tick()
            self.assertEqual(driver.ticks, 20)
            self.assertEqual(len(seen), 80)
            self.assertEqual(seen[:4], [('one', 'Pre'), ('two', 'Pre'), ('one', 'Post'), ('two', 'Post')])
            manager.close()
            driver.on_tick()
            self.assertEqual(len(seen), 80)

    def test_shared_attribute_barrier_only_runs_once(self):
        registration = package.load('neoforge.event.entity.registration')
        seen = []
        def start(ctx):
            ctx.mod_bus.subscribe(lambda event: seen.append(event), registration.EntityAttributeCreationEvent)
        manager = loader.TranslatedModLoader(lambda path: start)
        manager.load({'schema_version': 1, 'mods': [{'mod_id': 'one', 'entrypoint': 'start'}]})
        bus = events.ContentModBus(manager)
        bus.freeze_registries()
        bus.post(registration.EntityAttributeCreationEvent())
        bus.post(registration.EntityAttributeCreationEvent())
        self.assertEqual(len(seen), 1)
        manager.close()


if __name__ == '__main__':
    unittest.main()
