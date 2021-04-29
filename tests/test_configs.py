import os
import unittest
from unittest.mock import MagicMock, patch

import toml

from bluetube.configs import Configs


class TestConfig(unittest.TestCase):

    CONFIGS = '''
[editor]
default = "nano"
[media_player]
default = ""
'''

    @patch('toml.load')
    def setUp(self, _):
        Configs.create_configs = MagicMock()
        self.SUT = Configs(MagicMock())
        self.SUT._configs = toml.loads(TestConfig.CONFIGS)
        self.SUT._dump = lambda: None
        self.editor_bak = os.environ.get('EDITOR')

    def tearDown(self):
        if self.editor_bak is not None:
            os.environ['EDITOR'] = self.editor_bak

    def test_get_editor(self):
        os.environ['EDITOR'] = 'emacs'
        self.assertEqual('emacs', self.SUT.get_editor(), 'unexpected editor')
        os.environ['EDITOR'] = ""
        self.assertEqual('nano', self.SUT.get_editor(), 'unexpected editor')

    def test_get_media_player(self):
        player = 'vlc'
        self.SUT.set_media_player(player)
        self.assertEqual(player, self.SUT.get_media_player(),
                         'unexpected media player')


if __name__ == "__main__":
    unittest.main()
