import os
import shutil

from setuptools import Command, find_packages, setup


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

    def initialize_options(self):
        '''This method must be implemented by all command classes.'''
        pass

    def finalize_options(self):
        '''This method must be implemented by all command classes.'''
        pass

    def run(self):
        dirname = os.path.dirname(os.path.realpath(__file__))

        def remove(path):
            if os.path.exists(path):
                print("Removing {}".format(path))
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


print (find_packages())
setup(
    name="bluetube-cli",
    version="2.0",
    packages=find_packages(),
    package_data={
        '': ['*.py', ],
    },
    entry_points={
        "console_scripts": [
            "bluetube=bluetube.bluetube:main",
            ]
    },
    author="Olexandr Dubrov",
    author_email="olexandr.dubrov@gmail.com",
    description="a script that downloads video from Youtube by URLs get from RSS and sends via bluetooth",
    license="GNU GPL",
    keywords="Youtube, bluetooth, RSS",
    url="https://github.com/oleksandr-dubrov/bluetube",
    python_requires='>3.4, <4',
    install_requires=['feedparser', 'PyBluez', 'PyOBEX', 'toml'],
    cmdclass={
        'clean': CleanCommand,
    },
    classifiers=[
        'Programming Language :: Python :: 3.7',
    ],
)
