TaskBoot
========

> A Python 3 tool to bootstrap CI/CD workflows in [Taskcluster](https://docs.taskcluster.net) by building and publishing Docker images.

Features
--------

* clone a git repo
* build a docker image in a Taskcluster task without `dind`, by using [podman](https://podman.io/)
* push that docker image to a Docker repo, reading credentials from a Taskcluster secret
* build multiple docker images using a `docker-compose.yml` file
* build/update a Taskcluster hook
* write docker images as Taskcluster artifacts
* use those artifacts in another task to push them (allow for workflows like: build on pull-request and build/push on tag/prod branch)

Demo
----

TaskBoot is used by [bugbug](https://github.com/mozilla/bugbug/) to produce Docker images on pull requests and branch pushes, pushing them only when a tag is created.

Documentation
-------------

A more detailed documentation is available in this [project's wiki](https://github.com/mozilla/task-boot/wiki).
