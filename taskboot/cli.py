import argparse
from taskboot.build import build_image
import logging

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
        help='Taskcluster secret path',
    )
    commands = parser.add_subparsers(help='sub-command help')
    parser.set_defaults(func=usage)

    # Build a docker image
    build = commands.add_parser('build', help='Build a docker image')
    build.add_argument('dockerfile', type=str, help='Path to Dockerfile to build')
    build.add_argument('--write', type=str, help='Path to write the docker image')
    build.add_argument('--push', type=str, help='Path to push on configured repository')
    build.set_defaults(func=build_image)

    # Call the assigned function
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
