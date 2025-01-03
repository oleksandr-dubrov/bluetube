import logging
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from bluetube.bluetoothclient import BluetoothClient

ACCESS_MODE = 0o744

logger = logging.getLogger(__name__)


class Sender(ABC):

    @abstractmethod
    def send(self, src: Path, dst: str) -> None:
        """Send src to dst."""


class LocalSender(Sender):

    def send(self, src: Path, dst: str) -> None:
        """Copy a file to local directory."""

        local_dir = Path(dst)
        if not local_dir.is_dir():
            raise SenderException(f"{dst} is not directory")

        try:
            os.makedirs(local_dir, ACCESS_MODE, exist_ok=True)
        except PermissionError as e:
            raise SenderException(str(e))

        self._copy_to_local_path(src, dst)

    def _copy_to_local_path(self, src, dst) -> None:
        '''copy files defined by links to the local path'''
        logger.debug(f'copying {src} to {dst}')
        try:
            shutil.copy2(src, dst)
        except shutil.SameFileError:
            logger.warning("%s already exists", str(dst))


class BluetoothSender(Sender):

    def __init__(self, client: BluetoothClient) -> None:
        self._client = client

    def send(self, src: Path, dst: str) -> None:
        """Send file to a bluetooth device."""

        if not self._client.found:
            raise SenderException("device not found %s", dst)

        sent = self._client.send([src])
        self._client.disconnect()

        if not sent:
            raise SenderException("failed to send %s to", str(src.name), dst)


class SenderException(Exception):
    """Sender exception."""
