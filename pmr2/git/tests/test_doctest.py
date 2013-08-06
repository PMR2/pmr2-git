from unittest import TestCase, TestSuite, makeSuite
import doctest

from Testing import ZopeTestCase as ztc

from pmr2.git.tests import base

def test_suite():
    browser = ztc.ZopeDocFileSuite(
        'README.rst', package='pmr2.git',
        test_class=base.GitDocTestCase,
        optionflags=doctest.NORMALIZE_WHITESPACE|doctest.ELLIPSIS,
    )
    synchronize = ztc.ZopeDocFileSuite(
        'synchronize.rst', package='pmr2.git',
        test_class=base.GitDocTestCase,
        optionflags=doctest.NORMALIZE_WHITESPACE|doctest.ELLIPSIS,
    )
    synchronize.level = 9001
    return TestSuite([browser, synchronize])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
