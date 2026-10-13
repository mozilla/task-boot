# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import base64
import hashlib
import io
import json
import logging
import os
import re
import shutil
import subprocess
import tarfile
import tempfile

from dockerfile_parse import DockerfileParser

logger = logging.getLogger(__name__)

IMG_NAME_REGEX = re.compile(r"(?P<name>[\/\w\-\._]+):?(?P<tag>\S*)")

PODMAN_GRAPHROOT = "/var/lib/containers/storage"
NATIVE_OVERLAY_DIR = "/var/lib/taskboot"


def read_archive_tags(path):
    tar = tarfile.open(path)
    tags = []
    try:
        manifest_raw = tar.extractfile("manifest.json")
        manifest = json.loads(manifest_raw.read().decode("utf-8"))
        tags = manifest[0]["RepoTags"]
    except KeyError:
        # Use older image format:
        # {"registry.hub.docker.com/xyz/":{"master":"02d3443146cc39d41207919f156869d60942cd3eafeec793a4ac39f905f6f7c6"}}
        repositories_raw = tar.extractfile("repositories")
        repositories = json.loads(repositories_raw.read().decode("utf-8"))
        for repo, tag_and_sha in repositories.items():
            for tag, sha in tag_and_sha.items():
                tags.append("{}:{}".format(repo, tag))

    assert len(tags) > 0, "No tags found"
    return tags


class Tool(object):
    """
    Common interface for tools available in shell
    """

    def __init__(self, binary):
        # Check the tool is available on the system
        self.binary = shutil.which(binary)
        assert self.binary is not None, "Binary {} not found in PATH".format(binary)

    def run(self, command, **params):
        command = [self.binary] + command
        return subprocess.run(command, check=True, **params)


class Docker(Tool):
    """
    Interface to docker
    """

    def __init__(self):
        super().__init__("docker")

    def login(self, registry, username, password):
        """
        Login on remote registry
        """
        self.registry = registry
        cmd = ["login", "--password-stdin", "-u", username, registry]
        self.run(cmd, input=password.encode("utf-8"))
        logger.info("Authenticated on {} as {}".format(registry, username))

    def list_images(self):
        """
        List images stored in current state
        Parses the text output into usable dicts
        """
        # list images, skipping the ones without tags (dangling)
        ls = self.run(
            [
                "images",
                "--no-trunc",
                "--filter",
                "dangling=false",
                "--format",
                "{{ .Repository }} {{ .Tag }} {{ .Digest }}",
            ],
            stdout=subprocess.PIPE,
        )
        images = []
        for line in ls.stdout.splitlines():
            try:
                repository, tag, digest = line.decode("utf-8").split()
                if digest == "<none>":
                    logger.warn("Skipping image without digest: {}".format(line))
                    continue
                repository_parts = repository.split("/")
                if len(repository_parts) < 3:
                    registry = None
                else:
                    registry = repository_parts[0]
                    repository = "/".join(repository_parts[1:])
                images.append(
                    {
                        "registry": registry,
                        "repository": repository,
                        "tag": tag,
                        "digest": digest,
                    }
                )
            except ValueError:
                logger.warn("Did not parse this image: {}".format(line))
        return images

    def build(self, context_dir, dockerfile, tags, build_args=[]):
        logger.info("Building docker image {}".format(dockerfile))

        command = ["build", "--file", dockerfile] + self.build_flags()

        for add_tag in tags:
            command += ["--tag", add_tag]

        for single_build_arg in build_args:
            command += ["--build-arg", single_build_arg]

        command.append(context_dir)

        logger.info("Running docker command: {}".format(command))

        self.run(command)
        logger.info("Built image {}".format(", ".join(tags)))

    def build_flags(self):
        return []

    def save(self, tags, path):
        assert isinstance(tags, list)
        assert len(tags) > 0, "Missing tags"
        logger.info("Saving image with tags {} to {}".format(", ".join(tags), path))
        command = ["save", "--output", path] + tags
        self.run(command)

    def load(self, path):
        logger.info("Loading image from {}".format(path))
        self.run(["load", "--input", path])

    def push(self, tag):
        logger.info("Pushing image {}".format(tag))
        self.run(["push", tag])

    def tag(self, source, target):
        logger.info("Tagging {} with {}".format(source, target))
        self.run(["tag", source, target])

    def push_archive(self, path, custom_tag=None):
        """
        Push a local tar archive on the remote repo from config
        The tags used on the image are all used to push
        """
        assert os.path.exists(path), "Missing archive {}".format(path)
        assert tarfile.is_tarfile(path), "Not a TAR archive {}".format(path)

        tags = read_archive_tags(path)
        self.load(path)

        if custom_tag:
            self.tag(tags[0], custom_tag)
            tags = [custom_tag]

        for tag in tags:
            # Check the registry is in the tag
            assert tag.startswith(self.registry), (
                "Invalid tag {} : must use registry {}".format(tag, self.registry)
            )

            logger.info("Pushing image as {}".format(tag))
            self.push(tag)
            logger.info("Push successful")


