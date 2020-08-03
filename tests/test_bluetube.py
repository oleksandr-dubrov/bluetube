import json
import os
import unittest
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

from bluetube import Bluetube

from tests.fake_db import FAKE_DB


def read_mocked_data():
    d = os.path.dirname(os.path.abspath(__file__))
    zf = ZipFile(os.path.join(d,'mocked_data.zip'))
    with open(os.path.join(d, ZipFile.namelist(zf)[0]), 'r') as f:
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
        patch.stopall()  # @UndefinedVariable

    def mock_db(self):
        '''mock shelve DB with the fake DB''' 
        mock_db = MagicMock()
        mock_db.get.return_value = json.loads(FAKE_DB)
        patcher = patch('shelve.open', return_value=mock_db)
        return patcher.start()

    def mock_cli(self):
        ''' mock an event listener'''
        patcher = patch('bluetube.bluetube.CLI')
        cli = patcher.start()
        cli.ask.return_value = True
        self.sut.event_listener = cli
        return cli

    def mock_executor(self):
        '''mock the command executor'''
        self.sut.executor = MagicMock()
        self.sut.executor.call.side_effect = call_side_effect

    def mock_sender(self):
        '''mock the bluetooth client'''
        patcher = patch('bluetube.bluetube.BluetoothClient')
        bt = patcher.start()
        bt.found = True
        bt.connect.return_value = True
        bt.send.side_effect = bt_side_effect
        return bt

    def mock_remote_data(self):
        '''mock remote data returned by urlopen'''
        patcher = patch('urllib.request.urlopen')
        uo = patcher.start()
        md = read_mocked_data()
        uo.return_value = MagicMock()
        uo.return_value.read.side_effect = [l.encode() for l in md]
        return uo

    def testRun(self):
        '''an origin good usage'''
        mdb = self.mock_db()
        self.mock_cli()
        self.mock_executor()
        self.mock_sender()
        urlopen = self.mock_remote_data()

        self.sut.run()

        mdb.assert_called_once()
        # see fake_db.py
        self.assertEqual(urlopen.return_value.read.call_count, 10)

if __name__ == "__main__":
    unittest.main()
