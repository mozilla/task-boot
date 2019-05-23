from dockerfile_parse import DockerfileParser
import subprocess
import shutil
import tempfile
import logging
import os
import base64
import tarfile
import re
import json


logger = logging.getLogger(__name__)

# docker.io/mozilla/taskboot:latest  172.3MiB  25 hours ago  About an hour ago  sha256:e339e39884d2a6f44b493e8f135e5275d0e47209b3f990b768228534944db6e7  # noqa
IMG_LS_REGEX = re.compile(r'([\w\.]+)/(([\w\-_\.]+)/([\w\-_\.]+)):([\w\-_\.]+)\t+([\.\w]+)\t+([\w ]+)\t+([\w ]+)\t+sha256:(\w{64})')  # noqa

IMG_NAME_REGEX = re.compile(r'(?P<name>[\/\w\-\._]+):?(?P<tag>\S*)')


class Tool(object):
    '''
    Common interface for tools available in shell
    '''
    def __init__(self, binary):
        # Check the tool is available on the system
        self.binary = shutil.which(binary)
        assert self.binary is not None, 'Binary {} not found in PATH'.format(binary)

    def run(self, command, **params):
        command = [self.binary] + command
        return subprocess.run(command, check=True, **params)


class Docker(Tool):
    '''
    Interface to the img tool, replacing docker daemon
    '''
    def __init__(self, cache=None):
        super().__init__('img')

        # Setup img state, using or creating a cache folder
        if cache is not None:
            self.state = os.path.join(os.path.realpath(cache), 'img')
            os.makedirs(self.state, exist_ok=True)
        else:
            self.state = tempfile.mkdtemp('-img')
        logger.info('Docker state is using {}'.format(self.state))

    def login(self, registry, username, password):
        '''
        Login on remote registry
        '''
        cmd = [
            'login',
            '--state', self.state,
            '--password-stdin',
            '-u', username,
            registry,
        ]
        self.run(cmd, input=password.encode('utf-8'))
        logger.info('Authenticated on {} as {}'.format(registry, username))

    def list_images(self):
        '''
        List images stored in current state
        Parses the text output into usable dicts
        '''
        ls = self.run(['ls', '--state', self.state], stdout=subprocess.PIPE)
        out = []
        for line in ls.stdout.splitlines()[1:]:
            image = IMG_LS_REGEX.search(line.decode('utf-8'))
            if image is not None:
                out.append({
                    'registry': image.group(1),
                    'repository': image.group(2),
                    'tag': image.group(5),
                    'size': image.group(6),
                    'created': image.group(7),
                    'updated': image.group(8),
                    'digest': image.group(9),
                })
            else:
                logger.warn('Did not parse this image: {}'.format(line))
        return out

    def build(self, context_dir, dockerfile, tags, build_args=[]):
        logger.info('Building docker image {}'.format(dockerfile))

        command = [
            'build',
            '--state', self.state,
            '--no-console',
            '--file', dockerfile,
        ]

        for add_tag in tags:
            command += ["--tag", add_tag]

        # We need to "de-parse" the build args
        for single_build_arg in build_args:
            command += ['--build-arg', single_build_arg]

        command.append(context_dir)

        logger.info('Running img command: {}'.format(command))

        self.run(command)
        logger.info('Built image {}'.format(", ".join(tags)))

    def save(self, tag, path):
        logger.info('Saving image {} to {}'.format(tag, path))
        self.run([
            'save',
            '--state', self.state,
            '--output', path,
            tag,
        ])

    def push(self, tag):
        logger.info('Pushing image {}'.format(tag))
        self.run([
            'push',
            '--state', self.state,
            tag,
        ])


class Skopeo(Tool):
    '''
    Interface to the skopeo tool, used to copy local images to remote repositories
    '''
    def __init__(self, registry, username, password):
        super().__init__('skopeo')

        # Setup the authentication
        _, self.auth_file = tempfile.mkstemp(suffix='-skopeo.json')
        pair = '{}:{}'.format(username, password).encode('utf-8')
        server = 'https://{}/v1'.format(registry)
        self.registry = registry
        auth = {
            'auths': {
                server: {
                    'auth': base64.b64encode(pair).decode('utf-8')
                }
            }
        }
        with open(self.auth_file, 'w') as f:
            json.dump(auth, f)

    def push_archive(self, path):
        '''
        Push a local tar OCI archive on the remote repo from config
        The tags used on the image are all used to push
        '''
        assert os.path.exists(path), 'Missing archive {}'.format(path)
        assert tarfile.is_tarfile(path), 'Not a TAR archive {}'.format(path)

        # Open the manifest from downloaded archive
        tar = tarfile.open(path)
        manifest_raw = tar.extractfile('manifest.json')
        manifest = json.loads(manifest_raw.read().decode('utf-8'))
        tags = manifest[0]['RepoTags']
        assert len(tags) > 0, 'No tags found'

        for tag in tags:
            # Check the registry is in the tag
            assert tag.startswith(self.registry), \
                'Invalid tag {} : must use registry {}'.format(tag, self.registry)

            logger.info('Pushing image as {}'.format(tag))
            cmd = [
                'copy',
                '--authfile', self.auth_file,
                'oci-archive:{}'.format(path),
                'docker://{}'.format(tag),
            ]
            self.run(cmd)
            logger.info('Push successfull')


def parse_image_name(image_name):
    '''
    Helper to convert a Docker image name
    into a tuple (name, tag)
    Supports formats :
    * nginx
    * library/nginx
    * nginx:latest
    * myrepo/nginx:v123
    '''
    match = IMG_NAME_REGEX.match(image_name)
    if match is None:
        return (None, None)
    return (match.group('name'), match.group('tag') or 'latest')


def patch_dockerfile(dockerfile, images):
    '''
    Patch an existing Dockerfile to replace FROM image statements
    by their local images with digests. It supports multi-stage images
    This is needed to avoid retrieving remote images before checking current img state
    Bug https://github.com/genuinetools/img/issues/206
    '''
    assert os.path.exists(dockerfile), 'Missing dockerfile {}'.format(dockerfile)
    assert isinstance(images, list)
    if not images:
        return

    def _find_replacement(original):
        # Replace an image name by its local version
        # when it exists
        repo, tag = parse_image_name(original)
        for image in images:
            if image['repository'] == repo and image['tag'] == tag:
                local = '{}/{}@sha256:{}'.format(image['registry'], image['repository'], image['digest'])
                logger.info('Replacing image {} by {}'.format(original, local))
                return local

        return original

    # Parse the given dockerfile and update its parent images
    # with local version given by current img state
    # The FROM statement parsing & replacement is provided
    # by the DockerfileParser
    parser = DockerfileParser()
    parser.dockerfile_path = dockerfile
    parser.content = open(dockerfile).read()
    logger.info('Initial parent images: {}'.format(' & '.join(parser.parent_images)))
    parser.parent_images = list(map(_find_replacement, parser.parent_images))