class Podman(Docker):
    """
    Interface to the podman tool, replacing docker daemon
    """

    def __init__(self):
        Tool.__init__(self, "podman")

    def setup_native_overlay(self):
        """
        Back podman storage with an ext4 loop device when it would otherwise
        sit on an overlayfs (e.g. when running in a Docker container): podman
        then has to use fuse-overlayfs, which makes every commit walk the whole
        image, whereas the native overlay driver can diff layers directly.
        Falls back to the default storage if anything goes wrong.
        """
        if os.geteuid() != 0 or shutil.which("mkfs.ext4") is None:
            return
        if get_filesystem_type(PODMAN_GRAPHROOT) != "overlay":
            return
        if os.path.isdir(PODMAN_GRAPHROOT) and os.listdir(PODMAN_GRAPHROOT):
            logger.info("Podman storage is not empty, keeping it")
            return

        image = "{}.img".format(NATIVE_OVERLAY_DIR)
        storage = os.path.join(NATIVE_OVERLAY_DIR, "storage")
        # Buildah creates overlays (e.g. for rw bind mounts) in its temporary
        # directory, so it must not be on an overlayfs either.
        tmp = os.path.join(NATIVE_OVERLAY_DIR, "tmp")
        mounted = []
        try:
            os.makedirs(NATIVE_OVERLAY_DIR, exist_ok=True)
            # Sparse file, so it only takes the space actually used.
            with open(image, "wb") as f:
                f.truncate(shutil.disk_usage(os.path.dirname(image)).free)
            subprocess.run(["mkfs.ext4", "-q", image], check=True)
            subprocess.run(
                ["mount", "-o", "loop", image, NATIVE_OVERLAY_DIR], check=True
            )
            mounted.append(NATIVE_OVERLAY_DIR)
            os.makedirs(storage)
            os.makedirs(tmp)
            os.makedirs(PODMAN_GRAPHROOT, exist_ok=True)
            subprocess.run(["mount", "--bind", storage, PODMAN_GRAPHROOT], check=True)
            mounted.append(PODMAN_GRAPHROOT)
        except (OSError, subprocess.CalledProcessError) as e:
            logger.warning("Could not set up native overlay storage: {}".format(e))
            for path in reversed(mounted):
                subprocess.run(["umount", path])
            if os.path.exists(image):
                os.remove(image)
            return

        # Replace the storage options from the configuration, which make podman
        # use fuse-overlayfs.
        os.environ["STORAGE_OPTS"] = "overlay.mountopt=nodev"
        os.environ["TMPDIR"] = tmp
        logger.info("Using native overlay storage backed by {}".format(image))

    def build_flags(self):
        # Intermediate layers are only useful as a cache for later builds, which
        # we never have, and committing each of them is slow.
        return ["--layers=false"]

    def list_images(self):
        """
        List images stored in current state
        Parses the text output into usable dicts
        """
        result = super().list_images()
        for image in result:
            if image["digest"].startswith("sha256:"):
                image["digest"] = image["digest"][7:]
        return result


class Skopeo(Tool):
    """
    Interface to the skopeo tool, used to copy local images to remote repositories
    """

    def __init__(self):
        super().__init__("skopeo")

    def login(self, registry, username, password):
        """
        Generate auth file
        """
        # Setup the authentication
        _, self.auth_file = tempfile.mkstemp(suffix="-skopeo.json")
        pair = "{}:{}".format(username, password).encode("utf-8")
        server = "https://{}/v1".format(registry)
        self.registry = registry
        auth = {"auths": {server: {"auth": base64.b64encode(pair).decode("utf-8")}}}
        with open(self.auth_file, "w") as f:
            json.dump(auth, f)

    def push_archive(self, path, custom_tag=None):
        """
        Push a local tar OCI archive on the remote repo from config
        The tags used on the image are all used to push
        """
        assert os.path.exists(path), "Missing archive {}".format(path)
        assert tarfile.is_tarfile(path), "Not a TAR archive {}".format(path)

        if not custom_tag:
            tags = read_archive_tags(path)
        else:
            tags = [custom_tag]

        for tag in tags:
            # Check the registry is in the tag
            assert tag.startswith(self.registry), (
                "Invalid tag {} : must use registry {}".format(tag, self.registry)
            )

            logger.info("Pushing image as {}".format(tag))
            cmd = [
                "--debug",
                "copy",
                "--retry-times",
                "3",
                "--authfile",
                self.auth_file,
                "docker-archive:{}".format(path),
                "docker://{}".format(tag),
            ]
            self.run(cmd)
            logger.info("Push successful")


