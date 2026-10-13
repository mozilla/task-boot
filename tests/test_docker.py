# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import subprocess
import uuid

import pytest

from taskboot import docker
from taskboot.build import gen_docker_images
from taskboot.docker import get_filesystem_type
from taskboot.docker import parse_image_name
from taskboot.docker import patch_dockerfile
from taskboot.docker import read_manifest
from taskboot.docker import write_manifest

DOCKERFILE_SIMPLE = """
FROM project/base:latest
RUN something
CMD ["test"]
"""
DOCKERFILE_STAGES = """
FROM project/base:latest as build
RUN something

FROM project/another:123
COPY --from=build /src /dest
CMD ["test"]
"""


def test_parse_image_name():
    """
    Check the Docker image name & tag parser
    """
    assert parse_image_name("nginx") == ("nginx", "latest")
    assert parse_image_name("nginx:latest") == ("nginx", "latest")
    assert parse_image_name("nginx:v1.2.3") == ("nginx", "v1.2.3")
    assert parse_image_name("anotherImage-complicated:some-thing") == (
        "anotherImage-complicated",
        "some-thing",
    )
    assert parse_image_name("repo/project") == ("repo/project", "latest")
    assert parse_image_name("repo/project:latest") == ("repo/project", "latest")
    assert parse_image_name("repo/project:1.2") == ("repo/project", "1.2")
    assert parse_image_name("some/path/to/project") == (
        "some/path/to/project",
        "latest",
    )
    assert parse_image_name("some/path/to/project:abcd") == (
        "some/path/to/project",
        "abcd",
    )
    assert parse_image_name("registry.com/repo/project") == (
        "registry.com/repo/project",
        "latest",
    )


def test_patch_dockerfile(tmpdir):
    """
    Validate the Dockerfile patch by replacing images names/tags by local images digest
    """

    def patch(content, images):
        dockerfile = tmpdir.join(str(uuid.uuid4()))
        dockerfile.write(content)
        patch_dockerfile(str(dockerfile), images)
        return dockerfile.read()

    # No modifications when no images are provided
    images = []
    assert patch(DOCKERFILE_SIMPLE, images) == DOCKERFILE_SIMPLE

    # or the images do not match
    images = [{"repository": "another", "tag": "latest"}]
    assert patch(DOCKERFILE_SIMPLE, images) == DOCKERFILE_SIMPLE
    images = [{"repository": "project/base", "tag": "v123"}]
    assert patch(DOCKERFILE_SIMPLE, images) == DOCKERFILE_SIMPLE

    # Both repository & tag must match
    images = [
        {
            "repository": "project/base",
            "tag": "latest",
            "digest": "deadbeef12345",
            "registry": "hub.docker.com",
        }
    ]
    assert (
        patch(DOCKERFILE_SIMPLE, images)
        == """
FROM hub.docker.com/project/base@sha256:deadbeef12345
RUN something
CMD ["test"]
"""
    )

    # Multi stages images are supported
    images = [
        {
            "repository": "project/base",
            "tag": "latest",
            "digest": "deadbeef12345",
            "registry": "hub.docker.com",
        },
        {
            "repository": "project/another",
            "tag": "123",
            "digest": "coffee67890",
            "registry": "registry.mozilla.org",
        },
    ]
    assert (
        patch(DOCKERFILE_STAGES, images)
        == """
FROM hub.docker.com/project/base@sha256:deadbeef12345 AS build
RUN something

FROM registry.mozilla.org/project/another@sha256:coffee67890
COPY --from=build /src /dest
CMD ["test"]
"""
    )


def test_list_local_images(mock_docker):
    """
    Validate local images listing from img state
    """
    assert mock_docker.list_images() == []

    mock_docker.images = [
        (
            "registry.com/repo/test",
            "latest",
            "sha256:991d19e5156799aa79cf7138b8b843601f180e68f625b892df40a1993b7ac7da",
        )
    ]
    assert mock_docker.list_images() == [
        {
            "registry": "registry.com",
            "repository": "repo/test",
            "tag": "latest",
            "digest": "991d19e5156799aa79cf7138b8b843601f180e68f625b892df40a1993b7ac7da",
        }
    ]


