import zope.schema
import zope.interface

from pmr2.app.workspace.interfaces import IWorkspace


class IAppLayer(zope.interface.Interface):
    """
    Marker interface for this product.
    """


class IPMR2GitWorkspaceAdapter(zope.interface.Interface):
    """
    Adapter class between a PMR2 content class and pmr2.git Workspace
    object.
    """

    # XXX missing fields (such as rev)
    # XXX missing methods


class IGitWorkspace(IWorkspace):
    """
    Special marker for git workspaces to enable the git protocol views.
    """
