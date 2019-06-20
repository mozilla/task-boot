import logging
import taskcluster

import requests

from taskboot.config import Configuration
from taskboot.docker import Docker, Skopeo, docker_id_archive
from taskboot.utils import load_artifacts, download_artifact

logger = logging.getLogger(__name__)

HEROKU_REGISTRY = "registry.heroku.com"


def push_artifacts(target, args):
    '''
    Push all artifacts from dependant tasks
    '''
    assert args.task_id is not None, 'Missing task id'

    # Load config from file/secret
    config = Configuration(args)
    assert config.has_docker_auth(), 'Missing Docker authentication'

    if args.push_tool == "skopeo":
        push_tool = Skopeo()
    elif args.push_tool == "docker":
        push_tool = Docker()
    else:
        raise ValueError('Not  supported push tool: {}'.format(args.push_tool))

    push_tool.login(
        config.docker['registry'],
        config.docker['username'],
        config.docker['password'],
    )

    # Load queue service
    queue = taskcluster.Queue(config.get_taskcluster_options())

    # Load dependencies artifacts
    artifacts = load_artifacts(args.task_id, queue, args.artifact_filter, args.exclude_filter)

    for task_id, artifact_name in artifacts:
        push_artifact(queue, push_tool, task_id, artifact_name)

    logger.info('All found artifacts were pushed.')


def push_artifact(queue, push_tool, task_id, artifact_name, custom_tag=None):
    '''
    Download an artifact, reads its tags
    and push it on remote repo
    '''
    path = download_artifact(queue, task_id, artifact_name)
    push_tool.push_archive(path, custom_tag)


def heroku_release(target, args):
    '''
    Push all artifacts from dependant tasks
    '''
    assert args.task_id is not None, 'Missing task id'

    # Load config from file/secret
    config = Configuration(args)

    assert 'username' in config.heroku and 'password' in config.heroku, 'Missing Heroku authentication'

    # Setup skopeo
    skopeo = Skopeo()
    skopeo.login(
        HEROKU_REGISTRY,
        config.heroku['username'],
        config.heroku['password'],
    )

    # Load queue service
    queue = taskcluster.Queue(config.get_taskcluster_options())

    updates_payload = []

    for artifact in args.artifacts:
        heroku_dyno_type, artifact_path = artifact.split(":", 1)
        logger.info("Searching artifact for dyno type %r with filter %r", heroku_dyno_type, artifact_path)

        # Get the list of matching artifacts as we should get only one
        matching_artifacts = load_artifacts(args.task_id, queue, artifact_path)

        # Check that we only got one matching artifact
        if len(matching_artifacts) == 0:
            raise ValueError(f"No artifact found for {artifact_path}")
        elif len(matching_artifacts) > 1:
            raise ValueError(f"More than one artifact found for {artifact_path}: {matching_artifacts!r}")

        # Push the Docker image
        task_id, artifact_name = matching_artifacts[0]

        custom_tag_name = f"{HEROKU_REGISTRY}/{args.heroku_app}/{heroku_dyno_type}"

        artifact_path = download_artifact(queue, task_id, artifact_name)

        skopeo.push_archive(artifact_path, custom_tag_name)

        # Get the Docker image id
        image_id = docker_id_archive(artifact_path)

        updates_payload.append({"type": heroku_dyno_type, "docker_image": image_id})

    # Trigger a release on Heroku
    logger.info("Deploying update for dyno types: %r", list(sorted(x["type"] for x in updates_payload)))

    r = requests.patch(
            f'https://api.heroku.com/apps/{args.heroku_app}/formation',
            json=updates_payload,
            headers={
                'Accept': 'application/vnd.heroku+json; version=3.docker-releases',
                'Authorization': f"Bearer {config.heroku['password']}",
            },
    )
    r.raise_for_status()

    logger.info(f'The {args.heroku_app}/{args.heroku_dyno_type} application has been updated')
