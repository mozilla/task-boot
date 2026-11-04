# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import os

import pytest

from taskboot import pypi
from taskboot.config import Configuration

PYPROJECT = """
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "dummy"
version = "1.2.3"
"""

SETUP_PY = """
from setuptools import setup

setup(name="dummy", version="1.2.3", packages=["dummy"])
"""


@pytest.fixture
def uploads(monkeypatch):
    uploaded = []

    monkeypatch.setattr(
        Configuration,
        "config",
        {"pypi": {"username": "user", "password": "pass"}},
    )
    monkeypatch.setattr(
        pypi,
        "twine_upload",
        lambda settings, files: uploaded.extend(os.path.basename(f) for f in files),
    )

    return uploaded


def _publish(tmp_path):
    target = argparse.Namespace(dir=str(tmp_path))
    args = argparse.Namespace(secret=None, config=None, repository=None)
    pypi.publish_pypi(target, args)


@pytest.mark.parametrize(
    "files",
    [
        {"pyproject.toml": PYPROJECT},
        {"setup.py": SETUP_PY},
    ],
    ids=["pyproject", "setup.py"],
)
def test_publish_pypi(tmp_path, uploads, files):
    (tmp_path / "dummy").mkdir()
    (tmp_path / "dummy" / "__init__.py").write_text("")
    for name, content in files.items():
        (tmp_path / name).write_text(content)

    # Stale files from a previous build must not be uploaded
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "stale-0.0.1.tar.gz").write_text("")

    _publish(tmp_path)

    assert sorted(uploads) == [
        "dummy-1.2.3-py3-none-any.whl",
        "dummy-1.2.3.tar.gz",
    ]


def test_publish_pypi_missing_project(tmp_path, uploads):
    with pytest.raises(AssertionError, match="Missing pyproject.toml or setup.py"):
        _publish(tmp_path)
    assert uploads == []
