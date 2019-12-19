# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging

import requests
import taskcluster

from taskboot.config import Configuration
from taskboot.docker import Docker
from taskboot.docker import Skopeo
from taskboot.docker import docker_id_archive
from taskboot.utils import download_artifact
from taskboot.utils import load_artifacts
from taskboot.utils import load_named_artifacts

logger = logging.getLogger(__name__)

HEROKU_REGISTRY = "registry.heroku.com"


def push_artifacts(target, args):
    """
    Push all artifacts from dependent tasks
    """
    assert args.task_id is not None, "Missing task id"

    # Load config from file/secret
    config = Configuration(args)
    assert config.has_docker_auth(), "Missing Docker authentication"

    if args.push_tool == "skopeo":
        push_tool = Skopeo()
    elif args.push_tool == "docker":
        push_tool = Docker()
    else:
        raise ValueError("Not  supported push tool: {}".format(args.push_tool))

    push_tool.login(
        config.docker["registry"], config.docker["username"], config.docker["password"]
    )

    # Load queue service
    queue = taskcluster.Queue(config.get_taskcluster_options())

    # Load dependencies artifacts
    artifacts = load_artifacts(
        args.task_id, queue, args.artifact_filter, args.exclude_filter
    )

    for task_id, artifact_name in artifacts:
        push_artifact(queue, push_tool, task_id, artifact_name)

    logger.info("All found artifacts were pushed.")


def push_artifact(queue, push_tool, task_id, artifact_name, custom_tag=None):
    """
    Download an artifact, reads its tags
    and push it on remote repo
    """
    path = download_artifact(queue, task_id, artifact_name)
    push_tool.push_archive(path, custom_tag)


def heroku_release(target, args):
    """
    Push all artifacts from dependent tasks
    """
    assert args.task_id is not None, "Missing task id"

    # Load config from file/secret
    config = Configuration(args)

    assert (
        "username" in config.heroku and "password" in config.heroku
    ), "Missing Heroku authentication"

    # Setup skopeo
    skopeo = Skopeo()
    skopeo.login(HEROKU_REGISTRY, config.heroku["username"], config.heroku["password"])

    updates_payload = []

    for heroku_dyno_name, _, artifact_path in load_named_artifacts(
        config, args.task_id, args.artifacts
    ):

        # Push the Docker image
        custom_tag_name = f"{HEROKU_REGISTRY}/{args.heroku_app}/{heroku_dyno_name}"

        skopeo.push_archive(artifact_path, custom_tag_name)

        # Get the Docker image id
        image_id = docker_id_archive(artifact_path)

        updates_payload.append({"type": heroku_dyno_name, "docker_image": image_id})

    # Trigger a release on Heroku
    logger.info(
        "Deploying update for dyno types: %r",
        list(sorted(x["type"] for x in updates_payload)),
    )

    updates_payload = {"updates": updates_payload}
    logger.debug("Using payload: %r", updates_payload)

    r = requests.patch(
        f"https://api.heroku.com/apps/{args.heroku_app}/formation",
        json=updates_payload,
        headers={
            "Accept": "application/vnd.heroku+json; version=3.docker-releases",
            "Authorization": f"Bearer {config.heroku['password']}",
        },
    )
    logger.debug("Heroku deployment answer: %s", r.text)
    r.raise_for_status()

    logger.info(f"The {args.heroku_app} application has been updated")
