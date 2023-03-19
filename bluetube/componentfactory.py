'''
The factory.
'''


from bluetube.cli import Inputer, Outputer
from bluetube.commandexecutor import CommandExecutor
from bluetube.converter import FfmpegConvertver
from bluetube.ytdldownloader import YoutubeDlDownloader


class ComponentFactory(object):
    '''
    A factory that makes all bluetube components.
    '''

    def __init__(self) -> None:
        self._executor = None
        self._outputer = None

    def get_command_executor(self):
        '''Get a object to start OS processes.'''
        if not self._executor:
            self._executor = CommandExecutor()
        return self._executor

    def get_downloader(self, temp_dir: str):
        '''Get a downloader.'''
        ex = self.get_command_executor()
        return YoutubeDlDownloader(ex, self.get_outputer(), temp_dir)

    def get_converter(self, temp_dir: str):
        ex = self.get_command_executor()
        return FfmpegConvertver(self.get_outputer(), ex, temp_dir)

    def get_inputer(self, yes: bool) -> Inputer:
        ex = self.get_command_executor()
        return Inputer(ex, yes)

    def get_outputer(self) -> Outputer:
        if not self._outputer:
            self._outputer = Outputer()
        return self._outputer
