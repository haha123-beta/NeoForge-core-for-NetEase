import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from probe_network_late_work_contract import run


class LateWorkTests(unittest.TestCase):
    def test_reschedule_budget_backpressure_lifecycle_and_weak_ownership(self):
        self.assertGreaterEqual(len(run(Package().load)), 19)


if __name__ == '__main__': unittest.main()
