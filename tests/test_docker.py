from taskboot.docker import parse_image_name, patch_dockerfile, read_manifest, write_manifest
import uuid

DOCKERFILE_SIMPLE = '''
FROM project/base:latest
RUN something
CMD ["test"]
'''
DOCKERFILE_STAGES = '''
FROM project/base:latest as build
RUN something

FROM project/another:123
COPY --from=build /src /dest
CMD ["test"]
'''


def test_parse_image_name():
    '''
    Check the Docker image name & tag parser
    '''
    assert parse_image_name('nginx') == ('nginx', 'latest')
    assert parse_image_name('nginx:latest') == ('nginx', 'latest')
    assert parse_image_name('nginx:v1.2.3') == ('nginx', 'v1.2.3')
    assert parse_image_name('anotherImage-complicated:some-thing') == ('anotherImage-complicated', 'some-thing')
    assert parse_image_name('repo/project') == ('repo/project', 'latest')
    assert parse_image_name('repo/project:latest') == ('repo/project', 'latest')
    assert parse_image_name('repo/project:1.2') == ('repo/project', '1.2')
    assert parse_image_name('some/path/to/project') == ('some/path/to/project', 'latest')
    assert parse_image_name('some/path/to/project:abcd') == ('some/path/to/project', 'abcd')
    assert parse_image_name('registry.com/repo/project') == ('registry.com/repo/project', 'latest')


def test_patch_dockerfile(tmpdir):
    '''
    Validate the Dockerfile patch by replacing images names/tags by local images digest
    '''

    def patch(content, images):
        dockerfile = tmpdir.join(str(uuid.uuid4()))
        dockerfile.write(content)
        patch_dockerfile(str(dockerfile), images)
        return dockerfile.read()

    # No modifications when no images are provided
    images = []
    assert patch(DOCKERFILE_SIMPLE, images) == DOCKERFILE_SIMPLE

    # or the images do not match
    images = [
        {'repository': 'another', 'tag': 'latest'}
    ]
    assert patch(DOCKERFILE_SIMPLE, images) == DOCKERFILE_SIMPLE
    images = [
        {'repository': 'project/base', 'tag': 'v123'}
    ]
    assert patch(DOCKERFILE_SIMPLE, images) == DOCKERFILE_SIMPLE

    # Both repository & tag must match
    images = [
        {
            'repository': 'project/base',
            'tag': 'latest',
            'digest': 'deadbeef12345',
            'registry': 'hub.docker.com',
        }
    ]
    assert patch(DOCKERFILE_SIMPLE, images) == '''
FROM hub.docker.com/project/base@sha256:deadbeef12345
RUN something
CMD ["test"]
'''

    # Multi stages images are supported
    images = [
        {
            'repository': 'project/base',
            'tag': 'latest',
            'digest': 'deadbeef12345',
            'registry': 'hub.docker.com',
        },
        {
            'repository': 'project/another',
            'tag': '123',
            'digest': 'coffee67890',
            'registry': 'registry.mozilla.org',
        },
    ]
    assert patch(DOCKERFILE_STAGES, images) == '''
FROM hub.docker.com/project/base@sha256:deadbeef12345 AS build
RUN something

FROM registry.mozilla.org/project/another@sha256:coffee67890
COPY --from=build /src /dest
CMD ["test"]
'''


def test_list_local_images(mock_docker):
    '''
    Validate local images listing from img state
    '''
    assert mock_docker.list_images() == []

    mock_docker.images = [
        ('registry.com/repo/test:latest', '10.9MiB', '1 days ago', '1 days ago', 'sha256:991d19e5156799aa79cf7138b8b843601f180e68f625b892df40a1993b7ac7da')  # noqa
    ]
    assert mock_docker.list_images() == [
        {
            'registry': 'registry.com',
            'repository': 'repo/test',
            'tag': 'latest',
            'size': '10.9MiB',
            'created': '1 days ago',
            'updated': '1 days ago',
            'digest': '991d19e5156799aa79cf7138b8b843601f180e68f625b892df40a1993b7ac7da',
        }
    ]


def test_patch_manifest(hello_archive):
    '''
    Test low level functions to patch a docker image
    '''

    # Read original manifest
    manifest = read_manifest(hello_archive)
    assert manifest == [
        {
            'Config': 'fce289e99eb9bca977dae136fbe2a82b6b7d4c372474c9235adc1741675f587e.json',
            'Layers': ['cdccdf50922d90e847e097347de49119be0f17c18b4a2d98da9919fa5884479d/layer.tar'],
            'RepoTags': ['hello-world:latest']
        }
    ]

    # Update it with different tags
    manifest[0]['RepoTags'] += [
        'another:tag',
        'mozilla/taskboot:test',
    ]
    write_manifest(hello_archive, manifest)

    # Manifest should have changed
    manifest = read_manifest(hello_archive)
    assert manifest == [
        {
            'Config': 'fce289e99eb9bca977dae136fbe2a82b6b7d4c372474c9235adc1741675f587e.json',
            'Layers': ['cdccdf50922d90e847e097347de49119be0f17c18b4a2d98da9919fa5884479d/layer.tar'],
            'RepoTags': [
                'hello-world:latest',
                'another:tag',
                'mozilla/taskboot:test',
            ]
        }
    ]
