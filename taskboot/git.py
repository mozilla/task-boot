# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import subprocess

from taskboot.config import Configuration

logger = logging.getLogger(__name__)


def git_push(target, args):
    """
    Push commits on a repository
    """

    # Load config from file/secret
    config = Configuration(args)
    assert config.has_github_auth(), "Missing GitHub authentication"

    # Set remote repository
    repo_link = "https://{}:{}@{}.git".format(
        args.user, config.github["token"], args.repository
    )
    subprocess.run(["git", "remote", "set-url", "origin", repo_link])

    # Push on repository
    if args.force_push:
        command = ["git", "push", "-f", "origin", args.branch]
    else:
        command = ["git", "push", "origin", args.branch]

    subprocess.run(command, check=True)
