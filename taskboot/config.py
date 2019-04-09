import logging
import yaml

logger = logging.getLogger(__name__)


class Configuration(object):
    config = {}

    def __init__(self, args):
        if args.secret:
            self.load_secret(args.secret)
        elif args.config:
            self.load_config(args.config)
        else:
            logger.warn('No configuration available')

    def __getattr__(self, key):
        if key in self.config:
            return self.config[key]
        raise KeyError

    def load_secret(self, name):
        raise NotImplementedError('TODO: read secret {}'.format(name))

    def load_config(self, fileobj):
        self.config = yaml.safe_load(fileobj)
        assert isinstance(self.config, dict), 'Invalid YAML structure'

    def has_docker_auth(self):
        docker = self.config.get('docker')
        if docker is None:
            return False
        return 'repository' in docker \
               and 'username' in docker \
               and 'password' in docker
