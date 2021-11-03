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
from dulwich.objects import Tree
from dulwich.objects import Blob
from dulwich.objects import Tag
from dulwich.objects import Commit
from pygit2 import discover_repository, init_repository
from pygit2 import GIT_SORT_TIME

import dulwich.objects
from dulwich.errors import NotGitRepository
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


def rfc2822(time, offset):
    return datetime.fromtimestamp(time, tzoffset(None, offset))


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
            self.repo = Repo(rp)
        except NotGitRepository:
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
            return self.__commit.id
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

    def revparse_single(self, rev):
        try:
            branches = self.repo.refs.as_dict('refs/heads')
            if rev in branches:
                rev = branches[rev]
            if rev == 'HEAD':
                return self.repo.get_object(self.repo.head())
            return self.repo.get_object(rev)
        except AssertionError:
            # fallback to use the real version
            repo = Repository(discover_repository(self.repo.path))
            revision = repo.revparse_single(rev).oid.hex
            return self.repo.get_object(revision)

    def checkout(self, rev=None):
        # All the bad practices I did when building pmr2.mercurial will
        # be carried into here until a cleaner method is provided.
        # XXX None is invalid rev.
        if rev is None:
            rev = 'HEAD'

        self._lastcheckout = rev
        try:
            self.__commit = self.revparse_single(rev)
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

        root = self.repo.get_object(self._commit.tree)
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
                    oid = node[fragment][-1]
                    try:
                        node = self.repo.get_object(oid)
                    except (AssertionError, KeyError) as e:
                        node = None
                breadcrumbs.append(fragment)
                if node is None:
                    # strange.  Looks like it's either submodules only
                    # have entry nodes or pygit2 doesn't fully support
                    # this.  Try to manually resolve the .gitmodules
                    # file.
                    if not cls == Blob:
                        # If we want a file, forget it.
                        submods = parse_gitmodules(self.repo.get_object(
                            root[GIT_MODULE_FILE][-1]).data)
                        submod = submods.get('/'.join(breadcrumbs))
                        if submod:
                            fragments.reverse()
                            return {
                                '': '_subrepo',
                                'location': submod,
                                'path': '/'.join(fragments),
                                'rev': oid,
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
            'author': self._commit.committer,
            'email': self._commit.committer.rsplit('<')[-1][:-1],
            'permissions': '',
            'desc': self._commit.message,
            'node': self._commit.id,
            'date': rfc2822(
                self._commit.commit_time, self._commit.commit_timezone),
            'size': blob.raw_length(),
            'basename': path.split('/')[-1],
            'file': path,
            'mimetype': lambda: mimetypes.guess_type(path)[0]
                or magic.from_buffer(blob.as_raw_string()[:1000]),
            'contents': blob.as_raw_string,
            'baseview': 'file',
            'fullpath': None,
            'contenttype': None,
            'external': None,
        }

    def files(self):
        def _files(tree, current_path=None):
            results = []
            for node in tree.items():
                if current_path:
                    name = '/'.join([current_path, node.path])
                else:
                    name = node.path

                try:
                    obj = self.repo.get_object(node.sha)
                except KeyError:
                    # assume this is a submodule type
                    continue

                if isinstance(obj, dulwich.objects.Blob):
                    results.append(name)
                elif isinstance(obj, dulwich.objects.Tree):
                    results.extend(_files(obj, name))
            return results

        if not self._commit:
            return []

        tree = self.repo.get_object(self._commit.tree)
        results = _files(tree)

        return results

    def roots(self, rev=None):
        if rev is not None:
            commit = self.revparse_single(rev)
        else:
            commit = self._commit
        walker = self.repo.get_walker(commit.id)
        return [e.commit.id for e in walker if not e.commit.parents]

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
            tree = self.repo.get_object(self._commit.tree)

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
            for entry in tree.items():
                try:
                    node = self.repo.get_object(entry.sha)
                except KeyError:
                    pass
                else:
                    continue

                fullpath = path and '%s/%s' % (path, entry.path) or entry.path

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
            for entry in tree.items():
                try:
                    node = self.repo.get_object(entry.sha)
                    if not isinstance(node, Tree):
                        continue
                except KeyError:
                    continue

                fullpath = path and '%s/%s' % (path, entry.path) or entry.path

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
            for entry in tree.items():
                try:
                    node = self.repo.get_object(entry.sha)
                    if not isinstance(node, Blob):
                        continue
                except KeyError:
                    continue

                fullpath = path and '%s/%s' % (path, entry.path) or entry.path

                yield self.format(**{
                    'permissions': '-rw-r--r--',
                    'contenttype': 'file',
                    'node': self.rev,
                    'date': rfc2822(
                        self._commit.commit_time, self._commit.commit_timezone
                    ),
                    'size': str(node.raw_length()),
                    'path': fullpath,
                    'desc': self._commit.message,
                    'contents': node.as_raw_string,
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
            for pos, walker_entry in iterator:
                if pos == count:
                    raise StopIteration
                commit = walker_entry.commit
                name, email = self._commit.committer.rsplit('<', 1)
                email = email[:-1]
                yield {
                    'author': name,
                    'email': email,
                    'date': rfc2822(
                        commit.commit_time, commit.commit_timezone
                    ),
                    'node': commit.id,
                    'rev': commit.id,
                    'desc': commit.message
                }

        if start is None:
            # assumption.
            start = 'HEAD'
            try:
                self.revparse_single(start)
            except KeyError:
                return _log([])

        try:
            rev = self.revparse_single(start).id
        except KeyError:
            raise RevisionNotFoundError('revision %s not found' % start)

        iterator = enumerate(self.repo.get_walker([rev]))

        return _log(iterator)

    def clonecmd(self):
        try:
            info = self.file('.gitmodules')
        except PathInvalidError:
            return ''

        return 'git clone --recursive %s' % self.context.absolute_url()
