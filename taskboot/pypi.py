# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import glob
import logging
import os.path

from setuptools._distutils.core import run_setup
from twine.commands.upload import upload as twine_upload
from twine.settings import Settings

from taskboot.config import Configuration

logger = logging.getLogger(__name__)

DEFAULT_REPOSITORY = "https://upload.pypi.org/legacy/"


def publish_pypi(target, args):
    """
    Build and publish the target on a pypi repository
    """
    config = Configuration(args)
    assert config.has_pypi_auth(), "Missing PyPi authentication"

    # Build the project
    setup = target.check_path("setup.py")
    logger.info(f"Building Python project using {setup}")
    run_setup(setup, ["clean", "sdist", "bdist_wheel"])

    # Check some files were produced
    dist = target.check_path("dist")
    build = glob.glob(f"{dist}/*")
    assert len(build) > 0, "No built files found"
    logger.info("Will upload {}".format(", ".join(map(os.path.basename, build))))

    # Use default repository
    repository = args.repository or DEFAULT_REPOSITORY
    logger.info(f"Will upload on {repository}")

    # Upload it through twine
    upload_settings = Settings(
        username=config.pypi["username"],
        password=config.pypi["password"],
        repository_url=repository,
        verbose=True,
        disable_progress_bar=False,
    )
    twine_upload(upload_settings, build)

    logger.info("PyPi publication finished.")
