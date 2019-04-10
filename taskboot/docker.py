import subprocess
import logging

logger = logging.getLogger(__name__)


class Docker(object):
    '''
    Interface to the img tool, replacing docker daemon
    '''
    def __init__(self):
        # TODO: check img is available
        pass

    def login(self, registry, username, password):
        '''
        Login on remote registry
        '''
        cmd = [
            'login',
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
            '--output', path,
            tag,
        ])

    def push(self, tag):
        logger.info('Pushing image {}'.format(tag))
        self.run(['push', tag])

    def run(self, command, **params):
        out = subprocess.run(['img'] + command, **params)
        assert out.returncode == 0, 'Build failure'
        return out
