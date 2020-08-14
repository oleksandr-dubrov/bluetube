import json
import os
import unittest
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

from bluetube import Bluetube
from bluetube.bluetube import CLI

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


def get_nbr_of_new_links():
    '''get number of new videos, it's 3.'''
    return 3

def call_side_effect(*args, **kwargs):
    ''' create a files from the URL as the call does'''
    fake_name = args[0][-1].split('=')[1]
    open(os.path.join(kwargs['cwd'], fake_name), 'w').close()
    return 0


def bt_side_effect(*args):
    assert len(args) == 1
    # return the link we have got
    return args[0]


class TestBluetube(unittest.TestCase):

    def setUp(self):
        self.sut = Bluetube(verbose=True)
        self.sut._get_bt_dir = lambda: os.path.dirname(os.path.abspath(__file__))


    def tearDown(self):
        patch.stopall()  # @UndefinedVariable

    def mock_db(self, fake_db):
        '''mock shelve DB with the fake DB''' 
        mock_db = MagicMock()
        if isinstance(fake_db, dict):
            mock_db.get.return_value = fake_db
        elif isinstance(fake_db, str):
            mock_db.get.return_value = json.loads(fake_db)
        else:
            assert 0, 'string or dictionary expected'
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

    def mock_sender(self, found, connect, send):
        '''mock the bluetooth client'''
        patcher = patch('bluetube.bluetube.BluetoothClient')
        bt = patcher.start()
        attrs = dict(found=found,
                     connect=lambda: connect,
                     send=lambda *args: send(*args),
                     disconnect= lambda: None)
        bt.return_value = type('mocked_BluetoothClient', (object,), attrs)
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
        mdb = self.mock_db(FAKE_DB)
        cli = self.mock_cli()
        self.mock_executor()
        mock_send = MagicMock(side_effect=bt_side_effect)
        bt = self.mock_sender(found=True, connect=True, send=mock_send)
        urlopen = self.mock_remote_data()

        self.sut.run()

        nbr_urls = FAKE_DB.count('"url"')
        mdb.assert_called_once()
        self.assertEqual(urlopen.return_value.read.call_count, nbr_urls)
        self.assertEqual(cli.ask.call_count, get_nbr_of_new_links())
        bt.assert_called()
        self.assertEqual(mock_send.call_count, 2,
                         'it should be called if one or more links chosen')

    @patch('bluetube.bluetube.CLI')
    def testRunNothigSelected(self, cli):
        '''no selected videos to process'''
        cli.ask.return_value = False
        self.sut.event_listener = cli

        mdb = self.mock_db(FAKE_DB)
        self.mock_executor()
        mock_send = MagicMock(side_effect=bt_side_effect)
        bt = self.mock_sender(found=True, connect=True, send=mock_send)
        urlopen = self.mock_remote_data()

        self.sut.run()

        mdb.assert_called_once()
        cli.inform.assert_any_call('feeds updated')
        self.assertEqual(urlopen.return_value.read.call_count,
                         FAKE_DB.count('"url"'))
        self.assertEqual(cli.ask.call_count, get_nbr_of_new_links())
        bt.assert_not_called()
        self.assertEqual(mock_send.call_count, 0)

    def testEmptyDB(self):
        '''inform about the empty DB and do nothing'''
        mdb = self.mock_db({})
        cli = self.mock_cli()
        cli.inform = MagicMock()
        cli.feeds_updated = MagicMock()

        self.sut.run()

        mdb.assert_called_once()
        cli.inform.assert_any_call('empty database')
        cli.feeds_updated.assert_not_called()


class TestCli(unittest.TestCase):
    
    def setUp(self):
        self.sut = CLI(executor=MagicMock())

    def testInforms(self):
        with patch('builtins.print'):
            self.sut.inform('empty database')
            self.sut.inform('feed is fetching', 'a message')
            self.sut.inform('feed updated')
            self.sut.inform('an abitrary message')
        self.sut._executor.call.assert_called_once()


if __name__ == "__main__":
    unittest.main()
