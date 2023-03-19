'''
The factory.
'''


from bluetube.cli import CLI
from bluetube.commandexecutor import CommandExecutor
from bluetube.converter import FfmpegConvertver
from bluetube.ytdldownloader import YoutubeDlDownloader


class ComponentFactory(object):
    '''
    A factory that makes all bluetube components.
    '''

    def __init__(self) -> None:
        self._executor = None

    def get_command_executor(self):
        '''Get a object to start OS processes.'''
        if not self._executor:
            self._executor = CommandExecutor()
        return self._executor

    def get_downloader(self, event_listener: CLI, temp_dir: str):
        '''Get a downloader.'''
        ex = self.get_command_executor()
        return YoutubeDlDownloader(ex, event_listener, temp_dir)

    def get_converter(self, event_listener: CLI, temp_dir: str):
        ex = self.get_command_executor()
        return FfmpegConvertver(event_listener, ex, temp_dir)

    def get_cli(self, yes: bool):
        ex = self.get_command_executor()
        return CLI(ex, yes)
