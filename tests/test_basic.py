import unittest


class TestGenearate(unittest.TestCase):

    def setUp(self):
        self.seq = range(10)

    def test_smoke(self):
        import generate

if __name__ == '__main__':
    unittest.main()
