Changelog
=========

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

