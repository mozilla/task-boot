import docker
import os.path
from taskboot.config import Configuration
import logging

logger = logging.getLogger(__name__)


def build_image(args):
    '''
    Build a docker image and allow save/push
    '''
    # Load config from file/secret
    config = Configuration(args)

    # Check the dockerfile is available
    dockerfile = os.path.realpath(args.dockerfile)
    assert os.path.exists(dockerfile), 'Missing Dockerfile in {}'.format(dockerfile)

    # Check the output is writable
    output = os.path.realpath(args.write) if args.write else None
    if output:
        assert os.access(os.path.dirname(output), os.W_OK | os.W_OK), \
            'Destination is not writable'
        assert output.lower().endswith('.tar'), 'Destination path must ends in .tar'

    # Check we have docker auth
    if args.push:
        assert config.has_docker_auth(), 'Missing Docker authentication'

    client = docker.from_env()
    client.ping()

    # Build the image
    image, logs = client.images.build(
        fileobj=open(dockerfile, 'rb'),
        tag='{}:{}'.format(config.docker['repository'], args.push) if args.push else '',
    )
    logger.info('Built image {}'.format(image.id))

    # Write the produced image
    if output is not None:
        with open(output, 'wb') as f:
            for chunk in image.save():
                f.write(chunk)
        logger.info('Saved image in {}'.format(output))

    # Push the produced image
    if args.push:
        out = client.images.push(
            repository=config.docker['repository'],
            tag=args.push,
            auth_config={
                'username': config.docker['username'],
                'password': config.docker['password'],
            }
        )
        logger.info(out)
        logger.info('Pushed image to {}'.format(args.push))
