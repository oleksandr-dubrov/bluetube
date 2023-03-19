
import unittest
from unittest.mock import Mock

from bluetube.cli import Inputer, Outputer
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

    def test_get_inputer(self):
        inputer = self.sut.get_inputer(True)
        self.assertIsNotNone(self.sut._executor)
        self.assertIsInstance(inputer, Inputer)

    def test_get_outputer(self):
        outputer = self.sut.get_outputer()
        self.assertIsNone(self.sut._executor)
        self.assertIsInstance(outputer, Outputer)


if __name__ == "__main__":
    unittest.main()
