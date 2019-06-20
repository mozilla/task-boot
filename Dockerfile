# syntax=docker/dockerfile:experimental
FROM python:3-alpine

ARG BUILD_DIR=/build

# Add img
RUN apk add img --repository=http://dl-cdn.alpinelinux.org/alpine/edge/testing

# Setup other deps
RUN apk add git skopeo docker

# Install taskboot from mounted source code
# Use a dedicated build dir to avoid building in bind mount
RUN --mount=type=bind,target=/src/taskboot \
  cd /src/taskboot && \
  mkdir -p ${BUILD_DIR} && \
  pip install --no-cache-dir --build ${BUILD_DIR} . && \
  rm -rf ${BUILD_DIR}

CMD ["taskboot", "--help"]
