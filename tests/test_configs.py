import os
import unittest
from unittest.mock import MagicMock, patch

import toml

from bluetube.configs import Configs


class TestConfig(unittest.TestCase):

    CONFIGS = '''
[editor]
default = "nano"
'''

    @patch('toml.load')
    def setUp(self, _):
        Configs.create_configs = MagicMock()
        self.SUT = Configs(MagicMock())
        self.SUT._configs = toml.loads(TestConfig.CONFIGS)
        self.editor_bak = os.environ.get('EDITOR')

    def tearDown(self):
        if self.editor_bak is not None:
            os.environ['EDITOR'] = self.editor_bak

    def test_get_editor(self):
        os.environ['EDITOR'] = 'emacs'
        self.assertEqual('emacs', self.SUT.get_editor(), 'unexpected editor')
        os.environ['EDITOR'] = ""
        self.assertEqual('nano', self.SUT.get_editor(), 'unexpected editor')


if __name__ == "__main__":
    unittest.main()
