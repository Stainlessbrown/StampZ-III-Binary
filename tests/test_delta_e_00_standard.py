"""CIEDE2000 official worked examples (Sharma, Wu and Dalal, 2005)."""
import unittest
from utils.delta_e_00 import delta_e_00

PAIRS = [
    ((50, 2.6772, -79.7751), (50, 0, -82.7485), 2.0425),
    ((50, 3.1571, -77.2803), (50, 0, -82.7485), 2.8615),
    ((50, 2.8361, -74.0200), (50, 0, -82.7485), 3.4412),
    ((50, -1.3802, -84.2814), (50, 0, -82.7485), 1.0000),
    ((50, -1.1848, -84.8006), (50, 0, -82.7485), 1.0000),
    ((50, -0.9009, -85.5211), (50, 0, -82.7485), 1.0000),
]
class TestDeltaE00(unittest.TestCase):
    def test_reference_pairs(self):
        for a,b,expected in PAIRS:
            with self.subTest(expected=expected, a=a):
                self.assertAlmostEqual(delta_e_00(a,b),expected,delta=0.0001)
    def test_identity_and_symmetry(self):
        for a,b,_ in PAIRS:
            self.assertAlmostEqual(delta_e_00(a,a),0.0,places=12)
            self.assertAlmostEqual(delta_e_00(a,b),delta_e_00(b,a),places=10)

if __name__ == "__main__":
    unittest.main()
