import uuid
import os.path
import yaml
import json
import taskcluster
from taskboot.config import Configuration, TASKCLUSTER_DASHBOARD_URL
from taskboot.docker import Docker, patch_dockerfile
from taskboot.utils import retry
import logging

logger = logging.getLogger(__name__)


def build_image(target, args):
    '''
    Build a docker image and allow save/push
    '''
    docker = Docker(cache=args.cache)

    # Load config from file/secret
    config = Configuration(args)

    # Check the dockerfile is available in target
    dockerfile = target.check_path(args.dockerfile)

    # Check the output is writable
    output = None
    if args.write:
        output = os.path.realpath(args.write)
        assert output.lower().endswith('.tar'), 'Destination path must ends in .tar'
        assert os.access(os.path.dirname(output), os.W_OK | os.W_OK), \
            'Destination is not writable'

    # Build the tag
    tag = args.tag or 'taskboot-{}'.format(uuid.uuid4())
    # TODO: check tag is valid

    if args.push:
        assert config.has_docker_auth(), 'Missing Docker authentication'
        registry = config.docker['registry']
        if not tag.startswith(registry):
            tag = '{}/{}'.format(registry, tag)

        # Login on docker
        docker.login(
            registry,
            config.docker['username'],
            config.docker['password'],
        )

    logger.info('Will produce image {}'.format(tag))

    # Build the image
    docker.build(target.dir, dockerfile, tag, [])

    # Write the produced image
    if output:
        docker.save(tag, output)

    # Push the produced image
    if args.push:
        docker.push(tag)


def build_compose(target, args):
    '''
    Read a compose file and build each image described as buildable
    '''
    assert args.build_retries > 0, 'Build retries must be a positive integer'
    docker = Docker(cache=args.cache)

    # Check the dockerfile is available in target
    composefile = target.check_path(args.composefile)

    # Check compose file has version >= 3.0
    compose = yaml.load(open(composefile))
    version = compose.get('version')
    assert version is not None, 'Missing version in {}'.format(composefile)
    assert compose['version'].startswith('3.'), \
        'Only docker compose version 3 is supported'

    # Check output folder
    output = None
    if args.write:
        output = os.path.realpath(args.write)
        os.makedirs(output, exist_ok=True)
        logger.info('Will write images in {}'.format(output))

    # Load services
    services = compose.get('services')
    assert isinstance(services, dict), 'Missing services'

    # All paths are relative to the dockerfile folder
    root = os.path.dirname(composefile)

    for name, service in services.items():
        build = service.get('build')
        if build is None:
            logger.info('Skipping service {}, no build declaration'.format(name))
            continue

        # Build the image
        logger.info('Building image for service {}'.format(name))
        context = os.path.realpath(os.path.join(root, build.get('context', '.')))
        dockerfile = os.path.realpath(os.path.join(context, build.get('dockerfile', 'Dockerfile')))

        # We need to replace the FROM statements by their local versions
        # to avoid using the remote repository first
        patch_dockerfile(dockerfile, docker.list_images())

        tag = service.get('image', name)
        if args.registry:
            tag = '{}/{}'.format(args.registry, tag)
        retry(
            lambda: docker.build(context, dockerfile, tag, args.build_arg),
            wait_between_retries=1,
            retries=args.build_retries,
        )

        # Write the produced image
        if output:
            docker.save(tag, os.path.join(output, '{}.tar'.format(name)))

    logger.info('Compose file fully processed.')


def build_hook(target, args):
    '''
    Read a hook definition file and either create or update the hook
    '''
    hook_file_path = target.check_path(args.hook_file)

    hook_group_id = args.hook_group_id
    hook_id = args.hook_id

    with open(hook_file_path) as hook_file:
        payload = json.load(hook_file)

    # Load config from file/secret
    config = Configuration(args)

    hooks = taskcluster.Hooks(config.get_taskcluster_options())
    hooks.ping()

    hook_name = "{}/{}".format(hook_group_id, hook_id)
    logger.info("Checking if hook %s exists", hook_name)

    try:
        hooks.hook(hook_group_id, hook_id)
        hook_exists = True
        logger.info("Hook %s exists", hook_name)
    except taskcluster.exceptions.TaskclusterRestFailure:
        hook_exists = False
        logger.info("Hook %s does not exists", hook_name)

    if hook_exists:
        hooks.updateHook(hook_group_id, hook_id, payload)
        logger.info("Hook %s was successfully updated", hook_name)
    else:
        hooks.createHook(hook_group_id, hook_id, payload)
        logger.info("Hook %s was successfully created", hook_name)

    hook_url = "{}/hooks/{}/{}".format(TASKCLUSTER_DASHBOARD_URL, hook_group_id, hook_id)
    logger.info("Hook URL for debugging: %r", hook_url)
