# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import json
import logging
import pathlib
import re
from typing import List

from github import Commit
from github import Github
from github import GitRef
from github import Repository
from github import UnknownObjectException

from taskboot.config import Configuration
from taskboot.target import Target
from taskboot.utils import load_named_artifacts

logger = logging.getLogger(__name__)

RELEASE_MESSAGE_REGEX = re.compile(r"^(release|version|bump to) ([\w\-_\.]+)$")


def is_release_commit(commit: Commit.Commit, tags: List[str]) -> bool:
    """
    Check if the github commit is a known tag and has a release message like:
    - Release XXX
    - Version XXX
    - Bump to XXX
    """

    # Check if that commit is a tag too
    if commit.commit.sha not in tags:
        return False

    # Check if the commit matches the release message regex
    message = commit.commit.message
    if RELEASE_MESSAGE_REGEX.match(message.lower()):
        logger.info(f"Detected release commit {commit.commit.sha}: {message}")
        return True

    return False


def build_release_notes(repository: Repository.Repository, tag: GitRef.GitRef) -> str:
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
        commits = [commit for commit in repository.get_commits()]

    # List existing tags sha
    tags = [tag.commit.sha for tag in repository.get_tags()]

    # Use first line of every commit in between versions
    lines = [
        "- {}".format(commit.commit.message.splitlines()[0])
        for commit in commits
        if not is_release_commit(commit, tags)
    ]

    return "\n".join(lines) + signature


def github_release(target: Target, args: argparse.Namespace) -> None:
    """
    Push all artifacts from dependent tasks
    """
    assert args.task_id is not None, "Missing task id"

    # Load config from file/secret
    config = Configuration(args)
    assert config.has_git_auth(), "Missing Github authentication"

    # Check if local or dependent task assets are used
    if args.local_asset is None:
        # Check the assets before any Github change is applied
        assets = list(load_named_artifacts(config, args.task_id, args.asset))
    else:
        # Create a list of tuples structured in this way
        # (name, artifact_name, artifact_path)
        assets = [
            (
                str(pathlib.Path(artifact_path).stem),
                artifact_path,
                pathlib.Path(artifact_path),
            )
            for artifact_path in args.local_asset
        ]

    # Setup GitHub API client and load repository
    github = Github(config.git["token"])
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


def github_repository_dispatch(target: Target, args: argparse.Namespace) -> None:
    """
    Push all artifacts from dependent tasks
    """
    # Load config from file/secret
    config = Configuration(args)
    assert config.has_git_auth(), "Missing Github authentication"

    # Setup GitHub API client and load repository
    github = Github(config.git["token"])
    try:
        repository = github.get_repo(args.repository)
        logger.info(f"Loaded Github repository {repository.full_name} #{repository.id}")
    except UnknownObjectException:
        raise Exception(f"Repository {args.repository} is not available")

    repository.create_repository_dispatch(
        args.event_type,
        json.loads(args.client_payload) if args.client_payload is not None else None,
    )

    logger.info("Repository dispatch triggered")
