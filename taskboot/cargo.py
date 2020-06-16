# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import subprocess

from taskboot.config import Configuration

logger = logging.getLogger(__name__)


def cargo_publish(target, args):
    """
    Publish a crate on crates.io
    """

    # Load config from file/secret
    config = Configuration(args)
    assert config.has_cargo_auth(), "Missing Cargo authentication"

    # Check if the crate to be published contains some errors
    subprocess.run(["cargo", "publish", "--dry-run"])

    # Publish the crate on crates.io
    error = subprocess.run(
        ["cargo", "publish", "--token", config.cargo["token"]], capture_output=True
    )

    if error.returncode != 0:
        raise Exception(f"Failed to publish the crate")
