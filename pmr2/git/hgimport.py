"""
This module is only meant to be used for mercurial to git migration, and
it assumes the availability of hg-fast-export, which is accessed via
system calls through the subprocess module.  This is done because that
particular script is a mix shell/python script and is written as a
script and not a real module, making dependency management with the main
instance impossible, thus that needs to be installed separately into its
own virtualenv and extra parameters must be invoked before this can be
used.  This ultimately meant that this be ideally used from the debug
shell and no front-end should be built for this.

Also this is written as a one-off migration tool. YMMV.
"""

from subprocess import Popen
from subprocess import PIPE

import zope.component
from pmr2.app.workspace.interfaces import IStorage
from pmr2.app.workspace.interfaces import IStorageUtility
from pmr2.app.settings.interfaces import IPMR2GlobalSettings


class Migrator(object):

    def __init__(self, hg_fast_export='hg-fast-export.sh', env={}):
        """
        Creates the helper migration class.  Example invocation:

        >>> import zope.component
        >>> from pmr2.git.hgimport import Migrator
        >>> zope.component.hooks.setSite(app.portal)
        >>> m = Migrator('/path/to/fast-export/hg-fast-export.sh',
        ...     env={'PYTHON': '/path/to/fast-export/.env/bin/python'})
        >>> 

        This assumes the `hg-fast-export.sh` script is only available
        from that subpath and that it needs to be invoked using the
        python binary in the virtual env created for it.

        Migration is simply

        >>> m.hg_to_git(app.portal.workspace.example)
        >>> import transaction
        >>> transaction.commit()
        """

        # environment variables.
        self.env = {
        }

        self.env.update(env)
        self.hg_fast_export = hg_fast_export

    def hg_to_git(self, workspace):
        if workspace.storage != u'mercurial':
            raise TypeError('%s is not a mercurial repo' % str(workspace))

        hg_storage = zope.component.getAdapter(workspace, IStorage)
        storage_path = zope.component.getUtility(IPMR2GlobalSettings
            ).dirOf(workspace)

        git_util = zope.component.getUtility(IStorageUtility, 'git')

        # create new workspace in-place
        new_storage = git_util.create(workspace)

        p = Popen([self.hg_fast_export, '-r', '.'],
            cwd=storage_path, env=self.env, stdout=PIPE, stderr=PIPE)
        self.last_results = p.communicate()
        if p.returncode != 0:
            raise RuntimeError('Conversion failed, most likely due to '
                'submodules which needs to be manually handled.')
        
        workspace.storage = u'git'

        # need to commit the changes to effect them.

    def batch_migrate(self, portal):
        results = portal.portal_catalog(portal_type='Workspace')
        # for every workspace in the result from the thing
        # trap exception
        # record the failures.

        fail = []
        success = []

        for b in results:
            workspace = b.getObject()
            try:
                self.hg_to_git(workspace)
            except TypeError:
                continue
            except RuntimeError:
                fail.append(b.getPath())
                continue
            success.append(b.getPath())

        return success, fail
