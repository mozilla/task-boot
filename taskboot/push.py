import logging
import taskcluster
import tempfile
from fnmatch import fnmatch
from taskboot.config import Configuration
from taskboot.docker import Skopeo
from taskboot.utils import download_progress

logger = logging.getLogger(__name__)


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
    for i, task_id in enumerate(task['dependencies']):
        logger.info('Loading task dependencies {}/{} {}'.format(i+1, nb_deps, task_id))
        task_artifacts = queue.listLatestArtifacts(task_id)

        # Only process the filtered artifacts
        for artifact in task_artifacts['artifacts']:
            if fnmatch(artifact['name'], args.artifact_filter):
                push_artifact(queue, skopeo, task_id, artifact['name'])

    logger.info('All found artifacts were pushed.')


def push_artifact(queue, skopeo, task_id, artifact_name):
    '''
    Download an artifact, reads its tags
    and push it on remote repo
    '''
    logger.info('Download {} from {}'.format(artifact_name, task_id))

    # Build artifact url
    try:
        url = queue.buildSignedUrl('getLatestArtifact', task_id, artifact_name)
    except taskcluster.exceptions.TaskclusterAuthFailure:
        url = queue.buildUrl('getLatestArtifact', task_id, artifact_name)

    # Download the artifact in a temporary file
    _, path = tempfile.mkstemp(suffix='-taskboot.tar')
    download_progress(url, path)

    # Push image using skopeo
    skopeo.push_archive(path)
