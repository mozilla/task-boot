# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import os

import taskcluster
import yaml

logger = logging.getLogger(__name__)

TASKCLUSTER_DEFAULT_URL = "https://taskcluster.net"
TASKCLUSTER_DASHBOARD_URL = "https://tools.taskcluster.net"


class Configuration(object):
    config = {}

    def __init__(self, args):
        if args.secret:
            self.load_secret(args.secret)
        elif args.config:
            self.load_config(args.config)
        else:
            logger.warn("No configuration available")

    def __getattr__(self, key):
        if key in self.config:
            return self.config[key]
        raise KeyError

    def get_taskcluster_options(self):
        """
        Helper to get the Taskcluster setup options
        according to current environment (local or Taskcluster)
        """
        options = taskcluster.optionsFromEnvironment()
        proxy_url = os.environ.get("TASKCLUSTER_PROXY_URL")

        if proxy_url is not None:
            # Always use proxy url when available
            options["rootUrl"] = proxy_url

        if "rootUrl" not in options:
            # Always have a value in root url
            options["rootUrl"] = TASKCLUSTER_DEFAULT_URL

        return options

    def load_secret(self, name):
        secrets = taskcluster.Secrets(self.get_taskcluster_options())
        logging.info("Loading Taskcluster secret {}".format(name))
        payload = secrets.get(name)
        assert "secret" in payload, "Missing secret value"
        self.config = payload["secret"]

    def load_config(self, fileobj):
        self.config = yaml.safe_load(fileobj)
        assert isinstance(self.config, dict), "Invalid YAML structure"

    def has_docker_auth(self):
        docker = self.config.get("docker")
        if docker is None:
            return False
        return "registry" in docker and "username" in docker and "password" in docker

    def has_aws_auth(self):
        aws = self.config.get("aws")
        if aws is None:
            return False
        return "access_key_id" in aws and "secret_access_key" in aws

    def has_pypi_auth(self):
        pypi = self.config.get("pypi")
        if pypi is None:
            return False
        return "username" in pypi and "password" in pypi
