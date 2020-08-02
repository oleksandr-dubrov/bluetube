'''
Created on Aug 1, 2020

@author: olexandr
'''
import json
import unittest
from zipfile import ZipFile
from unittest.mock import patch, Mock
from bluetube import Bluetube


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


class Test(unittest.TestCase):

    def setUp(self):
        self.sut = Bluetube(verbose=True)


    def tearDown(self):
        pass

    @patch('bluetube.bluetube.CLI')
    @patch('shelve.open')
    def testRun(self, shelve, cli):
        md = read_mocked_data()
        mock_db = Mock()
        mock_db.get.return_value = json.loads('[{"playlists": [{"url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCemEkBcOpHNi1yZ4UjVi9EA", "out_format": "audio", "title": "ТаТоТаке", "last_update": 1595950278.0}], "author": "ТаТоТаке"}, {"playlists": [{"url": "https://www.youtube.com/feeds/videos.xml?playlist_id=PL9o6bQUWYNvLtTFwiVKY6Hpk7YaoJucsK", "out_format": "audio", "last_update": 1595433768.0, "title": "Безумный мир"}, {"url": "https://www.youtube.com/feeds/videos.xml?playlist_id=PL9o6bQUWYNvKejzvt2yclyZfJ-461xHB4", "out_format": "audio", "last_update": 1591785510.0, "title": "Право на гідність"}, {"url": "https://www.youtube.com/feeds/videos.xml?playlist_id=PL9o6bQUWYNvIetxWpnNeAAfkm6XRVkmCg", "out_format": "video", "title": "Диктатори", "last_update": 1583842878.0}, {"url": "https://www.youtube.com/feeds/videos.xml?playlist_id=PL9o6bQUWYNvIdr0SM0yU4OEEOQV4JorVa", "out_format": "audio", "title": "Финансовая грамотность", "last_update": 1592806397.0}, {"url": "https://www.youtube.com/feeds/videos.xml?playlist_id=PL9o6bQUWYNvLV7m3tATsU1Fodjy7ZGxXM", "out_format": "audio", "last_update": 1595914123.0, "title": "Чесна політика"}, {"url": "https://www.youtube.com/feeds/videos.xml?playlist_id=PL9o6bQUWYNvLX5jNrxI6LLI2-8t61Y5ql", "out_format": "audio", "last_update": 1595669945.0, "title": "Право на правду"}, {"url": "https://www.youtube.com/feeds/videos.xml?playlist_id=PL9o6bQUWYNvKDg0QIffdd2u2oYKXpg2lY", "out_format": "audio", "last_update": 1579761625.0, "title": "Що це було ?"}, {"url": "https://www.youtube.com/feeds/videos.xml?playlist_id=PL9o6bQUWYNvK1kz-Vifj4XSbg0ezMllJV", "out_format": "video", "last_update": 1595868497.0, "title": "Конфлікти"}, {"url": "https://www.youtube.com/feeds/videos.xml?playlist_id=PL9o6bQUWYNvJFiB30Tg_nNDKE3-T0ImI8", "out_format": "audio", "title": "Корпорації світу", "last_update": 1592143016.0}], "author": "24 Канал"}]')
        shelve.return_value = mock_db
        
        cli.ask.return_value = True
        self.sut.event_listener = cli
        with patch('urllib.request.urlopen') as urlopen:
            urlopen.return_value = Mock()
            urlopen.return_value.read.side_effect = [l.encode() for l in md]
            self.sut.run()


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()