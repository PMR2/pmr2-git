from os.path import dirname
from os.path import join

import zope.component
from zope.component import testing
import zope.interface
from Testing import ZopeTestCase as ztc
from Zope2.App import zcml
from Products.Five import fiveconfigure
from Products.PloneTestCase import PloneTestCase as ptc
from Products.PloneTestCase.layer import PloneSite
from Products.PloneTestCase.layer import onsetup
from Products.PloneTestCase.layer import onteardown

import pmr2.testing
from pmr2.app.workspace.content import WorkspaceContainer
from pmr2.app.workspace.content import Workspace
from pmr2.app.workspace.tests.base import WorkspaceDocTestCase
from pmr2.app.exposure.tests.base import ExposureDocTestCase

from pmr2.git.interfaces import IGitWorkspace


@onsetup
def setup():
    import pmr2.git
    fiveconfigure.debug_mode = True
    zcml.load_config('configure.zcml', pmr2.git)
    zcml.load_config('test.zcml', pmr2.testing)
    fiveconfigure.debug_mode = False
    ztc.installPackage('pmr2.app')

@onteardown
def teardown():
    pass

setup()
teardown()
# XXX dependant on pmr2.app still
ptc.setupPloneSite(products=('pmr2.app',))


class GitDocTestCase(ExposureDocTestCase):

    def setUp(self):
        # create real Hg repos, to be called only after workspace is
        # created and model root path is assigned
        super(GitDocTestCase, self).setUp()

        import pmr2.git.tests
        from pmr2.app.workspace.content import Workspace
        from pmr2.git.tests import util

        p = self.pmr2.createDir(self.portal.workspace)
        util.extract_archive(p)

        self.portal.w = WorkspaceContainer('w')
        # yes there are duplicates but the extra copies shouldn't matter
        util.extract_archive(self.pmr2.createDir(self.portal.w))

        p2a_test = join(dirname(pmr2.testing.__file__), 'pmr2.app.testdata.tgz')
        util.extract_archive(p, p2a_test)

        self.repodata_revs = util.ARCHIVE_REVS
        self.rdfmodel_revs = [
            'b94d1701154be42acf63ee6b4bd4a99d09ba043c',
            '2647d4389da6345c26d168bbb831f6512322d4f9',
            '006f11cd9211abd2a879df0f6c7f27b9844a8ff2',
        ]

        def mkgit_workspace(name, target=self.portal.workspace):
            # XXX temporary method to work with existing tests until
            # this is replaced
            w = Workspace(name)
            w.storage = u'git'
            w.title = u''
            w.description = u''
            zope.interface.alsoProvides(w, IGitWorkspace)
            target[name] = w

        mkgit_workspace('import1', self.portal.w)
        mkgit_workspace('import2', self.portal.w)
        mkgit_workspace('repodata')
        mkgit_workspace('rdfmodel')
        mkgit_workspace('simple1')
        mkgit_workspace('simple2')
        mkgit_workspace('simple3')
