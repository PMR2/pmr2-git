import unittest

from pmr2.git.ext import parse_gitmodules


class GitModuleTestCase(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_000_submodule(self):
        result = parse_gitmodules(
            '[submodule "ext/import1"]\n'
            '\tpath = ext/import1\n'
            '\turl = http://models.example.com/w/import1\n'
        )
        self.assertEqual(result, {
            'ext/import1': 'http://models.example.com/w/import1',
        })

    def test_001_submodule(self):
        result = parse_gitmodules(
            '[submodule "ext/import1"]\n'
            '\tpath = ext/import1\n'
            '\turl = http://models.example.com/w/import1\n'
            '\n'
            '[submodule "ext/import2"]\n'
            '\tpath = ext/import2\n'
            '\turl = http://models.example.com/w/import2\n'
        )
        self.assertEqual(result, {
            'ext/import1': 'http://models.example.com/w/import1',
            'ext/import2': 'http://models.example.com/w/import2',
        })

    def test_002_submodule_section_already_added(self):
        result = parse_gitmodules(
            '[submodule "ext/import1"]\n'
            '\tpath = ext/import1\n'
            '\turl = http://models.example.com/w/import1\n'
            '\n'
            '\tpath = ext/import2\n'
            '\turl = http://models.example.com/w/import2\n'
        )
        self.assertEqual(result, {
            'ext/import1': 'http://models.example.com/w/import1',
        })

    def test_003_submodule_equalsign(self):
        result = parse_gitmodules(
            '[submodule "simp=3"]\n'
            '\tpath = simp=3\n'
            '\turl = http://models.example.com/w/simp=3\n'
        )
        self.assertEqual(result, {
            'simp=3': 'http://models.example.com/w/simp=3',
        })


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(GitModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.main()
