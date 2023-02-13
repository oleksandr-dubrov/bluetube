'''
The factory.
'''


from bluetube.commandexecutor import CommandExecutor
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

    def get_downloader(self, event_listener, temp_dir):
        '''Get a downloader.'''
        ex = self.get_command_executor()
        return YoutubeDlDownloader(ex, event_listener, temp_dir)
