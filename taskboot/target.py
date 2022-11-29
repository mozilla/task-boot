# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import os
import subprocess
import tempfile

logger = logging.getLogger(__name__)


class Target(object):
    """
    A target repository
    """

    def __init__(self, args):

        # Setup workspace in a tempdir
        if args.target:
            self.dir = os.path.realpath(args.target)
        else:
            self.dir = tempfile.mkdtemp(prefix="taskboot.")
        assert os.path.isdir(self.dir), "Invalid target {}".format(self.dir)
        logging.info("Target setup in {}".format(self.dir))

        # Use git target
        if args.git_repository:
            self.clone(args.git_repository, args.git_revision)
        else:
            logger.warn("No target cloned")

    def clone(self, repository, revision):
        logger.info("Cloning {} @ {}".format(repository, revision))

        # Clone
        cmd = ["git", "clone", "--quiet", repository, self.dir]
        subprocess.check_output(cmd)
        logger.info("Cloned into {}".format(self.dir))

        # Explicitly fetch revision if it isn't present
        # This is necessary when revision is from a fork
        # and repository is the base repo.
        if (
            subprocess.run(
                ["git", "show", revision],
                cwd=self.dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            != 0
        ):
            cmd = ["git", "fetch", "--quiet", "origin", revision]
            subprocess.check_output(cmd, cwd=self.dir)

        # Checkout revision to pull modifications
        cmd = ["git", "checkout", revision, "-b", "taskboot"]
        subprocess.check_output(cmd, cwd=self.dir)
        logger.info("Checked out revision {}".format(revision))

    def check_path(self, path):
        """
        Check a path exists in target
        """
        assert not path.startswith("/"), "No absolute paths"
        full_path = os.path.join(self.dir, path)
        assert os.path.exists(full_path), "Missing file in target {}".format(path)
        return full_path
