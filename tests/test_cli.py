
import unittest
from unittest.mock import MagicMock, Mock, patch

from bluetube.cli import Outputer
from bluetube.cli.events import Error, Info, Success, Warn
from bluetube.cli.inputer import Inputer


class TestCliOutputer(unittest.TestCase):

    def setUp(self):
        self.sut = Outputer()

    def test_update(self):
        with patch('builtins.print'):
            self.sut.update(Info('empty database'))
            self.sut.update(Error('misformatted URL'))
            self.sut.update(Success('feed updated'))
            self.sut.update(Warn('conversion is not needed'))


class TestCliInputer(unittest.TestCase):

    def test_do_continue(self):
        sut = Inputer(executor=MagicMock())
        with patch('builtins.input'):
            self.assertTrue(sut.do_continue())

    def test_ask(self):
        sut = Inputer(executor=MagicMock(), yes=True)
        with patch('builtins.input'):
            self.assertTrue(sut.ask(Mock()))


if __name__ == "__main__":
    unittest.main()
