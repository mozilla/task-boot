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
    subprocess.run(["cargo", "publish", "--dry-run"], check=True)

    # Publish the crate on crates.io
    # stdout and stderr are captured to avoid leaking the token
    proc = subprocess.run(
        ["cargo", "publish", "--token", config.cargo["token"]], capture_output=True,
    )

    if proc.returncode != 0:
        raise Exception("Failed to publish the crate on crates.io")
