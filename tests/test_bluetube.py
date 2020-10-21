import io
import json
import os
import shutil
import unittest
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

from bluetube import Bluetube
from bluetube.bluetube import CLI
from bluetube.commandexecutor import cache
from tests.fake_db import FAKE_DB, NEW_LINKS


def read_mocked_data():
    d = os.path.dirname(os.path.abspath(__file__))
    with ZipFile(os.path.join(d, 'mocked_data.zip')) as zf:
        f = io.StringIO(zf.read(ZipFile.namelist(zf)[0]).decode("utf-8"))
        pls = []
        p = f.readline()
        for ln in f.readlines():
            if '<?xml version="1.0" encoding="UTF-8"?>' in ln:
                pls.append(p)
                p = ln
            else:
                p += ln
        pls.append(p)
        return pls


class TestBluetube(unittest.TestCase):

    TMP_DIR = '/tmp/bluetube_tests'  # sa: profiles.toml

    def setUp(self):
        self.args = []
        self.sut = Bluetube(verbose=False)
        self.sut._get_bt_dir = lambda: \
            os.path.dirname(os.path.abspath(__file__))
        self.nbr_downloaded = 0
        self.nbr_converted = 0
        self.nbr_sent = 0
        os.makedirs(TestBluetube.TMP_DIR, Bluetube.ACCESS_MODE, exist_ok=True)

    def tearDown(self):
        patch.stopall()  # @UndefinedVariable
        if os.path.exists(TestBluetube.TMP_DIR) \
                and os.path.isdir(TestBluetube.TMP_DIR):
            shutil.rmtree(TestBluetube.TMP_DIR)

    def mock_db(self, fake_db, dct=None):
        '''mock shelve DB with the fake DB'''
        mock_db = MagicMock()
        if dct:
            mock_db.__setitem__.side_effect = dct.__setitem__
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

    def mock_listdir(self, ret=None):
        '''mock os.listdir'''
        patcher = patch('os.listdir')
        osls = patcher.start()
        osls.return_value = ret
        return osls

    def mock_check_file(self):
        '''mock os.path.exists and os.path.isdir'''
        patcher1 = patch('os.path.exists')
        patcher2 = patch('os.path.isdir')
        ex = patcher1.start()
        isdir = patcher2.start()
        ex.return_value = True
        isdir.return_value = True
        return ex, isdir

    @cache
    def call_side_effect(self, *args, **kwargs):
        ''' create a files from the URL as the youtube-dl does
            or
            create a file with the extension as ffmpeg does'''
        str_args = ' '.join(args[0])
        if str_args in self.args:
            self.fail(f'called twice: {str_args}')
        self.args.append(str_args)

        if args[0][0] == 'youtube-dl':
            fake_name = args[0][-1].split('=')[1]
            open(os.path.join(kwargs['cwd'], fake_name), 'w').close()
            self.nbr_downloaded += 1
        elif args[0][0] == 'ffmpeg':
            open(args[0][-1], 'w').close()
            self.nbr_converted += 1
        return 0

    def mock_executor(self):
        '''mock the command executor'''
        self.sut.executor = MagicMock()
        self.sut.executor.call.side_effect = self.call_side_effect
        self.sut.executor.does_command_exist.return_value = True

    def mock_sender(self, found, connect, send):
        '''mock the bluetooth client'''
        patcher = patch('bluetube.bluetube.BluetoothClient')
        bt = patcher.start()
        attrs = dict(found=found,
                     connect=lambda: connect,
                     send=lambda *args: send(*args),
                     disconnect=lambda: None)
        bt.return_value = type('mocked_BluetoothClient', (object,), attrs)
        return bt

    def bt_side_effect(self, *args):
        assert len(args) == 1
        # return the link we have got
        self.nbr_sent += len(args[0])
        return args[0]

    def mock_remote_data(self):
        '''mock remote data returned by urlopen'''
        patcher = patch('urllib.request.urlopen')
        uo = patcher.start()
        md = read_mocked_data()
        uo.return_value = MagicMock()
        uo.return_value.read.side_effect = [ln.encode() for ln in md]
        return uo

    def mock_shutil_copy(self):
        ''' mock shutil.copy2'''
        patcher = patch('shutil.copy2')
        return patcher.start()

    def check_author_title(self, feeds, author, title):
        for a in feeds:
            if a['author'] == author:
                for t in a['playlists']:
                    if t['title'] == title:
                        return True
        return False