def test_patch_manifest(hello_archive):
    """
    Test low level functions to patch a docker image
    """

    # Read original manifest
    manifest = read_manifest(hello_archive)
    assert manifest == [
        {
            "Config": "fce289e99eb9bca977dae136fbe2a82b6b7d4c372474c9235adc1741675f587e.json",
            "Layers": [
                "cdccdf50922d90e847e097347de49119be0f17c18b4a2d98da9919fa5884479d/layer.tar"
            ],
            "RepoTags": ["hello-world:latest"],
        }
    ]

    # Update it with different tags
    manifest[0]["RepoTags"] += ["another:tag", "mozilla/taskboot:test"]
    write_manifest(hello_archive, manifest)

    # Manifest should have changed
    manifest = read_manifest(hello_archive)
    assert manifest == [
        {
            "Config": "fce289e99eb9bca977dae136fbe2a82b6b7d4c372474c9235adc1741675f587e.json",
            "Layers": [
                "cdccdf50922d90e847e097347de49119be0f17c18b4a2d98da9919fa5884479d/layer.tar"
            ],
            "RepoTags": ["hello-world:latest", "another:tag", "mozilla/taskboot:test"],
        }
    ]


def test_tags_generation():
    """
    Validate full docker tags generation from image name + versions
    """
    assert gen_docker_images("myimage") == ["myimage:latest"]
    assert gen_docker_images("myimage:sometag") == ["myimage:latest"]
    assert gen_docker_images("myimage", tags=["test"]) == ["myimage:test"]
    assert gen_docker_images("myimage", tags=["test", "v1.2.3"]) == [
        "myimage:test",
        "myimage:v1.2.3",
    ]
    assert gen_docker_images("repo/myimage:xxx", tags=["test", "v1.2.3"]) == [
        "repo/myimage:test",
        "repo/myimage:v1.2.3",
    ]
    assert gen_docker_images(
        "repo/myimage:xxx", tags=["test", "v1.2.3", "latest", "test"]
    ) == ["repo/myimage:latest", "repo/myimage:test", "repo/myimage:v1.2.3"]
    assert gen_docker_images(
        "repo/myimage:xxx", tags=["a", "c", "b"], registry="somewhere.com"
    ) == [
        "somewhere.com/repo/myimage:a",
        "somewhere.com/repo/myimage:b",
        "somewhere.com/repo/myimage:c",
    ]


def test_get_filesystem_type(tmp_path):
    """
    Check the filesystem type lookup uses the closest mount point
    """
    mounts = tmp_path / "mounts"
    mounts.write_text(
        "overlay / overlay rw,relatime 0 0\n"
        "proc /proc proc rw,nosuid 0 0\n"
        "/dev/loop0 /var/lib/containers/storage ext4 rw,relatime 0 0\n"
        "tmpfs /var/lib/containers-other tmpfs rw 0 0\n"
    )

    assert get_filesystem_type("/var/lib/containers/storage", mounts) == "ext4"
    assert get_filesystem_type("/var/lib/containers/storage/x", mounts) == "ext4"
    assert get_filesystem_type("/var/lib/containers", mounts) == "overlay"
    assert get_filesystem_type("/proc/self", mounts) == "proc"


@pytest.mark.parametrize("failing_command", [None, "mkfs.ext4", "--bind"])
def test_setup_native_overlay(monkeypatch, tmp_path, failing_command):
    """
    Check the native overlay storage setup, and its cleanup when it fails
    """
    native_dir = str(tmp_path / "native")
    monkeypatch.setattr(docker, "PODMAN_GRAPHROOT", str(tmp_path / "graphroot"))
    monkeypatch.setattr(docker, "NATIVE_OVERLAY_DIR", native_dir)
    monkeypatch.setattr(docker, "get_filesystem_type", lambda path: "overlay")
    monkeypatch.setattr(docker.os, "geteuid", lambda: 0)
    monkeypatch.setattr(docker.shutil, "which", lambda binary: "/sbin/" + binary)
    env: dict[str, str] = {}
    monkeypatch.setattr(docker.os, "environ", env)

    commands = []

    def fake_run(command, check=False):
        commands.append(command)
        if failing_command in command:
            raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(docker.subprocess, "run", fake_run)

    docker.Podman.__new__(docker.Podman).setup_native_overlay()

    if failing_command is None:
        assert commands[-1] == [
            "mount",
            "--bind",
            native_dir + "/storage",
            str(tmp_path / "graphroot"),
        ]
        assert env == {
            "STORAGE_OPTS": "overlay.mountopt=nodev",
            "TMPDIR": native_dir + "/tmp",
        }
        assert (tmp_path / "native.img").exists()
    else:
        if failing_command == "--bind":
            assert commands[-1] == ["umount", native_dir]
        else:
            assert commands[-1][0] == "mkfs.ext4"
        assert env == {}
        assert not (tmp_path / "native.img").exists()
