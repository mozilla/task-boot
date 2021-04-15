# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import logging
import subprocess

from taskboot.config import Configuration
from taskboot.target import Target

logger = logging.getLogger(__name__)


def cargo_publish(target: Target, args: argparse.Namespace) -> None:
    """
    Publish a crate on crates.io
    """

    # Load config from file/secret
    config = Configuration(args)
    assert config.has_cargo_auth(), "Missing Cargo authentication"

    # Build the package to publish on crates.io
    subprocess.run(["cargo", "publish", "--no-verify", "--dry-run"], check=True)

    # Publish the crate on crates.io
    # stdout and stderr are captured to avoid leaking the token
    proc = subprocess.run(
        ["cargo", "publish", "--no-verify", "--token", config.cargo["token"]],
        capture_output=True,
        text=True,  # Return stdout and stderr output as strings
    )

    # If an error is occurred while publishing the crate
    # Do not fail when a `crate already uploaded` error is found and
    # the option to ignore that kind of error is enabled
    if proc.returncode != 0 and not (
        args.ignore_published and "is already uploaded" in proc.stderr
    ):
        raise Exception("Failed to publish the crate on crates.io")
