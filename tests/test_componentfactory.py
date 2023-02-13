
import unittest
from unittest.mock import Mock

from bluetube.commandexecutor import CommandExecutor
from bluetube.componentfactory import ComponentFactory
from bluetube.ytdldownloader import YoutubeDlDownloader


class TestComponentFactory(unittest.TestCase):

    def setUp(self):
        self.sut = ComponentFactory()

    def test_get_command_executor(self):
        ex = self.sut.get_command_executor()
        self.assertIsInstance(ex, CommandExecutor)

    def test_get_downloader(self):
        dl = self.sut.get_downloader(Mock(), Mock())
        self.assertIsNotNone(self.sut._executor)
        self.assertIsInstance(dl, YoutubeDlDownloader)


if __name__ == "__main__":
    unittest.main()
