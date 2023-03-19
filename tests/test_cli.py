
import unittest
from unittest.mock import MagicMock, patch

from bluetube.cli.cli import CLI, Error, Info, Success, Warn


class TestCli(unittest.TestCase):

    def setUp(self):
        self.sut = CLI(executor=MagicMock())

    def test_update(self):
        with patch('builtins.print'):
            self.sut.update(Info('empty database'))
            self.sut.update(Error('misformatted URL'))
            self.sut.update(Success('feed updated'))
            self.sut.update(Warn('conversion is not needed'))
        self.sut._executor.call.assert_called_once()


if __name__ == "__main__":
    unittest.main()
