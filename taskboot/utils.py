# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import os
import pathlib
import tempfile
import time
from fnmatch import fnmatch

import requests
import taskcluster
import zstandard

logger = logging.getLogger(__name__)


def retry(operation, retries=5, wait_between_retries=30, exception_to_break=None):
    """
    Retry an operation several times
    """
    for i in range(retries):
        try:
            logger.debug("Trying {}/{}".format(i + 1, retries))
            return operation()
        except Exception as e:
            logger.warn("Try failed: {}".format(e))
            if exception_to_break and isinstance(e, exception_to_break):
                raise
            if i == retries - 1:
                raise
            time.sleep(wait_between_retries)


def download_progress(url, path):
    """
    Download a file using a streamed response
    and display progress
    """
    written = 0
    percent = 0
    with requests.get(url, stream=True) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", 0))
        assert total > 0, "No content-length"
        with open(path, "wb") as f:
            logger.info("Writing artifact in {}".format(path))
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    x = f.write(chunk)
                    written += x
                    p = int(100.0 * written / total)
                    if p % 10 == 0 and p > percent:
                        percent = p
                        logger.info("Written {} %".format(p))

    logger.info("Written {} with {} bytes".format(path, written))
    return written


def load_artifacts(task_id, queue, artifact_filter, exclude_filter=None):
    """
    Load Taskcluster artifacts from all tasks depending on specified one
    This will filter all the artifacts using inclusion and exclusion glob matches
    """
    # Load current task description to list its dependencies
    logger.info("Loading task status {}".format(task_id))
    task = queue.task(task_id)
    nb_deps = len(task["dependencies"])
    assert nb_deps > 0, "No task dependencies"

    # Get the list of matching artifacts as we should get only one
    matching_artifacts = []

    # Load dependencies artifacts
    for i, task_id in enumerate(task["dependencies"]):
        logger.info(
            "Loading task dependencies {}/{} {}".format(
                i + 1, len(task["dependencies"]), task_id
            )
        )
        task_artifacts = queue.listLatestArtifacts(task_id)

        # Only process the filtered artifacts
        for artifact in task_artifacts["artifacts"]:
            artifact_name = artifact["name"]
            if fnmatch(artifact_name, artifact_filter):
                if exclude_filter and fnmatch(artifact_name, exclude_filter):
                    logger.info(
                        "Excluding artifact %s because of exclude filter",
                        artifact_name,
                    )
                    continue

                matching_artifacts.append((task_id, artifact_name))

    return matching_artifacts


def download_artifact(queue, task_id, artifact_name, output_directory=None):
    """
    Download a Taskcluster artifact into a local tempfile
    """
    logger.info("Download {} from {}".format(artifact_name, task_id))

    # Build artifact url
    try:
        url = queue.buildSignedUrl("getLatestArtifact", task_id, artifact_name)
    except taskcluster.exceptions.TaskclusterAuthFailure:
        url = queue.buildUrl("getLatestArtifact", task_id, artifact_name)

    if output_directory is None:
        # Download the artifact in a temporary file
        _, ext = os.path.splitext(artifact_name)
        _, path = tempfile.mkstemp(suffix="-taskboot{}".format(ext))
    else:
        # Download the artifact in a specific directory
        path = output_directory.absolute() / pathlib.Path(artifact_name).name

    retry(lambda: download_progress(url, path))

    return path


def load_named_artifacts(config, source_task_id, arguments, output_directory=None):
    """
    Parse a list of CLI arguments used to name artifacts as name:path/to/artifact
    Download the relevant artifact from the targeted task and outputs
    the path for further processing
    """
    if not arguments:
        logger.info("No artifact arguments to process")
        return

    bad_parameter_error_message = "{!r} doesn't match format 'name:path/to/artifact'"

    queue = taskcluster.Queue(config.get_taskcluster_options())

    for artifact in arguments:
        colon_number = artifact.count(":")

        if colon_number != 1:
            raise Exception(bad_parameter_error_message.format(artifact))

        name, artifact_path = artifact.split(":", 1)

        if not name:
            raise Exception(bad_parameter_error_message.format(artifact))

        if not artifact_path:
            raise Exception(bad_parameter_error_message.format(artifact))

        logger.info(f"Searching artifact {name} with filter {artifact_path}")

        # Get the list of matching artifacts as we should get only one
        matching_artifacts = load_artifacts(source_task_id, queue, artifact_path)

        # Check that we only got one matching artifact
        if len(matching_artifacts) == 0:
            raise ValueError(f"No artifact found for {artifact_path}")
        elif len(matching_artifacts) > 1:
            raise ValueError(
                f"More than one artifact found for {artifact_path}: {matching_artifacts!r}"
            )

        # Download the artifact to process it later locally
        artifact_task_id, artifact_name = matching_artifacts[0]
        artifact_path = download_artifact(
            queue, artifact_task_id, artifact_name, output_directory
        )

        yield (name, artifact_name, artifact_path)


def zstd_compress(path: str) -> None:
    cctx = zstandard.ZstdCompressor(threads=-1)
    with open(path, "rb") as input_f:
        with open(f"{path}.zst", "wb") as output_f:
            cctx.copy_stream(input_f, output_f)

    os.remove(path)


def zstd_decompress(path: str) -> None:
    dctx = zstandard.ZstdDecompressor()
    with open(f"{path}.zst", "rb") as input_f:
        with open(path, "wb") as output_f:
            dctx.copy_stream(input_f, output_f)

    os.remove(f"{path}.zst")
