# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging

from taskboot.config import Configuration
from taskboot.utils import load_named_artifacts

logger = logging.getLogger(__name__)


def retrieve_artifacts(target, args):
    """
    Retrieve all artifacts from a task
    """
    assert args.task_id is not None, "Missing task id"

    # Load config from file/secret
    config = Configuration(args)

    # Load dependencies artifacts
    for _, artifact_name, artifact_path in load_named_artifacts(
        config, args.task_id, args.artifacts, args.output_path
    ):
        logger.info(f"{artifact_name} has been downloaded to {artifact_path}")

    logger.info("All found artifacts were downloaded.")
