"""
The factory.
"""

from pathlib import Path
from typing import Optional

from bluetube.bluetoothclient import BluetoothClient
from bluetube.cli import Inputer, Outputer
from bluetube.cli.events import Error
from bluetube.commandexecutor import CommandExecutor
from bluetube.converter import FfmpegConverter
from bluetube.eventpublisher import EventPublisher
from bluetube.repository import Repository
from bluetube.sender import BluetoothSender, LocalSender, Sender
from bluetube.ytdldownloader import YoutubeDlDownloader


class ComponentFactory(object):
    """
    A factory that makes all bluetube components.
    """

    _bt_senders: dict[str, BluetoothClient] = {}

    def get_command_executor(self):
        """Get a object to start OS processes."""
        if not hasattr(self, "_executor"):
            self._executor = CommandExecutor()
        return self._executor

    def get_downloader(self, publisher: EventPublisher, temp_dir: Path):
        """Get a downloader."""
        ex = self.get_command_executor()
        return YoutubeDlDownloader(ex, publisher, temp_dir)

    def get_converter(self, publisher: EventPublisher, temp_dir: str):
        ex = self.get_command_executor()
        return FfmpegConverter(ex, publisher, temp_dir)

    def get_inputer(self, yes: bool) -> Inputer:
        if not hasattr(self, "_inputer"):
            ex = self.get_command_executor()
            self._inputer = Inputer(ex, yes)
        return self._inputer

    def get_outputer(self) -> Outputer:
        if not hasattr(self, "_outputer"):
            self._outputer = Outputer()
        return self._outputer

    def get_bluetooth_client(self, device_id: str,
                             publisher: EventPublisher, temp_dir: Path) -> Optional[BluetoothClient]:
        '''Return a sender from the cache for a device ID if possible
        or create a new one.'''

        if device_id in self._bt_senders:
            return self._bt_senders[device_id]
        else:
            sender = BluetoothClient(publisher, device_id, temp_dir)
            if not sender.found:
                self.notify(Error('device not found', device_id, str(temp_dir)))
            else:
                self._bt_senders[device_id] = sender
            return sender

    def get_senders(self, publisher: EventPublisher, temp_dir: Path,
                    /, local_path: Optional[Path], device_id: Optional[str]) -> dict[str, Sender]:
        """Get senders based on input parameters."""
        senders = {}

        if local_path:
            senders[str(local_path)] = LocalSender()

        if device_id:
            client = self.get_bluetooth_client(device_id, publisher, temp_dir)
            senders[device_id] = BluetoothSender(client)

        return senders

    def get_repository(self, bt_dir: Path) -> Repository:
        """Get repository."""
        if not hasattr(self, "_repository"):
            self._repository = Repository(bt_dir)
        return self._repository
