# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging

from github import Github
from github import UnknownObjectException

from taskboot.config import Configuration
from taskboot.utils import load_named_artifacts

logger = logging.getLogger(__name__)


def build_release_notes(repository, tag):
    signature = (
        "\n---\nReleased with [mozilla/task-boot](https://github.com/mozilla/task-boot)"
    )

    # Get all commits between both versions using the comparison endpoint
    try:
        latest_release = repository.get_latest_release()
        diff = repository.compare(latest_release.tag_name, tag.ref)
        commits = diff.commits
    except UnknownObjectException:
        logger.info("No previous release available, will use all commits on repo")
        commits = repository.get_commits()

    # Use first line of every commit in between versions
    lines = ["- {}".format(commit.commit.message.splitlines()[0]) for commit in commits]

    return "\n".join(lines) + signature


def github_release(target, args):
    """
    Push all artifacts from dependent tasks
    """
    assert args.task_id is not None, "Missing task id"

    # Load config from file/secret
    config = Configuration(args)
    assert config.has_github_auth(), "Missing Github authentication"

    # Check the assets before any Github change is applied
    assets = list(load_named_artifacts(config, args.task_id, args.asset))

    # Setup GitHub API client and load repository
    github = Github(config.github["token"])
    try:
        repository = github.get_repo(args.repository)
        logger.info(f"Loaded Github repository {repository.full_name} #{repository.id}")
    except UnknownObjectException:
        raise Exception(f"Repository {args.repository} is not available")

    # Check that tag exists, it must be created by the user manually
    # Usually this task is triggered on a github tag event
    logger.debug(f"Checking git tag {args.version}")
    try:
        tag = repository.get_git_ref(f"tags/{args.version}")
        logger.info(f"Found existing tag {args.version}")
    except UnknownObjectException:
        raise Exception(f"Tag {args.version} does not exist on {repository}")

    # Check if requested release exists
    logger.debug(f"Checking requested release {args.version}")
    try:
        release = repository.get_release(args.version)
        logger.info(f"Found existing release {args.version}")
    except UnknownObjectException:
        # Create new release
        logger.info(f"Creating new release {args.version}")
        release = repository.create_git_release(
            tag=args.version,
            name=args.version,
            message=build_release_notes(repository, tag),
            target_commitish=tag.object.sha,
        )

    # Upload every named asset
    for asset_name, _, artifact_path in assets:
        logger.info(f"Uploading asset {asset_name} using {artifact_path}")
        release.upload_asset(name=asset_name, path=artifact_path, label=asset_name)

    logger.info(f"Release available as {release.html_url}")
