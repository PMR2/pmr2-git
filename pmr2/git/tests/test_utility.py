import unittest
import tempfile
import shutil
import os
from time import time
import tarfile
import zipfile
from os.path import basename, dirname, join
from logging import getLogger
from cStringIO import StringIO

import zope.component
import zope.interface
from zope.component.hooks import getSiteManager
from zope.publisher.browser import TestRequest

from zope.configuration.xmlconfig import xmlconfig
from zope.component.tests import clearZCML

from pmr2.app.settings.interfaces import IPMR2GlobalSettings
from pmr2.app.workspace.exceptions import *
from pmr2.app.workspace.interfaces import IWorkspace, IStorage

from pygit2 import Repository
from pygit2 import init_repository
from pygit2 import Signature
from pygit2 import GIT_FILEMODE_BLOB, GIT_FILEMODE_TREE

import pmr2.git
from pmr2.git import *
from pmr2.git.interfaces import *
from pmr2.git.utility import *

from pmr2.git.tests import util

logger = getLogger('pmr2.git.tests')


class DummyWorkspace(object):
    zope.interface.implements(IWorkspace)
    def __init__(self, path):
        # Dummy value for use by the dummy settings object below.
        self.path = path
        self.storage = 'git'

    @property
    def id(self):
        return basename(self.path)


class GitSettings(object):
    zope.interface.implements(IPMR2GlobalSettings)
    def dirCreatedFor(self, obj):
        return obj.path

    # dirOf is used by GitStorageUtility to acquire the path
    dirOf = dirCreatedFor


class TestCase(unittest.TestCase):

    def setUp(self):
        # XXX split this out into the setup decorator?
        self.testdir = tempfile.mkdtemp()
        self.repodir = join(self.testdir, 'repodir')

        self.revs = []

        self.path = dirname(__file__)

        self.filelist = ['file1', 'file2', 'file3',]
        self.nested_name = 'nested/deep/dir/file'
        self.nested_file = 'This is\n\na deeply nested file\n'
        self.files = [open(join(self.path, i)).read() for i in self.filelist]
        self.msg = 'added some files'
        self.user = 'Tester'
        self.email = '<test@example.com>'

        # Note: to maintain consistency with mercurial (and possibly
        # other repo formats), nest the bare repo under `.git`.
        repo = init_repository(join(self.repodir, '.git'), bare=True)
        tbder = repo.TreeBuilder()

        tbder.insert('file1', repo.create_blob(self.files[0]),
            GIT_FILEMODE_BLOB)
        tbder.insert('file2', repo.create_blob(self.files[0]),
            GIT_FILEMODE_BLOB)
        commit = repo.create_commit('refs/heads/master',
            Signature('user1', '1@example.com', int(time()), 0),
            Signature('user1', '1@example.com', int(time()), 0),
            'added1', tbder.write(),
            [],
        )
        self.revs.append(commit.hex)

        tbder.insert('file1', repo.create_blob(self.files[1]),
            GIT_FILEMODE_BLOB)
        commit = repo.create_commit('refs/heads/master',
            Signature('user2', '2@example.com', int(time()), 0),
            Signature('user2', '2@example.com', int(time()), 0),
            'added2', tbder.write(),
            [self.revs[-1]],
        )
        self.revs.append(commit.hex)

        tbder.insert('file2', repo.create_blob(self.files[1]),
            GIT_FILEMODE_BLOB)
        tbder.insert('file3', repo.create_blob(self.files[0]),
            GIT_FILEMODE_BLOB)
        commit = repo.create_commit('refs/heads/master',
            Signature('user3', '3@example.com', int(time()), 0),
            Signature('user3', '3@example.com', int(time()), 0),
            'added3', tbder.write(),
            [self.revs[-1]],
        )
        self.revs.append(commit.hex)

        ntbder = repo.TreeBuilder()
        nnames = self.nested_name.split('/')
        ntbder.insert(nnames.pop(), repo.create_blob(self.nested_file),
            GIT_FILEMODE_BLOB)

        for n in reversed(nnames):
            ntree = ntbder.write()
            ntbder = repo.TreeBuilder()
            ntbder.insert(n, ntree, GIT_FILEMODE_TREE)

        # ntree is the final node, n is leftover from the iterator,
        # ntbder is extra and is ignored.
        tbder.insert(n, ntree, GIT_FILEMODE_TREE)
        commit = repo.create_commit('refs/heads/master',
            Signature('user3', '3@example.com', int(time()), 0),
            Signature('user3', '3@example.com', int(time()), 0),
            'added4', tbder.write(),
            [self.revs[-1]],
        )
        self.revs.append(commit.hex)

        self.fulllist = self.filelist + [self.nested_name]

        self.rev = commit.hex

        clearZCML()
        xmlconfig(open(join(pmr2.git.__path__[0], 'utility.zcml')))

        # register custom utility that would have normally been done.
        sm = getSiteManager()
        sm.registerUtility(GitSettings(), IPMR2GlobalSettings)
        self.settings = zope.component.getUtility(IPMR2GlobalSettings)
        self.workspace = DummyWorkspace(self.repodir)

        util.extract_archive(self.testdir)
        self.repodata = DummyWorkspace(join(self.testdir, 'repodata'))
        self.import1 = DummyWorkspace(join(self.testdir, 'import1'))
        self.import2 = DummyWorkspace(join(self.testdir, 'import2'))

        self.simple1 = DummyWorkspace(join(self.testdir, 'simple1'))
        self.simple2 = DummyWorkspace(join(self.testdir, 'simple2'))
        self.simple3 = DummyWorkspace(join(self.testdir, 'simple3'))

    def tearDown(self):
        shutil.rmtree(self.testdir)


