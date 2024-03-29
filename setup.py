import os
import shutil

from setuptools import Command, setup


def onerror(func, path, exc_info):
    """
    Error handler for ``shutil.rmtree``.

    If the error is due to an access error (read only file)
    it attempts to add write permission and then retries.

    If the error is for another reason it re-raises the error.

    Usage : ``shutil.rmtree(path, onerror=onerror)``
    """
    import stat
    if not os.access(path, os.W_OK):
        # Is the error an access error ?
        os.chmod(path, stat.S_IWUSR)
        func(path)


class CleanCommand(Command):
    """Clean command."""

    user_options = []

    def initialize_options(self):
        pass  # an empty implementation for the abstract method

    def finalize_options(self):
        pass  # an empty implementation for the abstract method

    def run(self):
        dirname = os.path.dirname(os.path.realpath(__file__))

        def remove(path):
            if os.path.exists(path):
                print(f"Removing {path}")
                if os.path.isdir(path):
                    shutil.rmtree(os.path.join(dirname, path), onerror=onerror)
                else:
                    os.remove(path)

        def remove_pyc():
            for f in os.listdir(dirname):
                if os.path.splitext(f)[-1] == '.pyc':
                    os.remove(f)

        remove("build")
        remove("bluetube_cli.egg-info")
        remove("dist")
        remove_pyc()


with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="bluetube-cli",
    version='2.0',
    author="Olexandr Dubrov",
    author_email="olexandr.dubrov@gmail.com",
    description="to get video from Youtube by RSS and send via bluetooth",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/oleksandr-dubrov/bluetube",
    license="GNU GPL",
    packages=['bluetube'],
    package_data={
        '': ['*.py', '*.toml'],
    },
    entry_points={
        "console_scripts": [
            "bluetube=bluetube.app:main",
            ]
    },
    keywords="Youtube, bluetooth, RSS",
    python_requires='>3.7',
    install_requires=['feedparser==6.0.8',
                      'PyBluez==0.23',
                      'PyOBEX', 
                      'toml==0.10.1',
                      'mutagen==1.45.1'],
    cmdclass={
        'clean': CleanCommand,
    },
    test_suite="tests",
    classifiers=[
        'Programming Language :: Python :: 3.7',
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Operating System :: POSIX :: Linux'
    ],
)
