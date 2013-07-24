Introduction
============

``pmr2.git`` provides a Git based storage backend for the Physiome Model
Repository (PMR), and is intended to be used in conjunction with the
`PMR Software Suite`_.

.. _PMR software suite: https://github.com/PMR/pmr2.buildout/

Currently, this package is under development and is included in the
development version of the ``pmr2.buildout`` package, as specified in
the ``buildout.cfg`` within there.

Installation
------------

While not recommended, you may manually install this package onto any
Zope/Plone installation by modifying the ``buildout.cfg`` to include
this package at the relevant locations, for example::

    [buildout]
    ...

    [instance]
    ...

    eggs =
        ...
        pmr2.git

    zcml =
        ...
        pmr2.git

Also, the find-links attribute need to include the download location
of the tarball for this package.

Usage
-----

For further usage information, please refer to the tests and the
associated text files within.
