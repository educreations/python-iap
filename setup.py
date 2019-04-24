#!/usr/bin/env python

import os
import sys

from setuptools import setup


if sys.argv[-1] == 'publish':
    os.system('python setup.py register sdist bdist_wheel upload')
    sys.exit()


setup(
    name='iap',
    version='2.2.1',
    description='Python utilities for working with Apple In-App Purchases (IAP)',
    license="MIT",
    keywords="iap appstore django",
    author='Educreations Engineering',
    author_email='engineering@educreations.com',
    url='https://github.com/educreations/python-iap',
    packages=["iap"],
    package_dir={"iap": "iap"},
    install_requires=[
        'Django>=1.7',
        'pyopenssl>=17.0.0',
        'pyasn1',
        'pyasn1_modules',
        'requests',
    ],
    tests_require=[
        'pytest',
        'pytest-django',
    ],
)
