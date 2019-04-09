ROOT_DIR:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
TAG=mozilla/taskboot
VERSION=$(shell cat $(ROOT_DIR)/VERSION)

build: clean
	python setup.py sdist
	docker build $(ROOT_DIR) -t $(TAG):latest -t $(TAG):$(VERSION)

clean:
	rm -rf $(ROOT_DIR)/*.egg-info $(ROOT_DIR)/dist
