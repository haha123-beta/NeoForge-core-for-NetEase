import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
events = Package().load('neoforge.event.base')


class EventOverloadTests(unittest.TestCase):
    def test_post_returns_the_same_event_for_original_java_callers(self):
        bus = events.IEventBus()
        event = events.CancelableEvent()
        bus.addListener(events.CancelableEvent, lambda received: received.setCanceled(True))
        self.assertIs(bus.post(event), event)
        self.assertTrue(event.isCanceled())

    def test_priority_cancellation_and_stable_registration_order(self):
        bus, seen = events.IEventBus(), []
        def cancel(event):
            seen.append('high')
            event.setCanceled(True)
        bus.addListener(events.EventPriority.LOW, events.CancelableEvent, lambda event: seen.append('skip'))
        bus.addListener(events.EventPriority.HIGH, events.CancelableEvent, cancel)
        bus.addListener(events.EventPriority.LOW, True, events.CancelableEvent, lambda event: seen.append('low1'))
        bus.addListener(events.EventPriority.LOW, True, events.CancelableEvent, lambda event: seen.append('low2'))
        bus.post(events.CancelableEvent())
        self.assertEqual(seen, ['high', 'low1', 'low2'])

    def test_unregister_does_not_remove_other_lambda(self):
        bus, seen = events.IEventBus(), []
        first, second = lambda event: seen.append(1), lambda event: seen.append(2)
        bus.addListener(events.Event, first)
        bus.addListener(events.Event, second)
        self.assertEqual(bus.unregister(first), 1)
        bus.post(events.Event())
        self.assertEqual(seen, [2])

    def test_missing_type_is_not_silently_registered_for_every_event(self):
        bus = events.IEventBus()
        def listener(event):
            pass
        with self.assertRaises(Exception):
            bus.addListener(listener)
        listener.__neocore_event_type__ = events.Event
        bus.addListener(listener)
        self.assertEqual(bus.listenerCount(), 1)


if __name__ == '__main__':
    unittest.main()
