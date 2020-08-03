import os
import json
import unittest
from zipfile import ZipFile
from unittest.mock import patch, Mock
from bluetube import Bluetube
from .fake_profiles import PROFILES


def read_mocked_data():
    zf = ZipFile('mocked_data.zip')
    with open(ZipFile.namelist(zf)[0], 'r') as f:
        pls = []
        p = f.readline()
        for l in f.readlines():
            if '<?xml version="1.0" encoding="UTF-8"?>' in l:
                pls.append(p)
                p = l
            else:
                p += l
        pls.append(p)
        return pls


def call_side_effect(*args, **kwargs):
    ''' create a files from the URL as the call does'''
    fake_name = args[0][-1].split('=')[1]
    open(os.path.join(kwargs['cwd'], fake_name), 'w').close()
    return 0


def bt_side_effect(*args):
    assert len(args) == 1
    # return the link we have got
    return args[0]


class Test(unittest.TestCase):

    def setUp(self):
        self.sut = Bluetube(verbose=True)
        self.sut._get_bt_dir = lambda: os.path.dirname(os.path.abspath(__file__))


    def tearDown(self):
        pass

    @patch('bluetube.bluetube.BluetoothClient')
    @patch('bluetube.bluetube.CLI')
    @patch('shelve.open')
    def testRun(self, shelve, cli, bluetooth):
        md = read_mocked_data()
        mock_db = Mock()
        mock_db.get.return_value = json.loads(PROFILES)
        shelve.return_value = mock_db
        
        cli.ask.return_value = True
        self.sut.event_listener = cli
        self.sut.executor = Mock()
        self.sut.executor.call.side_effect = call_side_effect

        bluetooth.found = True
        bluetooth.connect.return_value = True
        bluetooth.send.side_effect = bt_side_effect

        with patch('urllib.request.urlopen') as urlopen:
            urlopen.return_value = Mock()
            urlopen.return_value.read.side_effect = [l.encode() for l in md]
            self.sut.run()


if __name__ == "__main__":
    unittest.main()
