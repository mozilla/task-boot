# syntax=docker/dockerfile:experimental
FROM python:3.10-alpine

# Setup other deps
RUN apk add --no-cache git skopeo docker cargo podman cni-plugins fuse-overlayfs zstd \
    && sed -i 's/^#mount_program/mount_program/' /etc/containers/storage.conf

# Define the working directory
WORKDIR taskboot

# Copy taskboot source directory on the image
COPY . /src/taskboot

RUN pip install --no-cache-dir /src/taskboot

CMD ["taskboot", "--help"]
