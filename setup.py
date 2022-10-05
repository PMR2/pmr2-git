from setuptools import setup, find_packages
import os

version = '0.7.2'

setup(name='pmr2.git',
      version=version,
      description="Git plugin for PMR",
      long_description=open("README.rst").read() + "\n" +
                       open(os.path.join("docs", "HISTORY.rst")).read(),
      # Get more strings from http://www.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
        ],
      keywords='',
      author='Tommy Yu',
      author_email='tommy.yu@auckland.ac.nz',
      url='https://github.com/PMR/pmr2.git',
      license='GPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['pmr2'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          # -*- Extra requirements: -*-
          'pygit2',
          'dulwich>=0.11.0',
          'python-magic>=0.4.9',
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
