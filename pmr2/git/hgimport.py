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
import zope.interface
from OFS.interfaces import ITraversable

from pmr2.app.workspace.interfaces import IStorage
from pmr2.app.workspace.interfaces import IStorageUtility
from pmr2.app.workspace.interfaces import IWorkspace
from pmr2.app.settings.interfaces import IPMR2GlobalSettings


@zope.interface.implementer(IWorkspace, ITraversable)
class EmbeddedWorkspace(object):

    def __init__(self, workspace, subpath, storage=u'mercurial'):
        self.workspace = workspace
        self.subpath = subpath
        self.storage = storage

    def getPhysicalPath(self):
        return (self.workspace.getPhysicalPath() +
            tuple(self.subpath.split('/')))


def get_hgsubs(hg_storage):
    try:
        subrepos = hg_storage.file('.hgsub')
    except:
        return []

    return [(x.strip(), y.strip()) for x, y in [
        i.split('=', 1) for i in hg_storage.file('.hgsub').splitlines()]]


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

    def hg_to_git(self, workspace, set_remote=False, rename_remote=None):
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
            hgsubs = get_hgsubs(hg_storage)
            if not hgsubs:
                raise RuntimeError('Conversion failed with no subrepos found.')
            hg_up = Popen(['hg', 'up', '-C'],
                cwd=storage_path, stdout=PIPE, stderr=PIPE)
            hg_up.communicate()

            if hg_up.returncode != 0:
                raise RuntimeError('hg update failed on subrepo')

            for subpath, url in hgsubs:
                embedded = EmbeddedWorkspace(workspace, subpath)
                self.hg_to_git(embedded, True, rename_remote)

            p = Popen([self.hg_fast_export, '-r', '.'],
                cwd=storage_path, env=self.env, stdout=PIPE, stderr=PIPE)
            self.last_results = p.communicate()
            if p.returncode != 0:
                raise RuntimeError(
                    'Conversion failed despite subrepo handling.')
        
        workspace.storage = u'git'

        if set_remote:
            remote = [v for s, n, v in hg_storage.storage._ui.walkconfig()
                if s == 'paths' and n == 'default']

            if callable(rename_remote):
                remote = rename_remote(remote)

            pr = Popen(['git', 'remote', 'add', 'origin'] + remote,
                cwd=storage_path, stdout=PIPE, stderr=PIPE)
            pr.communicate()

        # need to commit the changes to effect them.

    def batch_migrate(self, portal, rename_remote=None):
        results = portal.portal_catalog(portal_type='Workspace')
        # for every workspace in the result from the thing
        # trap exception
        # record the failures.

        fail = []
        success = []

        for b in results:
            workspace = b.getObject()
            try:
                self.hg_to_git(workspace, rename_remote=rename_remote)
            except TypeError:
                continue
            except RuntimeError:
                fail.append(b.getPath())
                continue
            success.append(b.getPath())

        return success, fail
