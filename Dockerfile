FROM python:3-alpine

# We need docker to build target images
RUN apk add docker

# Add taskboot
COPY dist/task-boot*.tar.gz /tmp/taskboot.tar.gz
RUN tar xvzf /tmp/taskboot.tar.gz
RUN pip install /tmp/taskboot.tar.gz

CMD ["taskboot", "--help"]
