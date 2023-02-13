
import unittest
from unittest.mock import MagicMock, patch

from bluetube.cli import CLI


class TestCli(unittest.TestCase):

    def setUp(self):
        self.sut = CLI(executor=MagicMock())

    def test_informs(self):
        with patch('builtins.print'):
            self.sut.inform('empty database')
            self.sut.inform('feed is fetching', 'a message')
            self.sut.success('feed updated')
            self.sut.inform('an arbitrary message')
        self.sut._executor.call.assert_called_once()


if __name__ == "__main__":
    unittest.main()
