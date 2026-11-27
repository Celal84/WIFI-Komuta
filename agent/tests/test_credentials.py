import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import credentials as c  # noqa: E402

class T(unittest.TestCase):
    def test_detect(self):
        self.assertEqual(c.detect_brand('<title>TP-Link Archer</title>'), 'TP-Link')
        self.assertEqual(c.detect_brand('Welcome to Superonline modem'), 'Turkcell Superonline')
        self.assertEqual(c.detect_brand('ZXHN H168N', 'Server: ZTE'), 'ZTE')
        self.assertIsNone(c.detect_brand('random page'))

    def test_candidates_order(self):
        cand = c.candidates('TP-Link')
        self.assertEqual(cand[0][:2], ('admin', 'admin'))  # marka ilk
        pairs = [(u, p) for u, p, _ in cand]
        self.assertEqual(len(pairs), len(set(pairs)))      # yinelenme yok
        self.assertIn(('user', 'user'), pairs)             # EX serisi dahil

    def test_extra_first(self):
        cand = c.candidates(None, extra=[('xy', 'zz')])
        self.assertEqual(cand[0][:2], ('xy', 'zz'))

    def test_is_default(self):
        self.assertTrue(c.is_default('admin', 'admin'))
        self.assertTrue(c.is_default('user', 'user'))
        self.assertFalse(c.is_default('celal', 'S3cret!'))

if __name__ == '__main__':
    unittest.main()
