# syntax=docker/dockerfile:experimental
FROM python:3.10-alpine

# Add img
RUN apk add --no-cache img --repository=http://dl-cdn.alpinelinux.org/alpine/edge/testing

# Setup other deps
RUN apk add --no-cache git skopeo docker cargo podman cni-plugins fuse-overlayfs \
    && sed -i 's/^#mount_program/mount_program/' /etc/containers/storage.conf

# Define the working directory
WORKDIR taskboot

# Copy taskboot source directory on the image
COPY . /src/taskboot

RUN pip install --no-cache-dir /src/taskboot

CMD ["taskboot", "--help"]
