from taskboot.target import Target
import os


class Config(object):
    target = None
    git_repository = None


def test_path():
    '''
    Test a path exists in a target
    '''
    conf = Config()
    target = Target(conf)

    assert os.path.isdir(target.dir)

    with open(os.path.join(target.dir, 'test.txt'), 'w') as f:
        f.write('Test')

    path = target.check_path('test.txt')
    assert os.path.exists(path)
    assert path.startswith(target.dir)
