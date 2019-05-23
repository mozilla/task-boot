import logging
import taskcluster
import tempfile
from fnmatch import fnmatch

import requests

from taskboot.config import Configuration
from taskboot.docker import Skopeo, docker_id_archive
from taskboot.utils import download_progress, retry

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

    # Setup skopeo
    skopeo = Skopeo(
        config.docker['registry'],
        config.docker['username'],
        config.docker['password'],
    )

    # Load queue service
    queue = taskcluster.Queue(config.get_taskcluster_options())

    # Load current task description to list its dependencies
    logger.info('Loading task status {}'.format(args.task_id))
    task = queue.task(args.task_id)
    nb_deps = len(task['dependencies'])
    assert nb_deps > 0, 'No task dependencies'

    # Load dependencies artifacts
    artifacts = load_artifacts(task, queue, args.artifact_filter, args.exclude_filter)

    for task_id, artifact_name in artifacts:
        push_artifact(queue, skopeo, task_id, artifact_name)

    logger.info('All found artifacts were pushed.')


def download_artifact(queue, task_id, artifact_name):
    logger.info('Download {} from {}'.format(artifact_name, task_id))

    # Build artifact url
    try:
        url = queue.buildSignedUrl('getLatestArtifact', task_id, artifact_name)
    except taskcluster.exceptions.TaskclusterAuthFailure:
        url = queue.buildUrl('getLatestArtifact', task_id, artifact_name)

    # Download the artifact in a temporary file
    _, path = tempfile.mkstemp(suffix='-taskboot.tar')
    retry(lambda: download_progress(url, path))

    return path


def push_artifact(queue, skopeo, task_id, artifact_name, custom_tag=None):
    '''
    Download an artifact, reads its tags
    and push it on remote repo
    '''
    path = download_artifact(queue, task_id, artifact_name)

    # Push image using skopeo
    skopeo.push_archive(path, custom_tag)


def heroku_release(target, args):
    '''
    Push all artifacts from dependant tasks
    '''
    assert args.task_id is not None, 'Missing task id'

    # Load config from file/secret
    config = Configuration(args)

    assert 'username' in config.heroku and 'password' in config.heroku, 'Missing Heroku authentication'

    # Setup skopeo
    skopeo = Skopeo(
        HEROKU_REGISTRY,
        config.heroku['username'],
        config.heroku['password'],
    )

    # Load queue service
    queue = taskcluster.Queue(config.get_taskcluster_options())

    # Load current task description to list its dependencies
    logger.info('Loading task status {}'.format(args.task_id))
    task = queue.task(args.task_id)
    nb_deps = len(task['dependencies'])
    assert nb_deps > 0, 'No task dependencies'

    # Get the list of matching artifacts as we should get only one
    matching_artifacts = load_artifacts(task, queue, args.artifact_filter, args.exclude_filter)

    # Push the Docker image
    if len(matching_artifacts) == 0:
        raise ValueError(f"No artifact found for {args.artifact_filter}")
    elif len(matching_artifacts) > 1:
        raise ValueError(f"More than one artifact found for {args.artifact_filter}: {matching_artifacts!r}")
    else:
        task_id, artifact_name = matching_artifacts[0]

        custom_tag_name = f"{HEROKU_REGISTRY}/{args.heroku_app}/{args.heroku_dyno_type}"

        artifact_path = download_artifact(queue, task_id, artifact_name)

        skopeo.push_archive(artifact_path, custom_tag_name)

    # Get the Docker image id
    image_id = docker_id_archive(artifact_path)

    # Trigger a release on Heroku
    logger.info(f"Deploying image id {image_id!r} to Heroku app {args.heroku_app!r} dyno {args.heroku_dyno_type!r}")
    update = dict(
        type=args.heroku_dyno_type,
        docker_image=image_id,
    )
    r = requests.patch(
            f'https://api.heroku.com/apps/{args.heroku_app}/formation',
            json=dict(updates=[update]),
            headers={
                'Accept': 'application/vnd.heroku+json; version=3.docker-releases',
                'Authorization': f"Bearer {config.heroku['password']}",
            },
    )
    r.raise_for_status()

    logger.info(f'The {args.heroku_app}/{args.heroku_dyno_type} application has been updated')


def load_artifacts(task, queue, artifact_filter, exclude_filter=None):
    # Get the list of matching artifacts as we should get only one
    matching_artifacts = []

    # Load dependencies artifacts
    for i, task_id in enumerate(task['dependencies']):
        logger.info('Loading task dependencies {}/{} {}'.format(i+1, len(task['dependencies']), task_id))
        task_artifacts = queue.listLatestArtifacts(task_id)

        # Only process the filtered artifacts
        for artifact in task_artifacts['artifacts']:
            artifact_name = artifact['name']
            if fnmatch(artifact_name, artifact_filter):

                if exclude_filter and fnmatch(artifact_name, exclude_filter):
                    logger.info('Excluding artifact %s because of exclude filter', artifact_name)
                    continue

                matching_artifacts.append((task_id, artifact_name))

    return matching_artifacts
