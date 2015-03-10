#!/usr/bin/env python

from setuptools import setup


setup(
    name='iap',
    version='0.2',
    description='Python utilities for working with Apple In-App Purchases (IAP)',
    author='Educreations Engineering',
    author_email='engineering@educreations.com',
    py_modules=['iap'],
    install_requires=['pycrypto', 'django', 'requests'],
)