class StorageTestCase(TestCase):

    def test_000_storage(self):
        # Direct instantiation
        storage = GitStorage(self.workspace)
        self.assert_(IStorage.providedBy(storage))

    def test_010_storage_base(self):
        storage = GitStorage(self.workspace)
        result = storage.files()
        self.assertEqual(result, self.fulllist)

    def test_101_storage_checkout(self):
        storage = GitStorage(self.workspace)
        storage.checkout(self.revs[0])
        result = storage.files()
        self.assertEqual(result, ['file1', 'file2',])

    def test_200_storage_log(self):
        storage = GitStorage(self.workspace)
        result = list(storage.log(self.revs[2], 2))
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['node'], self.revs[2])

    def test_201_storage_log(self):
        storage = GitStorage(self.workspace)
        result = list(storage.log(self.revs[2], 10))
        self.assertEqual(len(result), 3)

    def test_250_storage_log_revnotfound(self):
        storage = GitStorage(self.workspace)
        self.assertRaises(RevisionNotFoundError, storage.log, 'xxxxxxxxxx', 10)
        self.assertRaises(RevisionNotFoundError, storage.log, 'abcdef1234', 10)

    def test_300_storage_file(self):
        storage = GitStorage(self.workspace)
        file = storage.file('file3')
        self.assertEqual(file, self.files[0])

    def test_301_storage_file(self):
        storage = GitStorage(self.workspace)
        storage.checkout(self.revs[0])
        file = storage.file('file1')
        self.assertEqual(file, self.files[0])

    def test_302_storage_file(self):
        storage = GitStorage(self.workspace)
        # just for fun.
        storage.checkout(self.revs[0])
        storage.checkout(self.revs[3])
        file = storage.file(self.nested_name)
        self.assertEqual(file, self.nested_file)

    def test_350_storage_file_not_found(self):
        storage = GitStorage(self.workspace)
        self.assertRaises(PathNotFoundError, storage.file, 'failepicfail')
        self.assertRaises(PathNotFoundError, storage.file, 'nested')
        self.assertRaises(PathNotFoundError, storage.file, 'nested/deep')
        self.assertRaises(PathNotFoundError, storage.file, 'nested/deep/dir')
        storage.checkout(self.revs[0])
        self.assertRaises(PathNotFoundError, storage.file, self.nested_name)
        self.assertRaises(PathNotFoundError, storage.file, 'file3')

    def test_400_fileinfo(self):
        storage = GitStorage(self.workspace)
        storage.checkout(self.revs[0])
        result = storage.fileinfo('file1')
        answer = {
            'author': 'user1 <1@example.com>',
            # standalone files has no permission value in hgweb
            # 'permissions': '-rw-r--r--',
            'permissions': '',
            'desc': 'added1',
            'node': self.revs[0],
            'date': result['date'],  # manual checking
            'size': len(self.files[0]),
            'basename': 'file1',
            'file': 'file1',
            'mimetype': result['mimetype'],
            'contents': result['contents'],
            'baseview': 'file',
            'fullpath': None,
            'contenttype': None,
            'external': None,
        }

        # TODO validate the real formatted datetime.
        self.assertEqual(answer, result)

    def test_500_listdir_root(self):
        storage = GitStorage(self.workspace)
        storage.checkout(self.revs[3])
        result = list(storage.listdir(''))
        answer = [
        {
            'author': '',
            'permissions': 'drwxr-xr-x',
            'desc': '',
            'node': self.revs[3],
            'date': result[0]['date'],
            'size': '',
            'basename': 'nested',
            'file': 'nested',
            'mimetype': result[0]['mimetype'],
            'contents': result[0]['contents'],
            'baseview': 'file',
            'fullpath': None,
            'contenttype': 'folder',
            'external': None,
        },
        {
            'author': '',
            'permissions': '-rw-r--r--',
            'desc': 'added4',
            'node': self.revs[3],
            'date': result[1]['date'],
            'size': str(len(self.files[1])),
            'basename': 'file1',
            'file': 'file1',
            'mimetype': result[1]['mimetype'],
            'contents': result[1]['contents'],
            'baseview': 'file',
            'fullpath': None,
            'contenttype': 'file',
            'external': None,
        },
        {
            'author': '',
            'permissions': '-rw-r--r--',
            'desc': 'added4',
            'node': self.revs[3],
            'date': result[2]['date'],
            'size': str(len(self.files[1])),
            'basename': 'file2',
            'file': 'file2',
            'mimetype': result[2]['mimetype'],
            'contents': result[2]['contents'],
            'baseview': 'file',
            'fullpath': None,
            'contenttype': 'file',
            'external': None,
        },
        {
            'author': '',
            'permissions': '-rw-r--r--',
            'desc': 'added4',
            'node': self.revs[3],
            'date': result[3]['date'],
            'size': str(len(self.files[0])),
            'basename': 'file3',
            'file': 'file3',
            'mimetype': result[3]['mimetype'],
            'contents': result[3]['contents'],
            'baseview': 'file',
            'fullpath': None,
            'contenttype': 'file',
            'external': None,
        },
        ]
        self.assertEqual(answer, result)

    def test_501_listdir_root(self):
        storage = GitStorage(self.workspace)
        storage.checkout(self.revs[3])
        result = list(storage.listdir('nested'))
        answer = [
        {
            'author': '',
            'permissions': 'drwxr-xr-x',
            'desc': '',
            'node': self.revs[3],
            'date': result[0]['date'],
            'size': '',
            'basename': '..',
            'file': 'nested/..',
            'mimetype': result[0]['mimetype'],
            'contents': result[0]['contents'],
            'baseview': 'file',
            'fullpath': None,
            'contenttype': None,
            'external': None,
        },
        {
            'author': '',
            'permissions': 'drwxr-xr-x',
            'desc': '',
            'node': self.revs[3],
            'date': result[1]['date'],
            'size': '',
            'basename': 'deep',
            'file': 'nested/deep',
            'mimetype': result[1]['mimetype'],
            'contents': result[1]['contents'],
            'baseview': 'file',
            'fullpath': None,
            'contenttype': 'folder',
            'external': None,
        },
        ]
        self.assertEqual(answer, result)

    def test_502_listdir_nested_deep(self):
        storage = GitStorage(self.workspace)
        storage.checkout(self.revs[3])
        result = list(storage.listdir('nested/deep/dir'))
        answer = [
        {
            'author': '',
            'permissions': 'drwxr-xr-x',
            'desc': '',
            'node': self.revs[3],
            'date': result[0]['date'],
            'size': '',
            'basename': '..',
            'file': 'nested/deep/dir/..',
            'mimetype': result[0]['mimetype'],
            'contents': result[0]['contents'],
            'baseview': 'file',
            'fullpath': None,
            'contenttype': None,
            'external': None,
        },
        {
            'author': '',
            'permissions': '-rw-r--r--',
            'desc': 'added4',
            'node': self.revs[3],
            'date': result[1]['date'],
            'size': str(len(self.nested_file)),
            'basename': 'file',
            'file': 'nested/deep/dir/file',
            'mimetype': result[1]['mimetype'],
            'contents': result[1]['contents'],
            'baseview': 'file',
            'fullpath': None,
            'contenttype': 'file',
            'external': None,
        },
        ]
        self.assertEqual(answer, result)

    def test_503_listdir_old_rev(self):
        storage = GitStorage(self.workspace)
        storage.checkout(self.revs[1])
        result = list(storage.listdir(''))
        answer = [
        {
            'author': '',
            'permissions': '-rw-r--r--',
            'desc': 'added2',
            'node': self.revs[1],
            'date': result[0]['date'],
            'size': str(len(self.files[1])),
            'basename': 'file1',
            'file': 'file1',
            'mimetype': result[0]['mimetype'],
            'contents': result[0]['contents'],
            'baseview': 'file',
            'fullpath': None,
            'contenttype': 'file',
            'external': None,
        },
        {
            'author': '',
            'permissions': '-rw-r--r--',
            'desc': 'added2',
            'node': self.revs[1],
            'date': result[1]['date'],
            'size': str(len(self.files[0])),
            'basename': 'file2',
            'file': 'file2',
            'mimetype': result[1]['mimetype'],
            'contents': result[1]['contents'],
            'baseview': 'file',
            'fullpath': None,
            'contenttype': 'file',
            'external': None,
        },
        ]
        self.assertEqual(answer, result)

    def test_510_listdir_onfile_fail(self):
        storage = GitStorage(self.workspace)
        storage.checkout(self.revs[0])
        self.assertRaises(PathNotDirError, storage.listdir, 'file1')
        self.assertRaises(PathNotDirError, storage.listdir, 'file2')
        storage.checkout(self.revs[3])
        self.assertRaises(PathNotDirError, storage.listdir, 'file3')
        self.assertRaises(PathNotDirError, storage.listdir, self.nested_name)

    def test_511_listdir_on_invalid_path(self):
        storage = GitStorage(self.workspace)
        storage.checkout(self.revs[0])
        self.assertRaises(PathNotFoundError, storage.listdir, 'file3')
        self.assertRaises(PathNotFoundError, storage.listdir, 'file11')
        storage.checkout(self.revs[3])
        self.assertRaises(PathNotFoundError, storage.listdir,
                          self.nested_name + 'asdf')
        self.assertRaises(PathNotFoundError, storage.listdir, 'nested/not')

    def test_600_pathinfo(self):
        storage = GitStorage(self.workspace)
        storage.checkout(self.revs[0])
        result = storage.pathinfo('file1')
        answer = {
            'author': 'user1 <1@example.com>',
            'permissions': '',
            'desc': 'added1',
            'node': self.revs[0],
            'date': result['date'],
            'size': len(self.files[0]),
            'basename': 'file1',
            'file': 'file1',
            'mimetype': result['mimetype'],
            'contents': result['contents'],
            'baseview': 'file',
            'fullpath': None,
            'contenttype': None,
            'external': None,
        }
        self.assertEqual(answer, result)
        # TODO
        #self.assertTrue(result['mimetype']().startswith('text/plain'))

    def test_601_pathinfo_nested_dir(self):
        storage = GitStorage(self.workspace)
        storage.checkout(self.revs[3])
        result = storage.pathinfo('nested/deep/dir')
        answer = {
            'author': '',
            'permissions': 'drwxr-xr-x',
            'desc': '',
            'node': self.revs[3],
            'date': '',
            'size': '',
            'basename': 'dir',
            'file': 'nested/deep/dir',
            'mimetype': result['mimetype'],
            'contents': result['contents'],
            'baseview': 'file',
            'fullpath': None,
            'contenttype': None,
            'external': None,
        }
        self.assertEqual(answer, result)

    def test_602_pathinfo_nested_dir(self):
        storage = GitStorage(self.workspace)
        storage.checkout(self.revs[3])
        result = storage.pathinfo(self.nested_name)
        answer = {
            'author': 'user3 <3@example.com>',
            'permissions': '',
            'desc': 'added4',
            'node': self.revs[3],
            'date': result['date'],
            'size': len(self.nested_file),
            'basename': 'file',
            'file': self.nested_name,
            'mimetype': result['mimetype'],
            'contents': result['contents'],
            'baseview': 'file',
            'fullpath': None,
            'contenttype': None,
            'external': None,
        }
        self.assertEqual(answer, result)

    def test_650_pathinfo_external(self):
        storage = GitStorage(self.repodata)
        storage.checkout(util.ARCHIVE_REVS[1])
        result = storage.pathinfo('ext/import1/')
        answer = {
            'author': '',
            'permissions': 'lrwxrwxrwx',
            'desc': '',
            'node': util.ARCHIVE_REVS[1],
            'date': result['date'],
            'size': '',
            'basename': '',
            'file': 'ext/import1/',
            'mimetype': result['mimetype'],
            'contents': result['contents'],
            'baseview': 'file',
            'fullpath': None,
            'contenttype': None,
            'external': {
                '': '_subrepo',
                'location': 'http://models.example.com/w/import1',
                'path': '',
                'rev': 'ce679be0c07e30e81f93cc308ccdaab97b4da313',
            },
        }
        self.assertEqual(answer, result)

    def test_651_pathinfo_external(self):
        storage = GitStorage(self.repodata)
        storage.checkout(util.ARCHIVE_REVS[1])
        result = storage.pathinfo('ext/import1/if1')
        answer = {
            'author': '',
            'permissions': 'lrwxrwxrwx',
            'desc': '',
            'node': util.ARCHIVE_REVS[1],
            'date': result['date'],
            'size': '',
            'basename': 'if1',
            'file': 'ext/import1/if1',
            'mimetype': result['mimetype'],
            'contents': result['contents'],
            'baseview': 'file',
            'fullpath': None,
            'contenttype': None,
            'external': {
                '': '_subrepo',
                'location': 'http://models.example.com/w/import1',
                'path': 'if1',
                'rev': 'ce679be0c07e30e81f93cc308ccdaab97b4da313',
            },
        }
        self.assertEqual(answer, result)

    def test_652_pathinfo_external(self):
        storage = GitStorage(self.repodata)
        storage.checkout(util.ARCHIVE_REVS[1])
        # does not exist yet
        result = storage.pathinfo('ext/import2/if2')
        self.assertRaises(PathNotFoundError, storage.pathinfo, 
            'ext/import2/if2')

    def test_661_pathinfo_external_newerrev(self):
        storage = GitStorage(self.repodata)
        storage.checkout(util.ARCHIVE_REVS[4])
        result = storage.pathinfo('ext/import1/if1')
        answer = {
            'author': '',
            'permissions': 'lrwxrwxrwx',
            'desc': '',
            'node': util.ARCHIVE_REVS[4],
            'date': result['date'],
            'size': '',
            'basename': 'if1',
            'file': 'ext/import1/if1',
            'mimetype': result['mimetype'],
            'contents': result['contents'],
            'baseview': 'file',
            'fullpath': None,
            'contenttype': None,
            'external': {
                '': '_subrepo',
                'location': 'http://models.example.com/w/import1',
                'path': 'if1',
                'rev': '4df76eccfee8a0d27844b5c069bc399bb0e4e043',
            },
        }
        self.assertEqual(answer, result)

    def test_652_pathinfo_external(self):
        storage = GitStorage(self.repodata)
        storage.checkout(util.ARCHIVE_REVS[4])
        result = storage.pathinfo('ext/import2/if2')
        answer = {
            'author': '',
            'permissions': 'lrwxrwxrwx',
            'desc': '',
            'node': util.ARCHIVE_REVS[4],
            'date': result['date'],
            'size': '',
            'basename': 'if2',
            'file': 'ext/import2/if2',
            'mimetype': result['mimetype'],
            'contents': result['contents'],
            'baseview': 'file',
            'fullpath': None,
            'contenttype': None,
            'external': {
                '': '_subrepo',
                'location': 'http://models.example.com/w/import2',
                'path': 'if2',
                'rev': 'a413e4d7eb3846209aa8df44addf625093aac231',
            },
        }
        self.assertEqual(answer, result)

    def test_700_archiveFormats(self):
        storage = GitStorage(self.workspace)
        formats = storage.archiveFormats
        self.assertEqual(formats, ['tgz', 'zip',])

    def test_710_archiveInfo(self):
        storage = GitStorage(self.workspace)
        info = storage.archiveInfo('tgz')
        self.assertEqual(info, {
            'name': 'Tarball (gzipped)',
            'ext': '.tar.gz',
            'mimetype': 'application/x-tar',
        })
        info = storage.archiveInfo('zip')
        self.assertEqual(info, {
            'name': 'Zip File',
            'ext': '.zip',
            'mimetype': 'application/zip',
        })

    def test_720_archive_zip(self):
        storage = GitStorage(self.workspace)

        storage.checkout(self.revs[3])
        rev = self.revs[3][:12]
        root = '%s-%s' % (self.workspace.id, rev)
        names = ['file1', 'file2', 'file3', 'nested/deep/dir/file']
        contents = [self.files[1], self.files[1], self.files[0],
                    self.nested_file,]
        answer = zip(['%s/%s' % (root, n) for n in names], contents)

        archive = storage.archive('zip')
        stream = StringIO(archive)
        zfile = zipfile.ZipFile(stream, 'r')
        result = [i.filename for i in zfile.infolist()]

        for a, c in answer:
            self.assert_(a in result)
            self.assertEqual(zfile.read(a), c)

    def test_721_archive_zip(self):
        storage = GitStorage(self.workspace)

        storage.checkout(self.revs[0])
        rev = self.revs[0][:12]
        root = '%s-%s' % (self.workspace.id, rev)
        names = ['file1', 'file2']
        contents = [self.files[0], self.files[0],]
        answer = zip(['%s/%s' % (root, n) for n in names], contents)

        archive = storage.archive('zip')
        stream = StringIO(archive)
        zfile = zipfile.ZipFile(stream, 'r')
        result = [i.filename for i in zfile.infolist()]

        for a, c in answer:
            self.assert_(a in result)
            self.assertEqual(zfile.read(a), c)

    def test_730_archive_tgz(self):
        storage = GitStorage(self.workspace)

        storage.checkout(self.revs[3])
        rev = self.revs[3][:12]
        root = '%s-%s' % (self.workspace.id, rev)
        names = ['file1', 'file2', 'file3', 'nested/deep/dir/file']
        contents = [self.files[1], self.files[1], self.files[0],
                    self.nested_file,]
        answer = zip(['%s/%s' % (root, n) for n in names], contents)

        archive = storage.archive('tgz')
        stream = StringIO(archive)
        tfile = tarfile.open('test', 'r:gz', stream)
        result = [i.name for i in tfile.getmembers()]

        for a, c in answer:
            self.assert_(a in result)
            self.assertEqual(tfile.extractfile(a).read(), c)

    def test_731_archive_tgz(self):
        storage = GitStorage(self.workspace)

        storage.checkout(self.revs[0])
        rev = self.revs[0][:12]
        root = '%s-%s' % (self.workspace.id, rev)
        names = ['file1', 'file2']
        contents = [self.files[0], self.files[0],]
        answer = zip(['%s/%s' % (root, n) for n in names], contents)

        archive = storage.archive('tgz')
        stream = StringIO(archive)
        tfile = tarfile.open('test', 'r:gz', stream)
        result = [i.name for i in tfile.getmembers()]

        for a, c in answer:
            self.assert_(a in result)
            self.assertEqual(tfile.extractfile(a).read(), c)


