from setuptools import setup


def requirements(path):
    with open(path) as f:
        return f.read().splitlines()


setup(
    name="task-boot",
    version=open("VERSION").read().replace("\n", ""),
    author="Bastien Abadie",
    author_email="bastien@mozilla.com",
    description="An helper tool to bootstrap Taskcluster usage",
    url="https://github.com/mozilla/task-boot",
    license="MPL2",
    keywords="mozilla taskcluster ci",
    packages=["taskboot"],
    install_requires=requirements("requirements.txt"),
    tests_require=requirements("requirements-tests.txt"),
    entry_points={
        "console_scripts": ["tb = taskboot.cli:main", "taskboot = taskboot.cli:main"]
    },
)
