# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import logging
import os.path
import uuid

import taskcluster
import taskcluster_urls
import yaml

from taskboot.config import Configuration
from taskboot.docker import DinD
from taskboot.docker import Docker
from taskboot.docker import Podman
from taskboot.docker import patch_dockerfile
from taskboot.utils import retry
from taskboot.utils import zstd_compress

logger = logging.getLogger(__name__)


def gen_docker_images(docker_image_name, tags=None, registry=None):
    if not tags:
        tags = ["latest"]

    # Use unique instances of tags
    tags = sorted(set(tags))

    # Remove any potential existing tag
    tagless_image = docker_image_name.rsplit(":", 1)[0]

    result = []

    for tag in tags:
        if registry and not tagless_image.startswith(registry):
            full_tag = "{}/{}:{}".format(registry, tagless_image, tag)
        else:
            full_tag = "{}:{}".format(tagless_image, tag)

        logger.info("Will produce image {}".format(full_tag))
        result.append(full_tag)

    return result


def build_image(target, args):
    """
    Build a docker image and allow save/push
    """
    if args.build_tool == "docker":
        build_tool = Docker()
    elif args.build_tool == "podman":
        build_tool = Podman()
    elif args.build_tool == "dind":
        build_tool = DinD()
    else:
        raise ValueError("Unsupported build tool: {}".format(args.build_tool))

    # Load config from file/secret
    config = Configuration(args)

    # Check the dockerfile is available in target
    dockerfile = target.check_path(args.dockerfile)

    # Check the output is writable
    output = None
    if args.write:
        output = os.path.realpath(args.write)
        assert output.lower().endswith(".tar"), "Destination path must ends in .tar"
        assert os.access(
            os.path.dirname(output), os.W_OK | os.W_OK
        ), "Destination is not writable"

    # Build the tags
    base_image = args.image or "taskboot-{}".format(uuid.uuid4())
    tags = gen_docker_images(base_image, args.tag, args.registry)

    if args.push:
        assert config.has_docker_auth(), "Missing Docker authentication"
        registry = config.docker["registry"]

        if registry != args.registry:
            msg = "The credentials are the ones for %r not %r"
            logger.warning(msg, registry, args.registry)

        # Login on docker
        build_tool.login(registry, config.docker["username"], config.docker["password"])

    # Build the image
    build_tool.build(target.dir, dockerfile, tags, args.build_arg)

    # Write the produced image
    if output:
        build_tool.save(tags, output)
        zstd_compress(output)

    # Push the produced image
    if args.push:
        for tag in tags:
            build_tool.push(tag)


def build_compose(target, args):
    """
    Read a compose file and build each image described as buildable
    """
    assert args.build_retries > 0, "Build retries must be a positive integer"
    build_tool = Podman()

    # Check the dockerfile is available in target
    composefile = target.check_path(args.composefile)

    # Check compose file has version >= 3.0
    compose = yaml.load(open(composefile), Loader=yaml.SafeLoader)
    version = compose.get("version")
    assert version is not None, "Missing version in {}".format(composefile)
    assert compose["version"].startswith(
        "3."
    ), "Only docker compose version 3 is supported"

    # Check output folder
    output = None
    if args.write:
        output = os.path.realpath(args.write)
        os.makedirs(output, exist_ok=True)
        logger.info("Will write images in {}".format(output))

    # Load services
    services = compose.get("services")
    assert isinstance(services, dict), "Missing services"

    # All paths are relative to the dockerfile folder
    root = os.path.dirname(composefile)

    for name, service in services.items():
        build = service.get("build")
        if build is None:
            logger.info("Skipping service {}, no build declaration".format(name))
            continue

        if args.service and name not in args.service:
            msg = "Skipping service {}, building only {}".format(name, args.service)
            logger.info(msg)
            continue

        # Build the image
        logger.info("Building image for service {}".format(name))
        context = os.path.realpath(os.path.join(root, build.get("context", ".")))
        dockerfile = os.path.realpath(
            os.path.join(context, build.get("dockerfile", "Dockerfile"))
        )

        # We need to replace the FROM statements by their local versions
        # to avoid using the remote repository first
        patch_dockerfile(dockerfile, build_tool.list_images())

        docker_image = service.get("image", name)
        tags = gen_docker_images(docker_image, args.tag, args.registry)

        retry(
            lambda: build_tool.build(context, dockerfile, tags, args.build_arg),
            wait_between_retries=1,
            retries=args.build_retries,
        )

        # Write the produced image
        if output:
            output_path = os.path.join(output, f"{name}.tar")

            build_tool.save(tags, output_path)

            zstd_compress(output_path)

    logger.info("Compose file fully processed.")


def build_hook(target, args):
    """
    Read a hook definition file and either create or update the hook
    """
    hook_file_path = target.check_path(args.hook_file)

    hook_group_id = args.hook_group_id
    hook_id = args.hook_id

    with open(hook_file_path) as hook_file:
        payload = json.load(hook_file)

    # Load config from file/secret
    config = Configuration(args)

    hooks = taskcluster.Hooks(config.get_taskcluster_options())
    hooks.ping()

    hook_name = "{}/{}".format(hook_group_id, hook_id)
    logger.info("Checking if hook %s exists", hook_name)

    try:
        hooks.hook(hook_group_id, hook_id)
        hook_exists = True
        logger.info("Hook %s exists", hook_name)
    except taskcluster.exceptions.TaskclusterRestFailure:
        hook_exists = False
        logger.info("Hook %s does not exists", hook_name)

    if hook_exists:
        hooks.updateHook(hook_group_id, hook_id, payload)
        logger.info("Hook %s was successfully updated", hook_name)
    else:
        hooks.createHook(hook_group_id, hook_id, payload)
        logger.info("Hook %s was successfully created", hook_name)

    hook_url = taskcluster_urls.ui(
        config.get_root_url(), "hooks/{}/{}".format(hook_group_id, hook_id)
    )
    logger.info("Hook URL for debugging: %r", hook_url)
