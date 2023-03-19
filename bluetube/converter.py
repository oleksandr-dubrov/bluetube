'''
A video converter.
'''


import os

from bluetube.cli.events import Error, Info, Warn


class FfmpegConvertver(object):
    '''
    This class converts media by ffmpeg installed in the system.
    '''
    NAME = 'ffmpeg'
    # keep files that failed to be converted here
    NOT_CONV_DIR = '[not yet converted files]'

    def __init__(self, event_listener, executor, temp_dir) -> None:
        self._event_listener = event_listener
        self._executor = executor
        self._temp_dir = temp_dir

    def convert(self, entities, configs):
        '''convert all videos in the playlist,
        return a list of succeeded an and a list of failed links'''

        success, failure = [], []
        if not self._check_video_converter():
            self._event_listener.update(Error('converter not found',
                                        FfmpegConvertver.NAME))
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
                self._event_listener.update(Warn('conversion is not needed'))
                success.append(en)
                continue
            args = (FfmpegConvertver.NAME,) + ('-i', orig) + options + \
                codecs_options + (new,)
            if not 1 == self._executor.call(args, cwd=self._temp_dir):
                os.remove(os.path.join(self._temp_dir, orig))
                en['link'] = new
                success.append(en)
            else:
                failure.append(en)
                d = os.path.join(self._temp_dir, FfmpegConvertver.NOT_CONV_DIR)
                os.makedirs(d, FfmpegConvertver.ACCESS_MODE, exist_ok=True)
                os.rename(orig, os.path.join(d, os.path.basename(orig)))
                self._event_listener.update(Error(os.path.basename(orig)))
                self._event_listener.update(
                    Info(f'Command: \n{" ".join(args)}'))
                self._event_listener.update(Info(f'Check {d} after '
                                                 f'the script is done.'))
        return success, failure

    def _check_video_converter(self):
        if not self._executor.does_command_exist(FfmpegConvertver.NAME,
                                                 dashes=1):
            self._event_listener.update(Error('converter not found',
                                        FfmpegConvertver.NAME))
            return self._event_listener.do_continue()
        return True
