import docker
import os.path
from taskboot.config import Configuration
import logging

logger = logging.getLogger(__name__)

# Docker version available on Taskcluster is pretty old
DOCKER_MIN_VERSION = '1.18'


def build_image(target, args):
    '''
    Build a docker image and allow save/push
    '''
    # Load config from file/secret
    config = Configuration(args)

    # Check the dockerfile is available in target
    dockerfile = target.check_path(args.dockerfile)

    # Check the output is writable
    output = os.path.realpath(args.write) if args.write else None
    if output:
        assert os.access(os.path.dirname(output), os.W_OK | os.W_OK), \
            'Destination is not writable'
        assert output.lower().endswith('.tar'), 'Destination path must ends in .tar'

    # Check we have docker auth
    if args.push:
        assert config.has_docker_auth(), 'Missing Docker authentication'

    # Setup docker client
    client = docker.from_env(version=DOCKER_MIN_VERSION)
    assert client.ping(), 'Docker ping failed'

    # Build the image
    logger.info('Building docker image {}'.format(dockerfile))
    image = client.images.build(
        path=target.dir,
        dockerfile=dockerfile,
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
        client.images.push(
            repository=config.docker['repository'],
            tag=args.push,
            auth_config={
                'username': config.docker['username'],
                'password': config.docker['password'],
            }
        )
        logger.info('Pushed image to {}'.format(args.push))
