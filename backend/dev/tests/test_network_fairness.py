import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from probe_network_fairness_contract import run


class NetworkFairnessTests(unittest.TestCase):
    def test_replenishing_channels_frames_membership_and_failure_budget(self):
        results = run(Package().load)
        self.assertEqual(len(results), 8)


if __name__ == '__main__': unittest.main()
