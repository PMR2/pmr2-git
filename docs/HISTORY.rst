Changelog
=========

0.7.1 - 2022-06-10
------------------

* Ensure empty repos will produce no roots rather than error out.

0.7.0 - 2022-05-18
------------------

* Ensure when trying to access subpaths of a blob raise the correct
  exception
* Provide a git icon for submodules.

0.6.0 - 2021-11-04
------------------

* Partially mitigate the dangling opened file issue with the usage
  through the vocabulary factory by using dulwich to get the list of
  files.
* Support the default main branch on main listing as an alternative, as
  master branch is being deprecated.

0.5.0 - 2021-09-14
------------------

* Support for custom clone command, for git repos with submodules.

0.4.0 - 2021-07-01
------------------

* Support the roots API call.
* Ensure the Push events are fired.

0.3.1 - 2017-01-10
------------------

* Minor correction to testing to be compatible with some upstream fixes.

0.3 - 2016-03-08
----------------

* Correction to the mimetype reporting to use the path where it's done,
  and also use the magic module to achieve the guessing when that is not
  available.
* Other minor changes to match with pmr2.app.

0.2 - 2015-03-19
----------------

* Ensure that ``RevisionNotFound`` is raised for attempts to checkout a
  revision that is not found and is not ``HEAD``.

0.1 - 2014-04-03
----------------

* Initial release of the git backend for PMR.

