import unittest


class TestGenearate(unittest.TestCase):

    def setUp(self):
        self.seq = range(10)

    def test_smoke(self):
        "Basic smoke test that should pickup any silly errors"
        import external_naginator

if __name__ == '__main__':
    unittest.main()
