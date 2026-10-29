import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from probe_stability_r49_contract import run


class StabilityR49Tests(unittest.TestCase):
    def test_unicode_errors_queue_diagnostics_and_world_rebind(self):
        self.assertGreaterEqual(len(run(Package().load)), 17)


if __name__ == '__main__': unittest.main()
