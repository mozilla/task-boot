# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from taskboot.target import Target
import os


class Config(object):
    target = None
    git_repository = None


def test_path():
    """
    Test a path exists in a target
    """
    conf = Config()
    target = Target(conf)

    assert os.path.isdir(target.dir)

    with open(os.path.join(target.dir, "test.txt"), "w") as f:
        f.write("Test")

    path = target.check_path("test.txt")
    assert os.path.exists(path)
    assert path.startswith(target.dir)
