'''
The factory.
'''

from bluetube.cli import Inputer, Outputer
from bluetube.commandexecutor import CommandExecutor
from bluetube.converter import FfmpegConvertver
from bluetube.eventpublisher import EventPublisher
from bluetube.ytdldownloader import YoutubeDlDownloader


class ComponentFactory(object):
    '''
    A factory that makes all bluetube components.
    '''

    def get_command_executor(self):
        '''Get a object to start OS processes.'''
        if not hasattr(self, '_executor'):
            self._executor = CommandExecutor()
        return self._executor

    def get_downloader(self, publisher: EventPublisher, temp_dir: str):
        '''Get a downloader.'''
        ex = self.get_command_executor()
        return YoutubeDlDownloader(ex, publisher, temp_dir)

    def get_converter(self, publisher: EventPublisher, temp_dir: str):
        ex = self.get_command_executor()
        return FfmpegConvertver(ex, publisher, temp_dir)

    def get_inputer(self, yes: bool) -> Inputer:
        if not hasattr(self, '_inputer'):
            ex = self.get_command_executor()
            self._inputer = Inputer(ex, yes)
        return self._inputer

    def get_outputer(self) -> Outputer:
        if not hasattr(self, '_outputer'):
            self._outputer = Outputer()
        return self._outputer
