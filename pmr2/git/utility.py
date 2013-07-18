import re
from os.path import basename
from cStringIO import StringIO
import zope.component

from pygit2 import Repository

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
        raise NotImplementedError

    def isprotocol(self, request):
        raise NotImplementedError

    def protocol(self, context, request):
        raise NotImplementedError

    def syncIdentifier(self, context, identifier):
        raise NotImplementedError

    def syncWorkspace(self, context, source):
        raise NotImplementedError


class GitStorage(BaseStorage):

    # One of the future item is to modify this to more closely interact
    # with the mercurial library rather than go through one of our
    # previous abstractions.
    
    def __init__(self, context):
        rp = zope.component.getUtility(IPMR2GlobalSettings).dirOf(context)
        self.context = context

        raise NotImplementedError

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
        return self.__rev

    @property
    def shortrev(self):
        raise NotImplementedError

    def archive_zip(self):
        arctype = 'zip'
        raise NotImplementedError

    def archive_tgz(self):
        arctype = 'tgz'
        raise NotImplementedError

    def basename(self, name):
        raise NotImplementedError

    def checkout(self, rev=None):
        raise NotImplementedError

    # Unit tests would be useful here, even if this class will only
    # produce output for the browser classes.

    def file(self, path):
        raise NotImplementedError

    def fileinfo(self, path):
        raise NotImplementedError

    def files(self):
        raise NotImplementedError

    def listdir(self, path):
        raise NotImplementedError

    def pathinfo(self, path):
        raise NotImplementedError

    def log(self, start, count, branch=None, shortlog=False):
        raise NotImplementedError
