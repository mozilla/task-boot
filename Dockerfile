# syntax=docker/dockerfile:experimental
FROM python:3-alpine

# Add img
RUN apk add img --repository=http://dl-cdn.alpinelinux.org/alpine/edge/testing

# Setup other deps
RUN apk add git

# Install taskboot from mounted source code
RUN --mount=type=bind,target=/src/taskboot,readwrite \
  cd /src/taskboot && python setup.py install

CMD ["taskboot", "--help"]
