FROM python:3-alpine

# We need git & docker to build target images
RUN apk add docker git

# Add taskboot
COPY dist/task-boot*.tar.gz /tmp/taskboot.tar.gz
RUN tar xvzf /tmp/taskboot.tar.gz
RUN pip install /tmp/taskboot.tar.gz

CMD ["taskboot", "--help"]
