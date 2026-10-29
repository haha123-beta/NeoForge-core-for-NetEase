import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from probe_network_session_contract import run


class NetworkSessionTests(unittest.TestCase):
    def test_native_bidirectional_lifecycle_and_failure_contracts(self):
        checks = run(Package().load)
        self.assertGreaterEqual(len(checks), 35)


if __name__ == '__main__': unittest.main()
