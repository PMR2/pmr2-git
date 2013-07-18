import re
from os.path import basename
from cStringIO import StringIO
import zope.component

from pygit2 import Signature
from pygit2 import Repository
from pygit2 import discover_repository, init_repository
from pygit2 import GIT_FILEMODE_BLOB, GIT_FILEMODE_TREE
from pygit2 import GIT_OBJ_COMMIT, GIT_OBJ_TREE, GIT_OBJ_BLOB, GIT_OBJ_TAG

from pmr2.app.settings.interfaces import IPMR2GlobalSettings
from pmr2.app.workspace.exceptions import *
from pmr2.app.workspace.interfaces import IWorkspace
from pmr2.app.workspace.storage import StorageUtility
from pmr2.app.workspace.storage import BaseStorage


class GitStorageUtility(StorageUtility):
    title = 'Git'

    def create(self, context):
        rp = zope.component.getUtility(IPMR2GlobalSettings).dirOf(context)
        raise NotImplementedError

    def acquireFrom(self, context):
        return GitStorage(context)

    def isprotocol(self, request):
        # TODO implement the protocol support and use that to check.
        return False

    def protocol(self, context, request):
        raise NotImplementedError

    def syncIdentifier(self, context, identifier):
        # XXX should be named syncWithIdentifier
        raise NotImplementedError

    def syncWorkspace(self, context, source):
        # XXX should be named syncWithWorkspace
        # TODO verify that this works as intended when above is
        # implemented.
        remote = zope.component.getUtility(IPMR2GlobalSettings).dirOf(source)
        return self.syncIdentifier(context, remote)


class GitStorage(BaseStorage):

    # One of the future item is to modify this to more closely interact
    # with the mercurial library rather than go through one of our
    # previous abstractions.
    
    def __init__(self, context):
        rp = zope.component.getUtility(IPMR2GlobalSettings).dirOf(context)
        self.context = context

        try:
            self.repo = Repository(discover_repository(rp))
        except KeyError:
            # discover_repository may have failed.
            raise PathInvalidError('repository does not exist at path')

        self.checkout('HEAD')

    __datefmt_filter = {
        'rfc2822': 'rfc822date',
        'rfc3339': 'rfc3339date',
        'iso8601': 'isodate',
    }

    _archiveFormats = {
        'zip': ('Zip File', '.zip', 'application/zip',),
        'tgz': ('Tarball (gzipped)', '.tar.gz', 'application/x-tar',),
    }

    @property
    def datefmtfilter(self):
        return GitStorage.__datefmt_filter[self.datefmt]

    @property
    def rev(self):
        if self.__commit:
            return self.__commit.hex
        else:
            # cripes yet more bad practices from before.
            return '0' * 40

    @property
    def shortrev(self):
        # TODO this is an interim solution.
        return self.rev[:12]

    def archive_zip(self):
        arctype = 'zip'
        raise NotImplementedError

    def archive_tgz(self):
        arctype = 'tgz'
        raise NotImplementedError

    def basename(self, name):
        raise NotImplementedError

    def checkout(self, rev=None):
        # All the bad practices I did when building pmr2.mercurial will
        # be carried into here until a cleaner method is provided.
        try:
            self.__commit = self.repo.revparse_single(rev)
        except KeyError:
            # probably a new repo.
            self.__commit = None

    # Unit tests would be useful here, even if this class will only
    # produce output for the browser classes.

    def _getBlob(self, path):
        fragments = list(reversed(path.split('/')))
        node = self.repo.revparse_single(self.rev).tree
        while fragments:
            node = self.repo.get(node[fragments.pop()].oid)
        if node.type == GIT_OBJ_BLOB:
            return node.data
        raise KeyError

    def file(self, path):
        try:
            return self._getBlob(path)
        except KeyError:
            raise PathNotFoundError('path not found')

    def fileinfo(self, path):
        raise NotImplementedError

    def files(self):
        def _files(tree, current_path=None):
            results = []
            for node in tree:
                if current_path:
                    name = '/'.join([current_path, node.name])
                else:
                    name = node.name

                if self.repo.get(node.oid).type == GIT_OBJ_BLOB:
                    results.append(name)
                elif self.repo.get(node.oid).type == GIT_OBJ_TREE:
                    results.extend(_files(self.repo.get(node.oid, name), name))
            return results

        commit = self.repo.revparse_single(self.rev)
        results = _files(commit.tree)
        return results

    def listdir(self, path):
        raise NotImplementedError

    def pathinfo(self, path):
        raise NotImplementedError

    def log(self, start, count, branch=None, shortlog=False):
        raise NotImplementedError
