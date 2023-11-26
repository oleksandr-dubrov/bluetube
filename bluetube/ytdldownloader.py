'''
The youtube-dl downloader.
'''
import logging
import os
from typing import Dict, List, Tuple

from mutagen import MutagenError, id3, mp3, mp4

from bluetube.cli.events import Error
from bluetube.commandexecutor import CommandExecutor
from bluetube.eventpublisher import EventPublisher
from bluetube.model import OutputFormatType
from bluetube.utils import deemojify


class YoutubeDlDownloader(object):
    '''
    The class downloads media by youtube-dl installed in the system.
    '''

    NAME = "yt-dlp"  # ' a youtube-dl fork'

    def __init__(self, executor: CommandExecutor,
                 publisher: EventPublisher,
                 temp_dir: str) -> None:
        self._cache: Dict = {}
        self._executor = executor
        self._publisher = publisher
        self._temp_dir = temp_dir
        self._debug = logging.getLogger(__name__).debug

    def download(self, entities, output_format, configs) -> Tuple[List, List]:
        options = self._build_converter_options(output_format, configs)
        success: List = []
        failure: List = []

        if not self._check_downloader():
            self._publisher.notify(Error('downloader not found',
                                   YoutubeDlDownloader.NAME))
            failure = [en for en in entities]
            return success, failure

        for en in entities:
            all_options = options + (en['link'],)

            # check the value in the given cache
            # to avoid downloading the same file twice
            new_link = self._cache.get(' '.join(all_options))
            if new_link:
                self._debug(f'this link has been downloaded - {new_link}')
                en['link'] = new_link
                success.append(en)
            else:
                status = self._executor.call(all_options, cwd=self._temp_dir)
                just_downloaded = [jd for jd in os.listdir(self._temp_dir)
                                   if en['yt_videoid'] in jd]
                assert len(just_downloaded) <= 1, \
                    f"more than one file with {en['yt_videoid']}" +\
                    "has just been downloaded"
                if status:
                    failure.append(en)
                    # clear partially downloaded files if any
                    for f in just_downloaded:
                        os.unlink(os.path.join(self._temp_dir, f))
                else:
                    x = deemojify(just_downloaded[0])
                    os.rename(os.path.join(self._temp_dir, just_downloaded[0]),
                              os.path.join(self._temp_dir, x))
                    just_downloaded[0] = x
                    self._add_metadata(en,
                                       os.path.join(self._temp_dir,
                                                    just_downloaded[0]))
                    en['link'] = just_downloaded[0]
                    success.append(en)

                    # put the link to just downloaded file into the cache
                    self._cache[' '.join(all_options)] = just_downloaded[0]

        return success, failure

    def _build_converter_options(self, output_format, configs):
        '''build options for the youtube-dl command line'''

        options = ('--ignore-config',  # Do  not  read  configuration  files.
                   '--ignore-errors',  # Continue on download errors
                   '--mark-watched',   # Mark videos watched (YouTube only)
                   )
        if output_format == OutputFormatType.audio:
            output_format = configs['output_format']
            spec_options = ('--extract-audio',
                            f'--audio-format={output_format}',
                            '--audio-quality=9',  # 9 means worse
                            '--postprocessor-args', '-ac 1',  # convert to mono
                            )
        elif output_format == OutputFormatType.video:
            of = configs.get('output_format')
            spec_options = ('--format', of,) if of else ()
        else:
            assert 0, 'unexpected output format'

        all_options = (YoutubeDlDownloader.NAME,) + options + spec_options
        return all_options

    def _check_downloader(self):
        return self._executor.does_command_exist(YoutubeDlDownloader.NAME)

    def _add_metadata(self, entity, file_path):
        '''add metadata to a downloaded file'''
        ext = os.path.splitext(file_path)[1]
        try:
            if ext == '.mp3':
                audio = mp3.MP3(file_path)
                audio['TPE1'] = id3.TPE1(text=entity.author)
                audio['TIT2'] = id3.TIT2(text=entity.title)
                audio['COMM'] = id3.COMM(text=entity.summary[:256])
                audio.save()
            elif ext == '.mp4':
                video = mp4.MP4(file_path)
                video["\xa9ART"] = entity.author
                video["\xa9nam"] = entity.title
            else:
                self._debug(f'cannot add metadata to {ext}')
        except MutagenError as e:
            self._publisher.notify(Error(e))
