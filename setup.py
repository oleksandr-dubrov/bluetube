import os
import shutil

from setuptools import Command, setup

from bluetube import __version__


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
    else:
        raise


class CleanCommand(Command):
    """Clean command."""

    user_options = []

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
    version=__version__,
    author="Olexandr Dubrov",
    author_email="olexandr.dubrov@gmail.com",
    description="to get video from Youtube by RSS and send via bluetooth",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/oleksandr-dubrov/bluetube",
    license="GNU GPL",
    packages=['bluetube'],
    package_data={
        '': ['*.py', 'profiles.toml'],
    },
    entry_points={
        "console_scripts": [
            "bluetube=bluetube.bluetube:main",
            ]
    },
    keywords="Youtube, bluetooth, RSS",
    python_requires='>3.6',
    install_requires=['feedparser', 'PyBluez', 'PyOBEX', 'toml'],
    cmdclass={
        'clean': CleanCommand,
    },
    test_suite="tests",
    classifiers=[
        'Programming Language :: Python :: 3.7',
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Operating System :: POSIX :: Linux'
    ],
)
