"""
The youtube-dl downloader.
"""
import logging
from pathlib import Path

from mutagen import MutagenError, id3, mp3, mp4

from bluetube.cli.events import Error
from bluetube.commandexecutor import CommandExecutor
from bluetube.eventpublisher import EventPublisher
from bluetube.model import OutputFormatType, Publication, PublicationStatus
from bluetube.utils import deemojify


class YoutubeDlDownloader(object):
    """
    The class downloads media by youtube-dl installed in the system.
    """

    NAME = "yt-dlp"  # ' a youtube-dl fork'

    def __init__(self, executor: CommandExecutor,
                 publisher: EventPublisher,
                 temp_dir: Path) -> None:
        self._executor = executor
        self._publisher = publisher
        self._temp_dir = temp_dir
        self._debug = logging.getLogger(__name__).debug

    def download(self, pub: Publication, output_format, configs) -> Publication:
        options = self._build_converter_options(output_format, configs)
        local_name = f"{deemojify(pub.title)} [{pub.remote_id}].{configs['output_format']}"
        all_options = options + ("-o", local_name) + (pub.link,)
        self._debug(f"downloading {pub.title} to {local_name}")
        status = self._executor.call(all_options, cwd=self._temp_dir)
        if status:  # failed to download
            # do not clean partially the downloaded file, it will be used for the next time
            self._debug(f"failed to download {pub.title}")
            pub.local_path = None
            pub.status = PublicationStatus.failed
            return pub
        else:
            self._debug(f"{pub.title} downloaded")
            pub.local_path = self._temp_dir / local_name
            pub.status = PublicationStatus.downloaded
            self._add_metadata(pub)
            return pub

    def is_ready(self) -> bool:
        """Check if the downloader exists."""
        err = self._executor.does_command_exist(YoutubeDlDownloader.NAME)
        if err:
            self._publisher.notify(Error("downloader not found",
                                   YoutubeDlDownloader.NAME))
        return not bool(err)

    def _build_converter_options(self, output_format, configs):
        """build options for the youtube-dl command line"""

        options = ("--ignore-config",  # Do  not  read  configuration  files.
                   "--ignore-errors",  # Continue on download errors
                   "--mark-watched",   # Mark videos watched (YouTube only)
                   )
        if output_format == OutputFormatType.audio:
            output_format = configs["output_format"]
            spec_options = ("--extract-audio",
                            f"--audio-format={output_format}",
                            "--audio-quality=9",  # 9 means worse
                            "--postprocessor-args", "-ac 1",  # convert to mono
                            )
        elif output_format == OutputFormatType.video:
            of = configs.get("output_format")
            spec_options = ("--format", of,) if of else ()
        else:
            assert 0, "unexpected output format"

        all_options = (YoutubeDlDownloader.NAME,) + options + spec_options
        return all_options

    def _add_metadata(self, pub: Publication):
        """add metadata to a downloaded file"""
        assert pub.local_path, "local path not found"
        ext = pub.local_path.suffix
        try:
            if ext == ".mp3":
                audio = mp3.MP3(pub.local_path)
                audio["TPE1"] = id3.TPE1(text=pub.playlist.author.name)
                audio["TIT2"] = id3.TIT2(text=pub.title)
                audio["COMM"] = id3.COMM(text=pub.description[:256])
                audio.save()
            elif ext == ".mp4":
                video = mp4.MP4(pub.local_path)
                video["\xa9ART"] = pub.playlist.author.name
                video["\xa9nam"] = pub.title
            else:
                self._debug(f"cannot add metadata to {ext}")
        except MutagenError as e:
            self._publisher.notify(Error(e))
