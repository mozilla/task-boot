# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from setuptools import setup


def requirements(path):
    lines = []
    with open(path) as f:
        for line in f.read().splitlines():
            if line.startswith("https://"):
                line = line.split("#")[1].split("egg=")[1]
            lines.append(line)
    return sorted(lines)


setup(
    name="task-boot",
    version=open("VERSION").read().replace("\n", ""),
    author="Bastien Abadie",
    author_email="bastien@mozilla.com",
    description="An helper tool to bootstrap Taskcluster usage",
    url="https://github.com/mozilla/task-boot",
    license="MPL2",
    keywords="mozilla taskcluster ci",
    packages=["taskboot"],
    install_requires=requirements("requirements.txt"),
    tests_require=requirements("requirements-tests.txt"),
    entry_points={
        "console_scripts": ["tb = taskboot.cli:main", "taskboot = taskboot.cli:main"]
    },
)
