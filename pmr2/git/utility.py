import re
from os.path import basename, join
from cStringIO import StringIO
from hashlib import sha1
import logging
import mimetypes
from datetime import datetime
from dateutil.tz import tzoffset

import zope.component
import zope.interface

from magic import Magic

from pygit2 import Signature
from pygit2 import Repository
from pygit2 import Tree
from pygit2 import Blob
from pygit2 import Tag
from pygit2 import Commit
from pygit2 import discover_repository, init_repository
from pygit2 import GIT_SORT_TIME

from dulwich.repo import Repo
from dulwich.client import HttpGitClient

from pmr2.app.settings.interfaces import IPMR2GlobalSettings
from pmr2.app.workspace.exceptions import *
from pmr2.app.workspace.interfaces import IWorkspace
from pmr2.app.workspace.storage import StorageUtility
from pmr2.app.workspace.storage import BaseStorage

from .ext import parse_gitmodules, archive_tgz, archive_zip
from .interfaces import IGitWorkspace

GIT_MODULE_FILE = '.gitmodules'

logger = logging.getLogger('pmr2.git')

magic = Magic(mime=True)


def rfc2822(committer):
    return datetime.fromtimestamp(committer.time,
        tzoffset(None, committer.offset * 60))


class GitStorageUtility(StorageUtility):
    title = u'Git'
    command = u'git'
    clone_verb = u'clone'

    def create(self, context):
        rp = zope.component.getUtility(IPMR2GlobalSettings).dirOf(context)
        self._create(rp)
        # Also tag the object with our custom interface.
        zope.interface.alsoProvides(context, IGitWorkspace)

    def _create(self, rp):
        repo = init_repository(join(rp, '.git'), bare=True)
        # Allow receivepack by default for git push.
        repo.config.set_multivar('http.receivepack', '', 'true')

    def acquireFrom(self, context):
        return GitStorage(context)

    def isprotocol(self, request):
        # Git does things differently, so we are going to offer a
        # dedicated view instead.
        return False

    def protocol(self, context, request):
        raise NotImplementedError

    def syncIdentifier(self, context, identifier):
        # should be named syncWithIdentifier
        rp = zope.component.getUtility(IPMR2GlobalSettings).dirOf(context)

        # XXX assuming master.
        branch_name = 'master'
        # XXX when we figure out how to let users pick their primary
        # branches, use what they specify instead.
        branch = "refs/heads/%s" % branch_name

        # Since the network and remote handling aspect between dulwich
        # and pygit2 have different strengths, i.e. dulwich has better
        # remote network handling and fetching without having to create
        # a named remote, and pygit2 for determining merge base for
        # fast-forwarding the local to remote if applicable.

        # Process starts with dulwich.
        # 0. Connect to remote
        # 1. Fetch content
        # 2. Acquire merge target pairs.

        merge_target = self._fetch(rp, identifier, branch)

        # Then use pygit2.
        # 3. If merge base between the two have diverted, abort.
        # 4. If remote is fresher, fast forward local.

        return self._fast_forward(rp, merge_target, branch)

    def _fetch(self, local_path, remote_id, branch):
        # dulwich repo
        local = Repo(local_path)

        # Determine the fetch strategy based on protocol.
        if remote_id.startswith('http'):
            root, frag = remote_id.rsplit('/', 1)
            client = HttpGitClient(root)
            try:
                remote_refs = client.fetch(frag, local)
            except:
                raise ValueError('error fetching from remote: %s' % remote_id)
        elif remote_id.startswith('/'):
            client = Repo(remote_id)
            remote_refs = client.fetch(local)
        else:
            raise ValueError('remote not supported: %s' % remote_id)

        if branch in remote_refs:
            merge_target = remote_refs[branch]
        else:
            # Unknown, fall back to HEAD.
            merge_target = remote_refs['HEAD']

        # Switch usage to libgit2/pygit2 repo for "merging".

        return merge_target

    def _fast_forward(self, local_path, merge_target, branch):
        # pygit2 repo
        repo = Repository(discover_repository(local_path))

        # convert merge_target from hex into oid.
        fetch_head = repo.revparse_single(merge_target)

        # try to resolve a common anscestor between fetched and local
        try:
            head = repo.revparse_single(branch)
        except:
            # New repo, create the reference now and finish.
            repo.create_reference(branch, fetch_head.oid)
            return True, 'Created new branch: %s' % branch

        if head.oid == fetch_head.oid:
            return True, 'Source and target are identical.'

        # raises KeyError if no merge bases found.
        oid = repo.merge_base(head.oid, fetch_head.oid)

        # Three different outcomes between the remaining cases.
        if oid.hex not in (head.oid.hex, fetch_head.oid.hex):
            # common ancestor is beyond both of these, not going to
            # attempt a merge here and will assume this:
            raise ValueError('heads will diverge.')
        elif oid.hex == fetch_head.oid.hex:
            # Remote is the common base, so nothing to do.
            return True, 'No new changes found.'

        # This case remains: oid.hex == head.oid.hex
        # Local is the common base, so remote is newer, fast-forward.
        try:
            ref = repo.lookup_reference(branch)
            ref.delete()
        except KeyError:
            # assume repo is empty.
            pass

        repo.create_reference(branch, fetch_head.oid)

        return True, 'Fast-forwarded branch: %s' % branch

    def syncWorkspace(self, context, source):
        # should be named syncWithWorkspace
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

    _archiveFormats = {
        'zip': ('Zip File', '.zip', 'application/zip',),
        'tgz': ('Tarball (gzipped)', '.tar.gz', 'application/x-tar',),
    }

    @property
    def _commit(self):
        return self.__commit

    @property
    def rev(self):
        if self.__commit:
            return self.__commit.hex
        return None

    @property
    def shortrev(self):
        # TODO this is an interim solution.
        if self.rev:
            return self.rev[:12]

    def archive_zip(self):
        return archive_zip(self.repo, self._commit, self.context.id)

    def archive_tgz(self):
        return archive_tgz(self.repo, self._commit, self.context.id)

    def basename(self, name):
        return name.split('/')[-1]

    def checkout(self, rev=None):
        # All the bad practices I did when building pmr2.mercurial will
        # be carried into here until a cleaner method is provided.
        # XXX None is invalid rev.
        if rev is None:
            rev = 'HEAD'

        self._lastcheckout = rev
        try:
            self.__commit = self.repo.revparse_single(rev)
        except KeyError:
            if rev == 'HEAD':
                # probably a new repo.
                self.__commit = None
                return
            raise RevisionNotFoundError('revision %s not found' % rev)
            # otherwise a RevisionNotFoundError should be raised.

    # Unit tests would be useful here, even if this class will only
    # produce output for the browser classes.

    def _get_empty_root(self):
        return {'': '_empty_root'}

    def _get_obj(self, path, cls=None):
        if path == '' and self._commit is None:
            # special case
            return self._get_empty_root()

        root = self._commit.tree
        try:
            breadcrumbs = []
            fragments = list(reversed(path.split('/')))
            node = root
            oid = None
            while fragments:
                fragment = fragments.pop()
                if not fragment == '':
                    # no empty string entries, also skips over '//' and
                    # leaves the final node (if directory) as the tree.
                    oid = node[fragment].oid
                    node = self.repo.get(oid)
                breadcrumbs.append(fragment)
                if node is None:
                    # strange.  Looks like it's either submodules only
                    # have entry nodes or pygit2 doesn't fully support
                    # this.  Try to manually resolve the .gitmodules
                    # file.
                    if not cls == Blob:
                        # If we want a file, forget it.
                        submods = parse_gitmodules(self.repo.get(
                            root[GIT_MODULE_FILE].oid).data)
                        submod = submods.get('/'.join(breadcrumbs))
                        if submod:
                            fragments.reverse()
                            return {
                                '': '_subrepo',
                                'location': submod,
                                'path': '/'.join(fragments),
                                'rev': oid.hex,
                            }
                    raise PathNotDirError('path not dir')

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
            'email': self._commit.committer.email,
            'permissions': '',
            'desc': self._commit.message,
            'node': self._commit.hex,
            'date': rfc2822(self._commit.committer),
            'size': blob.size,
            'basename': path.split('/')[-1],
            'file': path,
            'mimetype': lambda: mimetypes.guess_type(path)[0]
                or magic.from_buffer(blob.read_raw()[:1000]),
            'contents': blob.read_raw,
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

                obj = self.repo.get(node.oid)
                if isinstance(obj, Blob):
                    results.append(name)
                elif isinstance(obj, Tree):
                    results.extend(_files(obj, name))
            return results

        if not self._commit:
            return []
        results = _files(self._commit.tree)
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
                if node is not None:
                    continue

                fullpath = path and '%s/%s' % (path, entry.name) or entry.name

                yield self.format(**{
                    'permissions': 'lrwxrwxrwx',
                    'contenttype': 'git',  # always git.
                    'node': self.rev,
                    'date': '',
                    'size': '',
                    'path': fullpath,
                    'desc': '',
                    'contents': '',  # XXX
                })

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
                    'date': rfc2822(self._commit.committer).date(),
                    'size': str(node.size),
                    'path': fullpath,
                    'desc': self._commit.message,
                    'contents': lambda: node.read_raw(),
                })

        return _listdir()

    def pathinfo(self, path):
        if self._commit is None: 
            if self._lastcheckout != 'HEAD':
                raise PathNotFoundError('commit not found')
            # give an exception to HEAD

        obj = self._get_obj(path)
        if isinstance(obj, Blob):
            return self.fileinfo(path, obj)
        elif isinstance(obj, dict):
            if obj[''] == '_subrepo':
                return self.format(**{
                    'permissions': 'lrwxrwxrwx',
                    'contenttype': None,
                    'node': self.rev,
                    'date': '',
                    'size': '',
                    'path': path,
                    'desc': '',
                    'contents': '',
                    'external': obj,
                })

            elif obj[''] == '_empty_root':
                return self.format(**{
                    'permissions': 'drwxr-xr-x',
                    'node': self.rev,
                    'date': '',
                    'size': '',
                    'path': path,
                    'contents': lambda: [],
                })

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

        def _log(iterator):
            for pos, commit in iterator:
                if pos == count:
                    raise StopIteration
                yield {
                    'author': commit.committer.name,
                    'email': self._commit.committer.email,
                    'date': rfc2822(commit.committer).date(),
                    'node': commit.hex,
                    'rev': commit.hex,
                    'desc': commit.message
                }

        if start is None:
            # assumption.
            start = 'HEAD'
            try:
                self.repo.revparse_single(start)
            except KeyError:
                return _log([])

        try:
            rev = self.repo.revparse_single(start).hex
        except KeyError:
            raise RevisionNotFoundError('revision %s not found' % start)

        iterator = enumerate(self.repo.walk(rev, GIT_SORT_TIME))

        return _log(iterator)
