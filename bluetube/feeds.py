import os
import shelve
from .bcolors import Bcolors
from .model import Playlist


'''
    This file is part of Bluetube.

    Bluetube is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Bluetube is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Bluetube.  If not, see <https://www.gnu.org/licenses/>.
'''


class Feeds(object):
    '''Manages RSS feeds in the shelve database'''

    def __init__(self, db_dirs, mode='rw'):
        self.db = None
        self.db_file = os.path.join(db_dirs[0], 'bluetube.dat')
        if not (os.path.exists(self.db_file) and os.path.isfile(self.db_file)):
            self.db_file = os.path.join(db_dirs[1], 'bluetube.dat')
        if mode == 'r':
            self.db = self._create_ro_connector()
        elif mode == 'rw':
            self.db = self._create_rw_connector()
        else:
            assert 0, 'the access mode should be either "rw" or "r"'

    def __del__(self):
        if self.db:
            try:
                self.db.close()
            except ValueError as e:
                Bcolors.error('Probably your changes were lost. Try again')
                raise e

    def _create_rw_connector(self):
        '''create DB connector in read/write mode'''
        return shelve.open(self.db_file, flag='c', writeback=False)

    def _create_ro_connector(self):
        '''create DB connector in read-only mode'''
        if not os.path.isfile(self.db_file):
            self._create_empty_db()
        return shelve.open(self.db_file, flag='r')

    def _create_empty_db(self):
        db = self._create_rw_connector()
        db['feeds'] = []
        db.sync()

    def get_authors(self):
        if 'feeds' in self.db:
            return [a['author'] for a in self.db['feeds']]
        return []

    def get_playlists(self, author):
        authors = self.get_authors()
        if authors:
            for au in self.db['feeds']:
                if au['author'] == author:
                    return [ch['title'] for ch in au['playlists']]
        return []

    def has_playlist(self, author, playlist):
        if playlist in self.get_playlists(author):
            return True
        return False

    def add_playlist(self, author, title, url, out_format):
        feeds = self.get_all_playlists()

        # create a playlist
        playlist = {"title": title,
                    "url": url,
                    "last_update": 0,
                    "out_format": out_format}

        # insert the playlist into the author
        if author not in [f['author'] for f in feeds]:
            feeds.append({'author': author, 'playlists': []})
        for f in feeds:
            if f['author'] == author:
                f['playlists'].append(playlist)
                break

        self.write_to_db(feeds)

    def get_all_playlists(self):
        return self.db.get('feeds', [])

    def remove_playlist(self, author, title):
        feeds = self.get_all_playlists()
        for idx in range(len(feeds)):
            if feeds[idx]['author'] == author:
                for jdx in range(len(feeds[idx]['playlists'])):
                    if feeds[idx]['playlists'][jdx]['title'] == title:
                        del feeds[idx]['playlists'][jdx]
                        if len(feeds[idx]['playlists']) == 0:
                            del feeds[idx]
                        self.write_to_db(feeds)
                        return

    def write_to_db(self, feeds):
        if 'feeds' not in self.db:
            self.db['feeds'] = []
        self.db['feeds'] = feeds
        self.db.sync()

    def update_last_update(self, info):
        '''update last_update in a list by info'''
        feeds = self.get_all_playlists()
        for a in feeds:
            if a['author'] == info['author']:
                for ch in a['playlists']:
                    if ch['title'] == info['playlist']['title']:
                        ch['last_update'] = info['published_parsed']
                        self.write_to_db(feeds)
                        return


class Feeds2(object):
    '''Manages RSS feeds in the shelve database'''

    DBFILENAME = 'bluetube.dat'

    def __init__(self, db_dir):
        self.db_file = os.path.join(db_dir, Feeds2.DBFILENAME)
        self._feeds = []

    def add_playlist(self, author, title, url, out_format):
        if not len(self._feeds):
            self._pull()
        pl = Playlist(title, url)
        pl.set_output_format_type(out_format)
        self._feeds[author].append(pl)
        self._push()

    def get_all_playlists(self):
        if not len(self._feeds):
            self._pull()
        return self._feeds
    
    def get_authors(self):
        if not len(self._feeds):
            self._pull()
        return [a['author'] for a in self._feeds]

    def _pull(self):
        'pull data from the DB'
        db = self._create_ro_connector()
        if db:
            raw_feeds = db.get('feeds', [])
            for author in raw_feeds:
                for raw_pl in author['playlists']:
                    pl = Playlist(raw_pl['title'], raw_pl['url'])
                    pl.set_last_update(raw_pl['last_update'])
                    pl.set_output_format_type(raw_pl['out_format'])
                    self._feeds[author].append(pl)
            self._close(db)

    def _push(self):
        'push data to the db'
        if not len(self._feeds):
            db = self._create_rw_connector()
            if db:
                res = []
                for author, pllst in self._feeds:
                    o = {'author': author, 'playlists': []}
                    for l in pllst:
                        o['playlists'].append({'title': l.title,
                                               'url': l.url,
                                               'last_update': l.last_update,
                                               'out_format': l.output_format,
                                               'profile': l.profile})
                    res.append(o)
                db['feeds'] = res
                self._close(db)

    def _create_rw_connector(self):
        '''create DB connector in read/write mode'''
        return shelve.open(self.db_file, flag='c', writeback=False)

    def _create_ro_connector(self):
        '''create DB connector in read-only mode'''
        if not ( os.path.exists(self.db_file) and os.path.isfile(self.db_file)):
            return None
        return shelve.open(self.db_file, flag='r')

    def _close(self, db):
        try:
            db.close()
        except ValueError as e:
            Bcolors.error('Probably your changes were lost. Try again')
            raise e
