# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import logging
import os

from taskboot.aws import push_s3
from taskboot.build import build_compose
from taskboot.build import build_hook
from taskboot.build import build_image
from taskboot.github import github_release
from taskboot.push import heroku_release
from taskboot.push import push_artifacts
from taskboot.pypi import publish_pypi
from taskboot.target import Target

logging.basicConfig(level=logging.INFO)


def usage(target, args):
    print("Here is how to use taskboot...")


def main():
    parser = argparse.ArgumentParser(prog="taskboot")
    parser.add_argument(
        "--config", type=open, help="Path to local configuration/secrets file"
    )
    parser.add_argument(
        "--secret",
        type=str,
        default=os.environ.get("TASKCLUSTER_SECRET"),
        help="Taskcluster secret path",
    )
    parser.add_argument(
        "--git-repository",
        type=str,
        default=os.environ.get("GIT_REPOSITORY"),
        help="Target git repository",
    )
    parser.add_argument(
        "--git-revision",
        type=str,
        default=os.environ.get("GIT_REVISION", "master"),
        help="Target git revision",
    )
    parser.add_argument(
        "--target", type=str, help="Target directory to use a local project"
    )
    parser.add_argument(
        "--cache", type=str, help="Path to a local folder used to cache build processes"
    )
    commands = parser.add_subparsers(help="sub-command help")
    parser.set_defaults(func=usage)

    # Build a docker image
    build = commands.add_parser("build", help="Build a docker image")
    build.add_argument("dockerfile", type=str, help="Path to Dockerfile to build")
    build.add_argument("--write", type=str, help="Path to write the docker image")
    build.add_argument(
        "--push",
        action="store_true",
        default=False,
        help="Push after building on configured repository",
    )
    build.add_argument(
        "--image",
        type=str,
        help="The docker image without tag, default to a random one",
    )
    build.add_argument(
        "--registry",
        type=str,
        default=os.environ.get("REGISTRY", "registry.hub.docker.com"),
        help="Docker registry to use in images tags",
    )
    build.add_argument(
        "--tag",
        type=str,
        action="append",
        default=[],
        help="Use a specific tag on this image, default to latest tag",
    )
    build.add_argument(
        "--build-arg",
        type=str,
        action="append",
        default=[],
        help="Docker build args passed the docker command",
    )
    build.add_argument(
        "--build-tool",
        dest="build_tool",
        choices=["img", "docker"],
        default=os.environ.get("BUILD_TOOL") or "img",
        help="Tool to build docker images.",
    )
    build.set_defaults(func=build_image)

    # Build images from a docker-compose.yml file
    compose = commands.add_parser(
        "build-compose", help="Build images from a docker-compose file"
    )
    compose.add_argument(
        "--compose-file",
        "-c",
        dest="composefile",
        type=str,
        help="Path to docker-compose.yml to use",
        default="docker-compose.yml",
    )
    compose.add_argument(
        "--registry",
        type=str,
        default=os.environ.get("REGISTRY", "registry.hub.docker.com"),
        help="Docker registry to use in images tags",
    )
    compose.add_argument(
        "--write", type=str, help="Directory to write the docker images"
    )
    compose.add_argument(
        "--build-retries",
        "-r",
        type=int,
        default=3,
        help="Number of times taskbook will retry building each image",
    )
    compose.add_argument(
        "--build-arg",
        type=str,
        default=[],
        action="append",
        help="Docker build args passed for each built service",
    )
    compose.add_argument(
        "--service",
        type=str,
        action="append",
        default=[],
        help="Build only the specific compose service",
    )
    compose.add_argument(
        "--tag",
        type=str,
        action="append",
        default=[],
        help="Use a specific tag on this image, default to latest tag",
    )
    compose.set_defaults(func=build_compose)

    # Push docker images produced in other tasks
    artifacts = commands.add_parser(
        "push-artifact", help="Push docker images produced in dependent tasks"
    )
    artifacts.add_argument(
        "--task-id",
        type=str,
        default=os.environ.get("TASK_ID"),
        help="Taskcluster task group to analyse",
    )
    artifacts.add_argument(
        "--artifact-filter",
        type=str,
        default="public/**.tar",
        help="Filter applied to artifacts paths, supports fnmatch syntax.",
    )
    artifacts.add_argument(
        "--exclude-filter",
        type=str,
        help="If an artifact match the exclude filter it won't be uploaded, supports fnmatch syntax.",
    )
    artifacts.add_argument(
        "--push-tool",
        dest="push_tool",
        choices=["skopeo", "docker"],
        default=os.environ.get("PUSH_TOOL") or "skopeo",
        help="Tool to push docker images.",
    )
    artifacts.set_defaults(func=push_artifacts)

    # Ensure the given hook is up-to-date with the given definition
    hooks = commands.add_parser(
        "build-hook",
        help="Ensure the given hook is up-to-date with the given definition",
    )
    hooks.add_argument("hook_file", type=str, help="Path to the hook definition")
    hooks.add_argument("hook_group_id", type=str, help="Hook group ID")
    hooks.add_argument("hook_id", type=str, help="Hook ID")
    hooks.set_defaults(func=build_hook)

    # Push and trigger a Heroku release
    deploy_heroku = commands.add_parser(
        "deploy-heroku", help="Push and trigger a Heroku release"
    )
    deploy_heroku.add_argument(
        "--task-id",
        type=str,
        default=os.environ.get("TASK_ID"),
        help="Taskcluster task group to analyse",
    )
    deploy_heroku.add_argument("--heroku-app", type=str, required=True)
    deploy_heroku.add_argument(
        "artifacts",
        nargs="+",
        help="the mapping of worker-type:artifact-path to deploy",
    )
    deploy_heroku.set_defaults(func=heroku_release)

    # Push files on an AWS S3 bucket
    deploy_s3 = commands.add_parser("deploy-s3", help="Push files on an AWS S3 bucket")
    deploy_s3.add_argument(
        "--task-id",
        type=str,
        default=os.environ.get("TASK_ID"),
        help="Taskcluster task group to analyse",
    )
    deploy_s3.add_argument(
        "--artifact-folder",
        type=str,
        help="Prefix of the Taskcluster artifact folder to upload on S3."
        "All files in that folder will be at the root of the bucket",
        required=True,
    )
    deploy_s3.add_argument(
        "--bucket", type=str, help="The S3 bucket to use", required=True
    )
    deploy_s3.set_defaults(func=push_s3)

    # Publish on a PyPi repository
    deploy_pypi = commands.add_parser(
        "deploy-pypi", help="Publish source code on a Pypi repository"
    )
    deploy_pypi.add_argument(
        "--repository",
        type=str,
        default=os.environ.get("PYPI_REPOSITORY"),
        help="PyPi repository to use for publication",
    )
    deploy_pypi.set_defaults(func=publish_pypi)

    # Deploy as a github release
    github_release_cmd = commands.add_parser(
        "github-release", help="Create a GitHub release and publish assets"
    )
    github_release_cmd.add_argument(
        "repository",
        type=str,
        help="Github repository name to use (example: mozilla/task-boot)",
    )
    github_release_cmd.add_argument(
        "version", type=str, help="Release version tag to create or update on github"
    )
    github_release_cmd.add_argument(
        "--task-id",
        type=str,
        default=os.environ.get("TASK_ID"),
        help="Taskcluster task group to analyse",
    )
    github_release_cmd.add_argument(
        "--asset",
        nargs="+",
        type=str,
        help="Asset to upload on the release, retrieved from previously created artifacts. Format is asset-name:path/to/artifact",
    )
    github_release_cmd.set_defaults(func=github_release)

    # Always load the target
    args = parser.parse_args()
    target = Target(args)

    # Call the assigned function
    args.func(target, args)


if __name__ == "__main__":
    main()
