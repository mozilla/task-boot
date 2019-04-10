ROOT_DIR:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
TAG=mozilla/taskboot
VERSION=$(shell cat $(ROOT_DIR)/VERSION)

build: clean
	python setup.py sdist
	docker build $(ROOT_DIR) -t $(TAG):latest -t $(TAG):$(VERSION)

publish:
	# Using a test repo for now
	docker tag $(TAG):latest babadie/taskboot:latest
	docker push babadie/taskboot:latest

clean:
	rm -rf $(ROOT_DIR)/*.egg-info $(ROOT_DIR)/dist
