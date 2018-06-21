#!/usr/bin/env python

import os
import sys

from setuptools import setup


if sys.argv[-1] == 'publish':
    os.system('python setup.py register sdist bdist_wheel upload')
    sys.exit()


setup(
    name='iap',
    version='2.0.3',
    description='Python utilities for working with Apple In-App Purchases (IAP)',
    license="MIT",
    keywords="iap appstore django",
    author='Educreations Engineering',
    author_email='engineering@educreations.com',
    url='https://github.com/educreations/python-iap',
    packages=["iap"],
    package_dir={"iap": "iap"},
    install_requires=['pycrypto', 'Django>=1.7', 'requests'],
)
