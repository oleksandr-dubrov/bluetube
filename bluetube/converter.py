"""
A video converter.
"""

from bluetube.cli.events import Error
from bluetube.commandexecutor import CommandExecutor
from bluetube.eventpublisher import EventPublisher
from bluetube.model import Publication, PublicationStatus


class FfmpegConverter(object):
    """
    This class converts media by ffmpeg installed in the system.
    """
    NAME = "ffmpeg"
    # keep files that failed to be converted here
    NOT_CONV_DIR = "[not yet converted files]"

    def __init__(self, executor: CommandExecutor,
                 publisher: EventPublisher,
                 temp_dir: str) -> None:
        self._publisher = publisher
        self._executor = executor
        self._temp_dir = temp_dir

    def convert(self, pub: Publication, configs) -> Publication:
        """Convert publication to disired format."""

        options = ("-y",  # overwrite output files
                   "-hide_banner",)
        codecs_options = configs.get("codecs_options", "")
        codecs_options = tuple(codecs_options.split())
        output_format = configs["output_format"]

        if not (pub.local_path and pub.local_path.is_file()):
            self._publisher(Error(f"file not found for {pub.title}; nothing to convert"))
            pub.status = PublicationStatus.failed
        else:
            new_name = pub.local_path.name.split(".")[0] + "." + output_format
            new_local_path = pub.local_path.with_name(new_name)
            args = (FfmpegConverter.NAME,) + ("-i", pub.local_path) + options + codecs_options + (new_local_path,)
            err = self._executor.call(args, cwd=self._temp_dir)
            if err:
                pub.status = PublicationStatus.failed
            else:
                pub.local_path = new_local_path
                pub.status = PublicationStatus.converted
        return pub

    def is_ready(self) -> bool:
        """Check if the converter exists."""
        err = self._executor.does_command_exist(FfmpegConverter.NAME, dashes=1)
        if err:
            self._publisher.notify(Error("converter not found", FfmpegConverter.NAME))
        return not bool(err)
