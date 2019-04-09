import logging
import tempfile
import subprocess
import os

logger = logging.getLogger(__name__)


class Target(object):
    '''
    A target repository
    '''
    def __init__(self, args):

        # Setup workspace in a tempdir
        if args.target:
            self.dir = os.path.realpath(args.target)
        else:
            self.dir = tempfile.mkdtemp(prefix='taskboot.')
        assert os.path.isdir(self.dir), 'Invalid target {}'.format(self.dir)
        logging.info('Target setup in {}'.format(self.dir))

        # Use git target
        if args.git_repository:
            self.clone(args.git_repository, args.git_revision)
        else:
            logger.warn('No target cloned')

    def clone(self, repository, revision):
        assert repository.startswith('git://'), \
            'Git repository must start with git:// scheme'
        logger.info('Cloning {} @ {}'.format(repository, revision))

        # Clone
        cmd = [
            'git', 'clone',
            repository,
            self.dir,
        ]
        subprocess.check_output(cmd)
        logger.info('Cloned into {}'.format(self.dir))

        # Checkout revision to pull modifications
        cmd = [
            'git', 'checkout', revision,
            '-b', 'taskboot',
        ]
        subprocess.check_output(cmd, cwd=self.dir)
        logger.info('Checked out revision {}'.format(revision))

    def check_path(self, path):
        '''
        Check a path exists in target
        '''
        assert not path.startswith('/'), 'No absolute paths'
        full_path = os.path.join(self.dir, path)
        assert os.path.exists(full_path), 'Missing file in target {}'.format(path)
        return full_path
