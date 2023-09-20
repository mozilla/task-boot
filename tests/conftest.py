# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import subprocess

import pytest

from taskboot.docker import Podman

TESTS_DIR = os.path.realpath(os.path.dirname(__file__))


@pytest.fixture
def mock_docker(tmpdir):
    """
    Mock the Docker tool class (podman) with a fake state
    """

    class MockDocker(Podman):
        def __init__(self):
            self.state = None
            self.images = []

        def run(self, command, **kwargs):
            # Fake podman calls
            if command[0] == "images":
                # Fake image listing
                output = "Headers\n"  # will be skipped by parser
                output += "\n".join(["\t".join(image) for image in self.images])
                return subprocess.CompletedProcess(
                    args=command, returncode=0, stdout=output.encode("utf-8")
                )

            else:
                raise Exception(
                    "Unsupported command in mock: {}".format(" ".join(command))
                )

    return MockDocker()


@pytest.fixture
def hello_archive(tmp_path):
    """
    Get a temporary copy of the helloworld docker archive
    """
    path = os.path.join(TESTS_DIR, "hello.tar")
    hello = tmp_path / "hello.tar"
    hello.write_bytes(open(path, "rb").read())
    return hello
