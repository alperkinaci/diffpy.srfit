#!/usr/bin/env python

# Installation script for diffpy.Structure

"""diffpy.srfit - prototype for new PDF calculator and assortment
of real space utilities.

Packages:   diffpy.srfit
Scripts:    (none yet)
"""

from setuptools import setup, find_packages
import fix_setuptools_chmod


# define distribution
dist = setup(
        name = "diffpy.srfit",
        version = "1.0a9",
        namespace_packages = ['diffpy'],
        packages = find_packages(exclude=['tests']),
        test_suite = 'tests',
        entry_points = {},
        install_requires = [
            # FIXME - need version greater than 6162.
            'diffpy.Structure>=1.0-r5333-20100518',
            'pyobjcryst>=1.0b1.dev-r5681-20100816',
            # FIXME - need version greater than 6162.
            'diffpy.srreal>=0.2a1.dev-r6037-20101130',
            'numpy>=1.0',
            'scipy>=0.7.0',
            ],
        dependency_links = [
            # REMOVE dev.danse.us for a public release.
            'http://dev.danse.us/packages/',
            "http://www.diffpy.org/packages/",
        ],

        author = "Simon J.L. Billinge",
        author_email = "sb2896@columbia.edu",
        maintainer = 'Christopher L. Farrow',
        maintainer_email = 'clf2121@columbia.edu',
        description = "SrFit - Structure refinement from diffraction data",
        license = "BSD",
        url = "http://www.diffpy.org/",
        keywords = "complex modeling calculator utilities",
        classifiers = [
            # List of possible values at
            # http://pypi.python.org/pypi?:action=list_classifiers
            'Development Status :: 4 - Beta',
            'Environment :: Console',
            'Intended Audience :: Science/Research',
            'Operating System :: MacOS',
            'Operating System :: Microsoft :: Windows',
            'Operating System :: POSIX',
            'Programming Language :: Python :: 2.6',
            'Topic :: Scientific/Engineering :: Physics',
        ],
)

# End of file
