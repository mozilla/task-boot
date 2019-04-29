import pytest
import subprocess
from taskboot.docker import Docker


@pytest.fixture
def mock_docker(tmpdir):
    '''
    Mock the Docker tool class (img) with a fake state
    '''
    class MockDocker(Docker):
        def __init__(self):
            self.state = None
            self.images = []

        def run(self, command, **kwargs):
            # Fake img calls
            if command[0] == 'ls':
                # Fake image listing
                output = 'Headers\n'  # will be skipped by parser
                output += '\n'.join(['\t'.join(image) for image in self.images])
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout=output.encode('utf-8'),
                )

            else:
                raise Exception('Unsupported command in mock: {}'.format(' '.join(command)))

    return MockDocker()