###############################################################################

    def test_run(self):
        '''an origin good usage'''
        mdb = self.mock_db(FAKE_DB)
        cli = self.mock_cli()
        self.mock_executor()
        mock_send = MagicMock(side_effect=self.bt_side_effect)
        bt = self.mock_sender(found=True, connect=True, send=mock_send)
        urlopen = self.mock_remote_data()
        mock_copy = self.mock_shutil_copy()

        self.sut.run()

        self.assertEqual(2, mdb.call_count,
                         'should be called for read and write')

        nbr_urls = FAKE_DB.count('"url"')
        self.assertEqual(urlopen.return_value.read.call_count, nbr_urls)

        self.assertEqual(cli.ask.call_count, NEW_LINKS)

        self.assertEqual(NEW_LINKS, self.nbr_downloaded)
        self.assertEqual(self.nbr_downloaded + self.nbr_converted,
                         self.sut.executor.call.call_count)

        bt.assert_called()
        self.assertEqual(3, mock_send.call_count,
                         'it should be called if one or more links chosen')
        self.assertEqual(NEW_LINKS, self.nbr_sent)
        self.assertEqual(NEW_LINKS+2, mock_copy.call_count,
                         'wrong number of copies, see profiles.toml')

    def test_run_download_failed(self):
        '''failed all downloads'''
        self.mock_db(FAKE_DB)
        self.mock_cli()
        self.sut.executor = MagicMock()
        self.sut.executor.call.side_effect = \
            lambda *args, **kwargs: 1  # @UnusedVariable
        mock_send = MagicMock(side_effect=self.bt_side_effect)
        bt = self.mock_sender(found=True, connect=True, send=mock_send)
        self.mock_remote_data()
        mock_copy = self.mock_shutil_copy()

        self.sut.run()

        self.assertEqual(0, self.nbr_downloaded)
        self.assertEqual(NEW_LINKS + 2, self.sut.executor.call.call_count,
                         'download does not cache failed attempts,'
                         'so it should called for every link in every profile')
        bt.assert_not_called()
        mock_send.assert_not_called()
        self.assertEqual(0, self.nbr_sent)
        self.assertEqual(0, mock_copy.call_count)

    @patch('bluetube.bluetube.CLI')
    def test_run_nothig_selected(self, cli):
        '''no selected videos to process'''
        cli.ask.return_value = False
        self.sut.event_listener = cli

        mdb = self.mock_db(FAKE_DB)
        self.mock_executor()
        mock_send = MagicMock(side_effect=self.bt_side_effect)
        bt = self.mock_sender(found=True, connect=True, send=mock_send)
        urlopen = self.mock_remote_data()

        self.sut.run()

        self.assertEqual(2, mdb.call_count,
                         'should be called for read and write')

        cli.inform.assert_any_call('feeds updated')
        self.assertEqual(urlopen.return_value.read.call_count,
                         FAKE_DB.count('"url"'))
        self.assertEqual(cli.ask.call_count, NEW_LINKS)
        bt.assert_not_called()
        self.assertEqual(mock_send.call_count, 0)

    def test_empty_DB(self):
        '''inform about the empty DB and do nothing'''
        mdb = self.mock_db({})
        self.mock_executor()
        cli = self.mock_cli()
        cli.inform = MagicMock()
        cli.feeds_updated = MagicMock()

        self.sut.run()

        mdb.assert_called_once()
        cli.inform.assert_any_call('empty database')
        cli.feeds_updated.assert_not_called()

    def test_add_playlist(self):
        self.mock_cli()
        d = {'feeds': []}
        self.mock_db(FAKE_DB, d)

        url = 'https://www.youtube.com/channel/UCSHZKyawb77ixDdsGog4iWA'
        out_format = 'video'
        profiles = ['profile_1', ]

        a = t = 'ТаТоТаке'
        for a, t in (('author1', 'title1'), (a, t)):
            parsed = type('mocked_feed',
                          (object,),
                          {'feed': type('mocked_pl',
                                        (object,),
                                        {'author': a, 'title': t})})
            with patch('feedparser.parse', return_value=parsed):
                self.sut.add_playlist(url, out_format, profiles)
                self.assertTrue(self.check_author_title(d['feeds'], a, t))

    def test_remove_playlist(self):
        self.mock_cli()
        d = {'feeds': []}
        self.mock_db(FAKE_DB, d)
        a = t = 'ТаТоТаке'
        self.sut.remove_playlist(a, t)
        self.assertTrue(len(d['feeds']))
        self.assertFalse(self.check_author_title(d['feeds'], a, t))

    def test_send(self):
        self.mock_db(FAKE_DB)
        cli = self.mock_cli()
        self.mock_listdir([])

        self.sut.send()
        cli.warn.assert_any_call('Nothing to send.')


class TestCli(unittest.TestCase):

    def setUp(self):
        self.sut = CLI(executor=MagicMock())

    def test_informs(self):
        with patch('builtins.print'):
            self.sut.inform('empty database')
            self.sut.inform('feed is fetching', 'a message')
            self.sut.inform('feed updated')
            self.sut.inform('an arbitrary message')
        self.sut._executor.call.assert_called_once()


if __name__ == "__main__":
    unittest.main()
