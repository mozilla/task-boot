FROM python:3-alpine

# Setup deps
RUN apk add git

# Add taskboot
COPY dist/task-boot*.tar.gz /tmp/taskboot.tar.gz
RUN tar xvzf /tmp/taskboot.tar.gz
RUN pip install /tmp/taskboot.tar.gz

CMD ["taskboot", "--help"]
