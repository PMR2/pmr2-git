import gzip
import re
from cStringIO import StringIO
from subprocess import Popen, PIPE

from AccessControl import Unauthorized
from zExceptions import Forbidden, BadRequest
from Products.CMFCore.utils import getToolByName
from zope.publisher.interfaces import NotFound
from plone.protect.interfaces import IDisableCSRFProtection
from zope.interface import alsoProvides
from zope.event import notify

from dulwich.server import Backend, DEFAULT_HANDLERS
from dulwich.repo import Repo
from dulwich.web import get_text_file, get_info_refs, get_loose_object
from dulwich.web import get_pack_file, get_idx_file, handle_service_request
from dulwich.web import get_info_packs
from dulwich.web import HTTPGitRequest
from dulwich.web import HTTP_OK, HTTP_NOT_FOUND, HTTP_FORBIDDEN, HTTP_ERROR

from pmr2.z3cform.page import TraversePage
from pmr2.app.settings.interfaces import IPMR2GlobalSettings
from pmr2.app.workspace.event import Push

from pmr2.git.utility import GitStorage

push_patt = re.compile('/git-receive-pack$')
push_warning = """
Please push a branch named either "master" or "main", otherwise the
workspace may appear to be missing your files.

To correct, please first checkout your desired branch to push and
rename it to `main` before pushing it by running:

    git branch -m main

"""


class ZopeHTTPGitRequest(HTTPGitRequest):
    """
    Override the methods to make it compatible with Zope.
    """

    status = None

    def respond(self, status=HTTP_OK, content_type=None, headers=None):
        """Begin a response with the given status and other headers."""
        if headers:
            self._headers.extend(headers)
        if content_type:
            self._headers.append(('Content-Type', content_type))
        self._headers.extend(self._cache_headers)

        # store the status code for later handling
        self.status = status
        self.out = StringIO()

        return self.out.write


class DulwichBackend(Backend):

    def __init__(self, path):
        self.repo = Repo(path)

    def open_repository(self, path):
        return self.repo


class GitProtocol(TraversePage):

    services = {
        ('GET', re.compile('/HEAD$')): get_text_file,
        ('GET', re.compile('/info/refs$')): get_info_refs,
        ('GET', re.compile('/objects/info/alternates$')): get_text_file,
        ('GET', re.compile('/objects/info/http-alternates$')): get_text_file,
        ('GET', re.compile('/objects/info/packs$')): get_info_packs,
        ('GET', re.compile('/objects/([0-9a-f]{2})/([0-9a-f]{38})$')):
            get_loose_object,
        ('GET', re.compile('/objects/pack/pack-([0-9a-f]{40})\\.pack$')):
            get_pack_file,
        ('GET', re.compile('/objects/pack/pack-([0-9a-f]{40})\\.idx$')):
            get_idx_file,

        ('POST', re.compile('/git-upload-pack$')): handle_service_request,
        ('POST', push_patt): handle_service_request,
    }

    def update(self):

        self.storage = GitStorage(self.context)
        backend = DulwichBackend(self.storage.repo.path)

        # The name of the view will be captured - combine that with the
        # subpath to get the original path.
        self.pathinfo = '/' + self.__name__
        if self.url_subpath:
            self.pathinfo += '/' + self.url_subpath

        if (self.pathinfo == '/info/refs' and
                'service=git-receive-pack' in self.request['QUERY_STRING']):
            # Since the basic auth doesn't get triggered for the POST
            # request (for obvious reasons because the entire upload blob
            # will have to be done again, we ban all anon here.
            pm = getToolByName(self.context, 'portal_membership')
            user = pm.getAuthenticatedMember()
            if pm.isAnonymousUser():
                raise Unauthorized()

        self.request.stdin.seek(0)
        if self.request.get('HTTP_CONTENT_ENCODING') == 'gzip':
            stdin = gzip.GzipFile(filename=None, fileobj=self.request.stdin,
                mode='r')
        else:
            stdin = self.request.stdin

        self.env = {
            #'GIT_HTTP_EXPORT_ALL': '1',
            'REQUEST_METHOD': self.request.method, 
            #'GIT_PROJECT_ROOT': self.storage.repo.path,
            'PATH_INFO': self.pathinfo,
            'CONTENT_TYPE': self.request['CONTENT_TYPE'],
            'QUERY_STRING': self.request['QUERY_STRING'],
            'wsgi.input': stdin,
        }

        req = ZopeHTTPGitRequest(self.env, None, dumb=False,
            handlers=dict(DEFAULT_HANDLERS))

        for smethod, spath in self.services.iterkeys():
            if smethod != self.request.method:
                continue
            match = spath.search(self.pathinfo)
            if match:
                handler = self.services[smethod, spath]
                break

        if handler is None:
            raise NotFound(self.context, self.pathinfo)

        if self.request.method == 'POST' and spath is push_patt:
            alsoProvides(self.request, IDisableCSRFProtection)
            notify(Push(self.context))
            self.is_push = True
        else:
            self.is_push = False

        self.handler = handler(req, backend, match)
        self.gitreq = req

    def render(self):
        # trigger the handler
        frags = [f for f in self.handler]

        # check if error status is set for gitreq obj.
        if self.gitreq.status == HTTP_NOT_FOUND:
            raise NotFound(self.context, self.pathinfo)
        elif self.gitreq.status == HTTP_FORBIDDEN:
            raise Forbidden('forbidden')
        elif self.gitreq.status == HTTP_FORBIDDEN:
            raise BadRequest('bad request')

        # acquire the response headers and body from the gitreq obj.
        for header in self.gitreq._headers:
            self.request.response.setHeader(*header)
        result = self.gitreq.out.getvalue()

        if self.is_push:
            try:
                self.storage.repo.revparse_single('HEAD')
            except KeyError:
                # attempt to set reference to main instead
                try:
                    self.storage.repo.revparse_single('main')
                except KeyError:
                    # trigger warning
                    result = '%04X\x02%s%s' % (
                        len(push_warning) + 5, push_warning, result)
                else:
                    self.storage.repo.head = 'refs/heads/main'

        return result

    def __call__(self):
        self.update()
        return self.render()
