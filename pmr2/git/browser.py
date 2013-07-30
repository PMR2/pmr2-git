from cStringIO import StringIO
from subprocess import Popen, PIPE

from AccessControl import Unauthorized
from Products.CMFCore.utils import getToolByName

from pmr2.z3cform.page import TraversePage
from pmr2.git.utility import GitStorage


"""
These are the defined git-http-backend service end points:

    {"GET", "/HEAD$", get_head},
    {"GET", "/info/refs$", get_info_refs},
    {"GET", "/objects/info/alternates$", get_text_file},
    {"GET", "/objects/info/http-alternates$", get_text_file},
    {"GET", "/objects/info/packs$", get_info_packs},
    {"GET", "/objects/[0-9a-f]{2}/[0-9a-f]{38}$", get_loose_object},
    {"GET", "/objects/pack/pack-[0-9a-f]{40}\\.pack$", get_pack_file},
    {"GET", "/objects/pack/pack-[0-9a-f]{40}\\.idx$", get_idx_file},

    {"POST", "/git-upload-pack$", service_rpc},
    {"POST", "/git-receive-pack$", service_rpc}
"""


class GitProtocol(TraversePage):

    # XXX make this configurable
    backend_bin = '/usr/lib/git-core/git-http-backend'

    def update(self):

        self.storage = GitStorage(self.context)

        pathinfo = '/' + self.__name__
        if self.url_subpath:
            pathinfo += '/' + self.url_subpath

        if (pathinfo == '/info/refs' and
                'service=git-receive-pack' in self.request['QUERY_STRING']):
            # Since the basic auth doesn't get triggered for the POST
            # request (for obvious reasons because the entire upload blob
            # will have to be done again, we ban all anon here.
            pm = getToolByName(self.context, 'portal_membership')
            user = pm.getAuthenticatedMember()
            if pm.isAnonymousUser():
                raise Unauthorized()

        self.env = {
            'GIT_HTTP_EXPORT_ALL': '1',
            'REQUEST_METHOD': self.request.method, 
            'GIT_PROJECT_ROOT': self.storage.repo.path,
            'PATH_INFO': pathinfo,
            'CONTENT_TYPE': self.request['CONTENT_TYPE'],
            'QUERY_STRING': self.request['QUERY_STRING'],
        }

    def render(self):
        raw = self.backend()
        while 1:
            line = raw.readline().strip()
            if line == '':
                break
            self.request.response.setHeader(*line.split(': ', 1))
        result = raw.read()
        return result

    def backend(self):
        self.request.stdin.seek(0)
        p = Popen(stdin=PIPE, stdout=PIPE, stderr=PIPE,
            env=self.env, *([self.backend_bin]))
        output, err = p.communicate(self.request.stdin.read())
        if err:
            raise Exception(err)  # XXX placeholder.
        return StringIO(output)

    def __call__(self):
        self.update()
        return self.render()
