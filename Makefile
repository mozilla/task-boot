ROOT_DIR:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
TAG=mozilla/taskboot
VERSION=$(shell cat $(ROOT_DIR)/VERSION)

build:
	podman build -t $(TAG):latest -t $(TAG):$(VERSION) $(ROOT_DIR)

publish:
	podman push $(TAG):latest
