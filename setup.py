#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))


def get_version():
    version_file_path = os.path.join(here, "package_version.txt")
    if not os.path.isfile(version_file_path):
        return "debug"
    version = None
    with open(version_file_path, "r") as raw:
        version = raw.read()

    return version


def get_requirements():
    with open(os.path.join(os.path.dirname(__file__), "requirements.txt")) as raw:
        return [r.strip() for r in raw.read().split("\n") if len(r.strip()) > 0]


setup(
    name="filebase_api",
    version=get_version(),
    description="A simple web api builder for python apps. Integrates Jinja templates, fileserver and websockets.",
    long_description="Please see the github repo and help @ https://github.com/LamaAni/FilebaseAPI",
    classifiers=[],
    author="Zav Shotan",
    author_email="",
    url="https://github.com/LamaAni/FilebaseAPI",
    packages=["filebase_api", "filebase_api/session", "filebase_api/web"],
    platforms="any",
    license="LICENSE",
    install_requires=get_requirements(),
    python_requires=">=3.6",
    include_package_data=True,
)
