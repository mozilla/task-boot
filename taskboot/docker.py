import subprocess
import shutil
import tempfile
import logging
import os
import base64
import tarfile
import json


logger = logging.getLogger(__name__)


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

    def build(self, context_dir, dockerfile, tag):
        logger.info('Building docker image {}'.format(dockerfile))
        self.run([
            'build',
            '--state', self.state,
            '--no-console',
            '--tag', tag,
            '--file', dockerfile,
            context_dir,
        ])
        logger.info('Built image {}'.format(tag))

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
