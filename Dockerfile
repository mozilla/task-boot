# syntax=docker/dockerfile:experimental
FROM python:3.10-alpine

# Add img
RUN apk add --no-cache img --repository=http://dl-cdn.alpinelinux.org/alpine/edge/testing

# Setup other deps
RUN apk add --no-cache git skopeo docker cargo

# Define the working directory
WORKDIR taskboot

# Copy taskboot source directory on the image
COPY . /src/taskboot

RUN pip install --no-cache-dir /src/taskboot

CMD ["taskboot", "--help"]
