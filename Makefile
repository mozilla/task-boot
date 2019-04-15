ROOT_DIR:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
# Using a test repo for now
TAG=babadie/taskboot
VERSION=$(shell cat $(ROOT_DIR)/VERSION)

build:
	img build -t $(TAG):latest -t $(TAG):$(VERSION) $(ROOT_DIR)

publish:
	img push $(TAG):latest
