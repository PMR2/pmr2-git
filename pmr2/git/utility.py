import re
from os.path import basename
from cStringIO import StringIO
import mimetypes

import zope.component

from pygit2 import Signature
from pygit2 import Repository
from pygit2 import Tree
from pygit2 import Blob
from pygit2 import Tag
from pygit2 import Commit
from pygit2 import discover_repository, init_repository
from pygit2 import GIT_SORT_TIME

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
    def _commit(self):
        return self.__commit

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
        return name.split('/')[-1]

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

    def _get_obj(self, path, cls=None):
        try:
            fragments = list(reversed(path.split('/')))
            node = self.repo.revparse_single(self.rev).tree
            while fragments:
                fragment = fragments.pop()
                if not fragment == '':
                    # no empty string entries, also skips over '//' and
                    # leaves the final node (if directory) as the tree.
                    node = self.repo.get(node[fragment].oid)
            if cls is None or isinstance(node, cls):
                return node
        except KeyError:
              # can't find what is needed in repo, raised by pygit2
            raise PathNotFoundError('path not found')

        # not what we were looking for.
        if cls == Tree:
            raise PathNotDirError('path not dir')
        # default
        # if cls == Blob:
        raise PathNotFoundError('path not found')

    def file(self, path):
        return self._get_obj(path, Blob).data

    def fileinfo(self, path, blob=None):
        if blob is None:
            blob = self._get_obj(path, Blob)
        return {
            'author': '%s <%s>' % (
                self._commit.committer.name,
                self._commit.committer.email,
            ),
            'permissions': '',
            'desc': self._commit.message,
            'node': self._commit.hex,
            'date': self._commit.committer.time,  # raw unix
            'size': blob.size,
            'basename': path.split('/')[-1],
            'file': path,
            'mimetype': lambda: mimetypes.guess_type(blob.data)[0]
                or 'application/octet-stream',
            'contents': lambda: node.read_raw(),
            'baseview': 'file',
            'fullpath': None,
            'contenttype': None,
            'external': None,
        }

    def files(self):
        def _files(tree, current_path=None):
            results = []
            for node in tree:
                if current_path:
                    name = '/'.join([current_path, node.name])
                else:
                    name = node.name

                if isinstance(self.repo.get(node.oid), Blob):
                    results.append(name)
                elif isinstance(self.repo.get(node.oid), Tree):
                    results.extend(_files(self.repo.get(node.oid, name), name))
            return results

        commit = self.repo.revparse_single(self.rev)
        results = _files(commit.tree)
        return results

    def listdir(self, path):
        def strippath(_path):
            frags = path.split('/')
            while frags:
                if frags[:-1] != ['']:
                    break
                frags.pop()
            return '/'.join(frags)

        path = strippath(path)

        if path:
            tree = self._get_obj(path, Tree)
        else:
            tree = self._commit.tree

        def _listdir():
            if path:
                yield self.format(**{
                    'permissions': 'drwxr-xr-x',
                    'contenttype': None,
                    'node': self.rev,
                    'date': '',
                    'size': '',
                    'path': '%s/..' % path,
                    'desc': '',
                    'contents': '',  # XXX
                    # 'emptydirs': '/'.join(emptydirs),
                })

            # TODO submodule handling
            # this involves linking the git submodule definitions with
            # the commit objects found here.

            # return trees first:
            for entry in tree:
                node = self.repo.get(entry.oid)
                if not isinstance(node, Tree):
                    continue

                fullpath = path and '%s/%s' % (path, entry.name) or entry.name

                yield self.format(**{
                    'permissions': 'drwxr-xr-x',
                    'contenttype': 'folder',
                    'node': self.rev,
                    'date': '',
                    'size': '',
                    'path': fullpath,
                    'desc': '',
                    'contents': '',  # XXX
                })

            # then return files
            for entry in tree:
                node = self.repo.get(entry.oid)
                if not isinstance(node, Blob):
                    continue

                fullpath = path and '%s/%s' % (path, entry.name) or entry.name

                yield self.format(**{
                    'permissions': '-rw-r--r--',
                    'contenttype': 'file',
                    'node': self.rev,
                    'date': self._commit.committer.time,
                    'size': str(node.size),
                    'path': fullpath,
                    'desc': self._commit.message,
                    'contents': lambda: node.read_raw(),
                })

        return _listdir()

    def pathinfo(self, path):
        obj = self._get_obj(path)
        if isinstance(obj, Blob):
            return self.fileinfo(path, obj)
        return self.format(**{
            'permissions': 'drwxr-xr-x',
            'node': self.rev,
            'date': '',
            'size': '',
            'path': path,
            'contents': lambda: self.listdir(path)
        })

    def log(self, start, count, branch=None, shortlog=False):
        """
        start and branch are literally the same thing.
        """

        try:
            rev = self.repo.revparse_single(start).hex
        except KeyError:
            raise RevisionNotFoundError('revision %s not found' % start)

        def _log():
            for pos, commit in enumerate(self.repo.walk(rev, GIT_SORT_TIME)):
                if pos == count:
                    raise StopIteration
                yield {
                    'author': commit.committer.name,
                    'date': commit.committer.time,
                    'node': commit.hex,
                    'rev': commit.hex,
                    'desc': commit.message
                }

        return _log()
