import datetime
import io
import json
import os
import shutil
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from zipfile import ZipFile

from bluetube import Bluetube
from bluetube.commandexecutor import cache
from bluetube.model import OutputFormatType
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
        Bluetube._get_bt_dir = lambda _, __: \
            os.path.dirname(os.path.abspath(__file__))
        self.mock_executor()
        self.sut = Bluetube(verbose=False)
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
        in_patcher = patch('bluetube.componentfactory.Inputer')
        inp = in_patcher.start()
        inp.ask.return_value = True
        self.sut.inputer = inp

        out_patcher = patch('bluetube.componentfactory.Outputer')
        out = out_patcher.start()
        self.sut._subscribers.append(out)

        return inp, out

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

        if args[0][0] in ['youtube-dl', 'yt-dlp']:
            fake_name = args[0][-1].split('=')[1]
            open(os.path.join(kwargs.get('cwd', TestBluetube.TMP_DIR),
                              fake_name), 'w').close()
            self.nbr_downloaded += 1
        elif args[0][0] == 'ffmpeg':
            open(os.path.join(kwargs.get('cwd', TestBluetube.TMP_DIR),
                              args[0][-1]), 'w').close()
            self.nbr_converted += 1
        return 0

    def mock_executor(self):
        '''mock the command executor'''
        patcher = patch('bluetube.componentfactory.CommandExecutor')
        mocked_executor_class = patcher.start()
        instance = mocked_executor_class.return_value
        instance.call.side_effect = self.call_side_effect
        instance.does_command_exist.return_value = True
        return instance

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
        '''mock remote data returned'''
        mocked_fetch = AsyncMock()
        md = read_mocked_data()
        mocked_fetch.side_effect = [ln.encode() for ln in md]
        self.sut._fetch_rss = mocked_fetch
        return mocked_fetch

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
        inp, _ = self.mock_cli()
        mock_send = MagicMock(side_effect=self.bt_side_effect)
        bt = self.mock_sender(found=True, connect=True, send=mock_send)
        fetch = self.mock_remote_data()
        mock_copy = self.mock_shutil_copy()

        self.sut.run()

        self.assertEqual(2, mdb.call_count,
                         'should be called for read and write')

        self.assertEqual(fetch.await_count, FAKE_DB.count('"url"'))

        self.assertEqual(inp.ask.call_count, NEW_LINKS)

        self.assertEqual(NEW_LINKS, self.nbr_downloaded)
        self.assertEqual(self.nbr_downloaded + self.nbr_converted,
                         self.sut.factory._executor.call.call_count)

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
        self.sut.factory._executor = MagicMock()
        self.sut.factory._executor.call.side_effect = \
            lambda *args, **kwargs: 1  # @UnusedVariable
        mock_send = MagicMock(side_effect=self.bt_side_effect)
        bt = self.mock_sender(found=True, connect=True, send=mock_send)
        self.mock_remote_data()
        mock_copy = self.mock_shutil_copy()

        self.sut.run()

        self.assertEqual(0, self.nbr_downloaded)
        self.assertEqual(NEW_LINKS + 2,
                         self.sut.factory._executor.call.call_count,
                         'download does not cache failed attempts,'
                         'so it should called for every link in every profile')
        bt.assert_not_called()
        mock_send.assert_not_called()
        self.assertEqual(0, self.nbr_sent)
        self.assertEqual(0, mock_copy.call_count)

    @patch('bluetube.componentfactory.Inputer')
    def test_run_nothing_selected(self, cli):
        '''no selected videos to process'''
        cli.ask.return_value = False
        self.sut.inputer = cli
        self.sut.outputer = MagicMock()

        mdb = self.mock_db(FAKE_DB)
        self.mock_executor()
        mock_send = MagicMock(side_effect=self.bt_side_effect)
        bt = self.mock_sender(found=True, connect=True, send=mock_send)
        fetch = self.mock_remote_data()

        self.sut.run()

        self.assertEqual(2, mdb.call_count,
                         'should be called for read and write')

        self.assertEqual(fetch.await_count, FAKE_DB.count('"url"'))
        self.assertEqual(cli.ask.call_count, NEW_LINKS)
        bt.assert_not_called()
        self.assertEqual(mock_send.call_count, 0)

    def test_empty_DB(self):
        '''inform about the empty DB and do nothing'''
        mdb = self.mock_db({})
        self.mock_executor()
        _, out = self.mock_cli()

        self.sut.run()

        mdb.assert_called_once()
        self.assertEqual(2, out.update.call_count)  # 1st is 'Updating feeds.'
        self.assertEquals('empty database', out.update.call_args[0][0].msg)
        out.feeds_updated.assert_not_called()

    def test_add_playlist(self):
        self.mock_cli()
        d = {'feeds': []}
        self.mock_db(FAKE_DB, d)

        url = 'https://www.youtube.com/channel/UCSHZKyawb77ixDdsGog4iWA'
        out_format = 'video'
        profiles = ['profile_1', ]

        a = t = 'ТаТоТаке'
        em = "\U0001F612"
        for a, t in (('author1', 'title1'), (a, t)):
            parsed = type('mocked_feed',
                          (object,),
                          {'feed': type('mocked_pl',
                                        (object,),
                                        # check that emojies are cut off
                                        {'author': a+em,
                                         'title': t+em})})
            with patch('feedparser.parse', return_value=parsed):
                self.sut.add_playlist(url, out_format, profiles)
                self.assertTrue(self.check_author_title(d['feeds'],
                                                        a+"□",
                                                        t+"□"))

    def test__get_feed_url(self):
        '''test possible URLs of playlists'''
        exp_id = 'UCSHZKyawb77ixDdsGog4iWA'
        urls = [
            'youtube.com/channel/UCSHZKyawb77ixDdsGog4iWA',
            'https://www.youtube.com/channel/UCSHZKyawb77ixDdsGog4iWA',
            'https://www.youtube.com/channel/UCSHZKyawb77ixDdsGog4iWA/video',
            'youtube.com/playlist?list=UCSHZKyawb77ixDdsGog4iWA&playnext=1' +
            '&index=1',
            'https://www.youtube.com/watch?v=qZmkoV6U_qw&list' +
            '=UCSHZKyawb77ixDdsGog4iWA&index=4',
            ]
        for u in urls:
            feed = self.sut._get_feed_url(u)
            self.assertTrue(exp_id in feed, f"unexpected feed for {u}")

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
        _, out = self.mock_cli()
        self.mock_listdir([])

        self.sut.send()
        out.update.assert_called_once()
        self.assertEquals('Nothing to send.', out.update.call_args[0][0].msg)

    def test_edit_playlist(self):
        _, out = self.mock_cli()
        d = {'feeds': []}
        self.mock_db(FAKE_DB, d)
        a = '24 Канал'
        t = 'Чесна політика'

        self.sut.edit_playlist(a, t)
        out.update.assert_called_once()
        out.reset_mock()

        orig_db = json.loads(FAKE_DB)
        old_last_update = orig_db[1]['playlists'][1]['last_update']
        self.sut.edit_playlist(a, t, output_type=OutputFormatType.video,
                               profiles=('mobile', 'local'),
                               reset_failed=True,
                               days_back=90)
        out.warn.assert_not_called()
        pl = d['feeds'][1]['playlists'][1]
        self.assertEqual(old_last_update - pl['last_update'],
                         datetime.timedelta(days=int(90)).total_seconds(),
                         'unexpected last update')


if __name__ == "__main__":
    unittest.main()
