# syntax=docker/dockerfile:experimental
FROM python:3.7-alpine

# Add img
RUN apk add --no-cache img --repository=http://dl-cdn.alpinelinux.org/alpine/edge/testing

# Setup other deps
RUN apk add --no-cache git skopeo docker cargo

# Define the working directory
WORKDIR taskboot

# Copy taskboot source directory on the image
COPY . /src/taskboot

# Use a dedicated build dir to avoid building in bind mount
RUN mkdir -p /build && \
    pip install --no-cache-dir --build /build /src/taskboot && \
    rm -rf /build

CMD ["taskboot", "--help"]
