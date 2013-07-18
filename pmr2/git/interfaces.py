import zope.schema
import zope.interface


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
