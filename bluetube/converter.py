'''
A video converter.
'''


import os

from bluetube.cli.events import Error, Info, Warn
from bluetube.cli.inputer import Inputer
from bluetube.commandexecutor import CommandExecutor
from bluetube.eventpublisher import EventPublisher


class FfmpegConverter(object):
    '''
    This class converts media by ffmpeg installed in the system.
    '''
    NAME = 'ffmpeg'
    # keep files that failed to be converted here
    NOT_CONV_DIR = '[not yet converted files]'

    def __init__(self, executor: CommandExecutor,
                 publisher: EventPublisher,
                 temp_dir: str) -> None:
        self._publisher = publisher
        self._executor = executor
        self._temp_dir = temp_dir

    def convert(self, entities, configs):
        '''convert all videos in the playlist,
        return a list of succeeded an and a list of failed links'''

        success, failure = [], []
        if not self._check_video_converter():
            self._publisher.notify(Error('converter not found',
                                   FfmpegConverter.NAME))
            failure = [en for en in entities]
            return success, failure

        options = ('-y',  # overwrite output files
                   '-hide_banner',)
        codecs_options = configs.get('codecs_options', '')
        codecs_options = tuple(codecs_options.split())
        output_format = configs['output_format']
        for en in entities:
            orig = en['link']
            new = os.path.splitext(orig)[0] + '.' + output_format
            if orig == new:
                self._publisher.notify(Warn('conversion is not needed'))
                success.append(en)
                continue
            args = (FfmpegConverter.NAME,) + ('-i', orig) + options + \
                codecs_options + (new,)
            if not 1 == self._executor.call(args, cwd=self._temp_dir):
                os.remove(os.path.join(self._temp_dir, orig))
                en['link'] = new
                success.append(en)
            else:
                failure.append(en)
                d = os.path.join(self._temp_dir, FfmpegConverter.NOT_CONV_DIR)
                os.makedirs(d, FfmpegConverter.ACCESS_MODE, exist_ok=True)
                os.rename(orig, os.path.join(d, os.path.basename(orig)))
                self._publisher.notify(Error(os.path.basename(orig)))
                self._publisher.notify(
                    Info(f'Command: \n{" ".join(args)}'))
                self._publisher.notify(Info(f'Check {d} after '
                                            f'the script is done.'))
        return success, failure

    def _check_video_converter(self):
        if not self._executor.does_command_exist(FfmpegConverter.NAME,
                                                 dashes=1):
            self._publisher.notify(Error('converter not found',
                                         FfmpegConverter.NAME))
            return Inputer.do_continue()
        return True
