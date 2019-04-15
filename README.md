Task Boot
=========

An helper tool to bootstrap Taskcluster usage

Taskcluster + Github
--------------------

1. Create an account or login on [Taskcluster tools](https://tools.taskcluster.net/)
2. Go to the [Github quick-start](https://tools.taskcluster.net/quickstart) page
3. Fill in the form related to your github repository
5. Specify the `payload.image` as `babadie/taskboot:latest`
4. Specify the `payload.command` as 
```
command:
	- taskboot
	- build
	- path/to/Dockerfile
```
5. Copy the produced YAML code and commit it in your repository as `.taskcluster.yml`
6. Acticate the [Taskcluster Github addon](https://github.com/apps/taskcluster) on your repository

Roles
-----

We recommend creating one role per functionality. If you want to build docker images in some steps, and push or dpeloy them in other steps (or maybe on some specific tags or branches), you might create 2 distinct roles as below.

TODO: explain the worker type needs and how to get them

Build role scopes:

* `docker-worker:capability:privileged` : needed to run the container in privileged mode to allow Docker builds
* `queue:create-task:aws-provisioner-v1/<WORKER_TYPE>` : needed to create a task in the privileged worker type

Deploy role scopes:

* `secrets:get:path/to/your/secret` : needed to read a secret you manage, and where you store Docker registry credentials

Now you need to assign (or `assume` in Taskcluster linguo) those new roles to the roles used by the Taskcluster Github application:

* `repo:github.com/<GROUP>/<PROJECT>:pull-request` is used when a pull request is created. Generally you only want the build role here
* `repo:github.com/<GROUP>/<PROJECT>:branch:*` is used when pushing to any branch. You can specify a branch instead of wildcard too.
* `repo:github.com/<GROUP>/<PROJECT>:tag:*` is used when a tag is created, generally for new releases. You might want to use build & deploy scopes here.
