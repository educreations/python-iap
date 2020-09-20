#!/usr/bin/env python

from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="iap",
    version="2.3.3",
    description="Python utilities for working with Apple In-App Purchases (IAP)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="MIT",
    keywords="iap appstore django",
    author="Educreations Engineering",
    author_email="engineering@educreations.com",
    url="https://github.com/educreations/python-iap",
    classifiers=[
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    packages=["iap"],
    package_dir={"iap": "iap"},
    install_requires=[
        "Django>=1.9",
        "pytz",
        "asn1crypto",
        "pyopenssl>=17.0.0",
        "requests",
    ],
    extras_require={"test": ["pytest", "pytest-django", "responses", "flake8"]},
    tests_require=["iap[test]"],
)
