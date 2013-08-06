Workspace browser interaction with Git Backend
==============================================

This module is the Git backend for PMR Workspaces.

Setup
-----

Before we get started, we need to import the required classes::

    >>> import zope.component
    >>> from pmr2.app.workspace.browser import browser
    >>> from pmr2.testing.base import TestRequest
    >>> from plone.z3cform.tests import setup_defaults
    >>> from pmr2.app.workspace.interfaces import *
    >>> from pmr2.app.workspace.content import *

Adding Git based workspace
--------------------------

Once Git is installed, it should have been registered as one of the
available backends that can be added inside the workspace creation form.
This can be checked as so::

    >>> request = TestRequest()
    >>> form = browser.WorkspaceStorageCreateForm(
    ...     self.portal.workspace, request)
    >>> result = form()
    >>> 'git' in result
    True

Now the data can be filled out and submitted::

    >>> request = TestRequest(form={
    ...     'form.widgets.id': u'foobarbaz',
    ...     'form.widgets.title': u'Foo Bar Baz',
    ...     'form.widgets.description': u'Foo Bar Baz',
    ...     'form.widgets.storage': [u'git'],
    ...     'form.buttons.add': 1,
    ... })
    >>> form = browser.WorkspaceStorageCreateForm(
    ...     self.portal.workspace, request)
    >>> form.update()

The Git workspace should have been created, and it could be adapted into
a usable a GitStorage instance::

    >>> foobarbaz = self.portal.workspace.foobarbaz
    >>> foobarbaz.title
    u'Foo Bar Baz'
    >>> storage = zope.component.getAdapter(foobarbaz, IStorage)
    >>> '.git' in storage.repo.path
    True

Initial page should render::

    >>> request = TestRequest()
    >>> wkspc = self.portal.workspace.foobarbaz
    >>> testpage = browser.WorkspacePage(wkspc, request)
    >>> result = testpage()
    >>> 'Workspace Summary' in result
    True

Log page should also render::

    >>> request = TestRequest()
    >>> testpage = browser.WorkspaceShortlog(wkspc, request)
    >>> testpage.__name__ = 'log'
    >>> result = testpage()

We can test this new empty workspace later by pushing some data to it.

Rendering
---------

Now that the Git archive has been extracted, with its workspace object
created, we can now test the basic rendering of the landing page::

    >>> request = TestRequest()
    >>> wkspc = self.portal.workspace.repodata
    >>> testpage = browser.WorkspacePage(wkspc, request)
    >>> result = testpage()
    >>> 'Workspace Summary' in result
    True

Now for a file listing, without any traverse subpaths::

    >>> request = TestRequest()
    >>> testpage = browser.FilePage(wkspc, request)
    >>> testpage.update()
    >>> result = testpage()
    >>> label = u'Location: repodata @ %s /' % \
    ...     self.repodata_revs[-1][:12]
    >>> label in result
    True
    >>> 'file1' in result
    True
    >>> 'file2' in result
    True
    >>> 'README' in result
    True

Now for a file listing, just traversing down a previous revision, using
a partial revision id::

    >>> subpath = [self.repodata_revs[7][:6]]
    >>> testpage = self.traverse(wkspc, browser.FilePage, subpath)
    >>> testpage.update()
    >>> result = testpage()
    >>> label = u'Location: repodata @ %s /' % \
    ...     self.repodata_revs[7][:12]
    >>> label in result
    True
    >>> 'file1' in result
    True
    >>> 'file2' in result
    True
    >>> 'README' in result
    True
    >>> ('http://nohost/plone/workspace/repodata/file/'
    ...  'eab05fccc349fbeb57ade09a197ddc72cd9e4388/1') in result
    True
    >>> ('http://nohost/plone/workspace/repodata/file/'
    ...  'eab05fccc349fbeb57ade09a197ddc72cd9e4388/README') in result
    True
    >>> '<td>43</td>' in result
    True

Now test the listing of the container that contains import links::

    >>> subpath = [self.repodata_revs[7], 'ext']
    >>> testpage = self.traverse(wkspc, browser.FilePage, subpath)
    >>> testpage.update()
    >>> result = testpage()
    >>> label = u'Location: repodata @ %s / ext' % \
    ...     self.repodata_revs[7][:12]
    >>> 'import1' in result
    True
    >>> 'import2' in result
    True

Accessing the import links using the file page will trigger a 
redirection::

    >>> subpath = [self.repodata_revs[7], 'ext', 'import1']
    >>> testpage = self.traverse(wkspc, browser.FilePage, subpath)
    >>> testpage.update()
    'http://.../w/import1/rawfile/466b6256bd9a.../'

Try again with a different file and revision the intended redirection
should also be triggered.  As the `__name__` would have been be set
during the acquisition of the form, we will emulate this here also::

    >>> subpath = [self.repodata_revs[1], 'ext', 'import1', 'if1']
    >>> testpage = self.traverse(wkspc, browser.FilePage, subpath)
    >>> testpage.__name__ = 'file'
    >>> testpage.update()
    'http://.../w/import1/file/00cf337ef94f.../if1'

Subdirectories should work::

    >>> subpath = [self.repodata_revs[7], '1', '2']
    >>> testpage = self.traverse(wkspc, browser.FilePage, subpath)
    >>> testpage.update()
    >>> result = testpage()
    >>> label = u'Location: repodata @ eab05fccc349 / 1 / 2'
    >>> label in result
    True
    >>> '2f2' in result
    True

Bad revision results in not found::

    >>> subpath = ['abcdef1234567890', 'component']
    >>> testpage = self.traverse(wkspc, browser.FilePage, subpath)
    >>> testpage.update()
    Traceback (most recent call last):
    ...
    NotFound: ...
    ...

We also need to test the log viewer.  Shortlog viewer should have the
links to the file listing::

    >>> request = TestRequest()
    >>> testpage = browser.WorkspaceShortlog(wkspc, request)
    >>> testpage.__name__ = 'log'
    >>> testpage.update()
    >>> result = testpage()
    >>> 'http://nohost/plone/workspace/repodata/@@file/0a6808653e65' in result
    True
    >>> len([i for i in self.repodata_revs if i in result]) == len(
    ...     self.repodata_revs)
    True

Git Protocol Integration
------------------------

Unlike Mercurial, git protocol operates differently.  Currently this is
deferred to a CGI binary and subprocess.Popen is used to call that for
now.

Git Workspace Forking
---------------------

User workspace will need to be set up correctly in order for this test
to function.  Make sure one is created for the current user::

    >>> self.pmr2.createUserWorkspaceContainer('test_user_1_')

Make use of one of the workspace as the context and then activate the
fork button::

    >>> simple1 = self.portal.workspace.simple1
    >>> simple1_storage = zope.component.getAdapter(simple1, IStorage)
    >>> request = TestRequest(form={
    ...     'form.buttons.fork': 1,
    ... })
    >>> form = browser.WorkspaceForkForm(simple1, request)
    >>> form.update()

A new workspace within the user's workspace container should be
present::

    >>> cloned = self.pmr2.getCurrentUserWorkspaceContainer().get('simple1')
    >>> cloned.storage == u'git'
    True

The list of files between both of them should be equal::

    >>> cloned_storage = zope.component.getAdapter(cloned, IStorage)
    >>> cloned_storage.files() == simple1_storage.files()
    True
