FROM python:3-alpine

# Add img
RUN apk add img --repository=http://dl-cdn.alpinelinux.org/alpine/edge/testing

# Setup other deps
RUN apk add git

# Add taskboot
COPY dist/task-boot*.tar.gz /tmp/taskboot.tar.gz
RUN tar xvzf /tmp/taskboot.tar.gz
RUN pip install /tmp/taskboot.tar.gz

CMD ["taskboot", "--help"]