def get_filesystem_type(path, mounts="/proc/self/mounts"):
    """
    Find the type of the filesystem holding path, even if it doesn't exist yet
    """
    path = os.path.realpath(path)
    best_mount_point, best_type = "", None
    with open(mounts) as f:
        for line in f:
            _, mount_point, fs_type = line.split()[:3]
            if (
                path == mount_point or path.startswith(mount_point.rstrip("/") + "/")
            ) and len(mount_point) > len(best_mount_point):
                best_mount_point, best_type = mount_point, fs_type
    return best_type


def docker_id_archive(path):
    """Get docker image ID

    Docker image ID corresponds to the sha256 hash of the config file.
    Imported from release-services
    """
    tar = tarfile.open(path)
    manifest = json.load(tar.extractfile("manifest.json"))
    config = tar.extractfile(manifest[0]["Config"])
    image_sha256 = hashlib.sha256(config.read()).hexdigest()
    return f"sha256:{image_sha256}"


def parse_image_name(image_name):
    """
    Helper to convert a Docker image name
    into a tuple (name, tag)
    Supports formats :
    * nginx
    * library/nginx
    * nginx:latest
    * myrepo/nginx:v123
    """
    match = IMG_NAME_REGEX.match(image_name)
    if match is None:
        return (None, None)
    return (match.group("name"), match.group("tag") or "latest")


def patch_dockerfile(dockerfile, images):
    """
    Patch an existing Dockerfile to replace FROM image statements
    by their local images with digests. It supports multi-stage images
    This is needed to avoid retrieving remote images before checking current img state
    Bug https://github.com/genuinetools/img/issues/206
    """
    assert os.path.exists(dockerfile), "Missing dockerfile {}".format(dockerfile)
    assert isinstance(images, list)
    if not images:
        return

    def _find_replacement(original):
        # Replace an image name by its local version
        # when it exists
        repo, tag = parse_image_name(original)
        for image in images:
            if image["repository"] == repo and image["tag"] == tag:
                if image["registry"]:
                    local = "{}/{}@sha256:{}".format(
                        image["registry"], image["repository"], image["digest"]
                    )
                else:
                    local = "{}@sha256:{}".format(image["repository"], image["digest"])
                logger.info("Replacing image {} by {}".format(original, local))
                return local

        return original

    # Parse the given dockerfile and update its parent images
    # with local version given by current img state
    # The FROM statement parsing & replacement is provided
    # by the DockerfileParser
    parser = DockerfileParser()
    parser.dockerfile_path = dockerfile
    parser.content = open(dockerfile).read()
    logger.info("Initial parent images: {}".format(" & ".join(parser.parent_images)))
    parser.parent_images = list(map(_find_replacement, parser.parent_images))


def read_manifest(path):
    """
    Read a Docker archive manifest and load it as JSON
    """
    assert os.path.exists(path), "Missing archive {}".format(path)
    assert tarfile.is_tarfile(path), "Not a TAR archive {}".format(path)

    with tarfile.open(path) as tar:
        manifest_raw = tar.extractfile("manifest.json")
        return json.load(manifest_raw)


def write_manifest(path, manifest):
    """
    Update the manifest of an existing Docker archive image
    Used to update tags
    """
    assert os.path.exists(path), "Missing archive {}".format(path)
    assert tarfile.is_tarfile(path), "Not a TAR archive {}".format(path)
    assert isinstance(manifest, list)

    # Tar file content must be provided as bytes
    content = json.dumps(manifest).encode("utf-8")

    # TarInfo is the pointer to the data in the tar archive
    index = tarfile.TarInfo("manifest.json")
    index.size = len(content)

    # Open the archive in append mode, and overwrite the existing file
    with tarfile.open(path, "a") as tar:
        tar.addfile(index, io.BytesIO(content))
        logger.info("Patched manifest of archive {}".format(path))
