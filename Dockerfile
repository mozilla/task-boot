# syntax=docker/dockerfile:experimental
FROM python:3.7-alpine

ARG BUILD_DIR=/build
ARG MOUNT_SOURCE_CODE=/src/taskboot

# Add img
RUN apk add --no-cache img --repository=http://dl-cdn.alpinelinux.org/alpine/edge/testing

# Setup other deps
RUN apk add --no-cache git skopeo docker

# Use a dedicated build dir to avoid building in bind mount
RUN mkdir -p ${BUILD_DIR}

# Define the working directory
WORKDIR taskboot

# Install taskboot from mounted source code
RUN mkdir -p ${MOUNT_SOURCE_CODE}
COPY . ${MOUNT_SOURCE_CODE}

RUN cd ${MOUNT_SOURCE_CODE} && \
    pip install --no-cache-dir --build ${BUILD_DIR} . && \
    rm -rf ${BUILD_DIR}

CMD ["taskboot", "--help"]
