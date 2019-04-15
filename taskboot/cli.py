import argparse
from taskboot.build import build_image, build_compose
from taskboot.target import Target
import logging
import os

logging.basicConfig(level=logging.INFO)


def usage(args):
    print('Here is how to use taskboot...')


def main():
    parser = argparse.ArgumentParser(prog='taskboot')
    parser.add_argument(
        '--config',
        type=open,
        help='Path to local condfiguration/secrets file',
    )
    parser.add_argument(
        '--secret',
        type=str,
        default=os.environ.get('TASKCLUSTER_SECRET'),
        help='Taskcluster secret path',
    )
    parser.add_argument(
        '--git-repository',
        type=str,
        default=os.environ.get('GIT_REPOSITORY'),
        help='Target git repository',
    )
    parser.add_argument(
        '--git-revision',
        type=str,
        default=os.environ.get('GIT_REVISION', 'master'),
        help='Target git revision',
    )
    parser.add_argument(
        '--target',
        type=str,
        help='Target directory to use a local project',
    )
    commands = parser.add_subparsers(help='sub-command help')
    parser.set_defaults(func=usage)

    # Build a docker image
    build = commands.add_parser('build', help='Build a docker image')
    build.add_argument('dockerfile', type=str, help='Path to Dockerfile to build')
    build.add_argument('--write', type=str, help='Path to write the docker image')
    build.add_argument('--push', type=str, help='Path to push on configured repository')
    build.add_argument('--tag', type=str, help='Use a specific tag on this image')
    build.set_defaults(func=build_image)

    # Build images from a docker-compose.yml file
    compose = commands.add_parser('build-compose', help='Build images from a docker-compose flie')
    compose.add_argument(
        '--compose-file', '-c',
        dest='composefile',
        type=str,
        help='Path to docker-compose.yml to use',
        default='docker-compose.yml',
    )
    compose.add_argument('--write', type=str, help='Directory to write the docker images')
    compose.set_defaults(func=build_compose)

    # Always load the target
    args = parser.parse_args()
    target = Target(args)

    # Call the assigned function
    args.func(target, args)


if __name__ == '__main__':
    main()
