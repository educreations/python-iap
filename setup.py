#!/usr/bin/env python

from setuptools import setup


setup(
    name="iap",
    version="2.2.2",
    description="Python utilities for working with Apple In-App Purchases (IAP)",
    license="MIT",
    keywords="iap appstore django",
    author="Educreations Engineering",
    author_email="engineering@educreations.com",
    url="https://github.com/educreations/python-iap",
    packages=["iap"],
    package_dir={"iap": "iap"},
    install_requires=[
        "Django>=1.7",
        "pyopenssl>=17.0.0",
        "pyasn1",
        "pyasn1_modules",
        "requests",
    ],
    extras_require={"test": ["pytest", "pytest-django", "responses"]},
    tests_require=["iap[test]"],
)
