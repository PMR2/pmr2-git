This test needs to be done separately as proper cleanup of the spawned
ZServer is not done, which will interfere with all normal tests.

This can be avoided if we can override git.url and splice the
testbrowser opener director into that place (or into the httprepo that
this testcase instantiates).

Synchronization
---------------

A more comprehensive test can be done.  We are going to make use of the
testbrowser Browser for this test.  First log-in::

    >>> import zope.component
    >>> from pmr2.app.workspace.interfaces import *
    >>> from Testing.testbrowser import Browser
    >>> from Products.PloneTestCase.setup import portal_owner, default_password
    >>> browser = Browser()
    >>> portal_url = self.portal.absolute_url()
    >>> browser.open(portal_url + '/login')
    >>> browser.getControl(name='__ac_name').value = portal_owner
    >>> browser.getControl(name='__ac_password').value = default_password
    >>> browser.getControl(name='submit').click()

Initialize and verify some values::

    >>> simple1 = self.portal.workspace.simple1
    >>> simple2 = self.portal.workspace.simple2
    >>> simple1_url = simple1.absolute_url()
    >>> simple2_url = simple2.absolute_url()
    >>> simple1_storage = zope.component.getAdapter(simple1, IStorage)
    >>> simple2_storage = zope.component.getAdapter(simple2, IStorage)
    >>> simple1_files = simple1_storage.files()
    >>> simple2_files = simple2_storage.files()
    >>> simple1_files
    ['README', 'test1', 'test2', 'test3']
    >>> simple2_files
    ['test1', 'test2', 'test3']

Publish the target also::

    >>> from Products.CMFCore.utils import getToolByName
    >>> self.setRoles(('Manager',))
    >>> wft = getToolByName(self.portal, 'portal_workflow')
    >>> wft.doActionFor(simple1, 'publish')

As Git expects a real IP address, we need a real server to test
this.  Start one up::

    >>> from Testing.ZopeTestCase.utils import startZServer
    >>> server = startZServer()

Now construct URL and sync with the target::

    >>> target_url = 'http://%s:%s/plone/workspace/simple1' % server
    >>> browser.open(simple2_url + '/sync')
    >>> browser.getControl(name='form.widgets.external_uri').value = target_url
    >>> browser.getControl(name='form.buttons.syncWithTarget').click()

Should have been redirected back to main page::

    >>> browser.url
    '.../plone/workspace/simple2'
    >>> 'README' in browser.contents
    True

Verify that the file list is updated::

    >>> simple2_storage = zope.component.getAdapter(simple2, IStorage)
    >>> simple2_files = simple2_storage.files()
    >>> simple2_files
    ['README', 'test1', 'test2', 'test3']

However, if we were to use an valid protocol (such as file), an error
will be generated instead::

    >>> target_url = 'file://' + self.pmr2.dirOf(simple1)
    >>> browser.open(simple2_url + '/sync')
    >>> browser.getControl(name='form.widgets.external_uri').value = target_url
    >>> browser.getControl(name='form.buttons.syncWithTarget').click()
    >>> 'is using a forbiddened protocol.' in browser.contents
    True

    >>> target_url = self.pmr2.dirOf(simple1)
    >>> browser.open(simple2_url + '/sync')
    >>> browser.getControl(name='form.widgets.external_uri').value = target_url
    >>> browser.getControl(name='form.buttons.syncWithTarget').click()
    >>> 'is using a forbiddened protocol.' in browser.contents
    True

Ditto with using a path directly::

    >>> browser.open(simple2_url + '/sync')
    >>> browser.getControl(name='form.widgets.external_uri').value = target_url
    >>> browser.getControl(name='form.buttons.syncWithTarget').click()
    >>> 'is using a forbiddened protocol.' in browser.contents
    True

Shutdown the test server::

    >>> import threading
    >>> from Testing.ZopeTestCase.threadutils import QuietThread
    >>> for t in threading.enumerate():
    ...     if isinstance(t, QuietThread):
    ...         t._Thread__stop()
    >>> import pdb;pdb.set_trace()
