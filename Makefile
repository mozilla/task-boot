ROOT_DIR:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
TAG=mozilla/taskboot
VERSION=$(shell cat $(ROOT_DIR)/VERSION)

build:
	img build -t $(TAG):latest -t $(TAG):$(VERSION) $(ROOT_DIR)

taskcluster-build:
	# Used by Taskcluster build
	img build --no-console -t $(TAG):latest $(ROOT_DIR)
	img save --format oci -o /image.tar $(TAG):latest
	mkdir image
	echo '{}' > image/repositories
	tar -rvf /image.tar image/repositories
	zstd /image.tar

publish:
	# Using a test repo for now
	img tag $(TAG):latest babadie/taskboot:latest
	img push babadie/taskboot:latest