class UtilityTestCase(TestCase):

    def setUp(self):
        super(UtilityTestCase, self).setUp()
        self.filelist1 = ['README', 'test1', 'test2', 'test3',]

    def test_0001_utility_base(self):
        utility = GitStorageUtility()
        storage = utility(self.workspace)
        self.assert_(isinstance(storage, GitStorage))
        self.assert_(IStorage.providedBy(storage))

    def test_0100_sync(self):
        utility = GitStorageUtility()
        simple1 = utility(self.simple1)
        filelist = simple1.files()
        # verify file list for simple1
        self.assertEqual(filelist, self.filelist1)
        target = join(self.testdir, 'simple1')

        # sync simple2 with simple1
        utility.sync(self.simple2, target)
        simple2 = utility(self.simple2)
        simple2.checkout()
        filelist = simple2.files()
        self.assertEqual(filelist, self.filelist1)

    def test_0101_sync_same_root_conflict_filenames(self):
        utility = GitStorageUtility()
        target = join(self.testdir, 'simple1')
        # sync simple3 with simple1
        utility.sync(self.simple3, target)
        simple3 = utility(self.simple3)
        simple3.checkout()
        filelist = simple3.files()
        self.assertEqual(filelist, self.filelist1)

        # should be a better way to show this.
        self.assertEqual(len(simple3.storage._repo.heads()), 2)

    def test_0110_sync_mismatch_root(self):
        utility = GitStorageUtility()
        target = self.repodir
        # just trap the most basic form
        self.assertRaises(Exception, utility.sync, self.simple3, target)
        # will need to update this once this exception is dealt with


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(StorageTestCase))
    suite.addTest(makeSuite(UtilityTestCase))
    return suite

if __name__ == '__main__':
    unittest.main()
