import dbm
import os
import shelve

from bluetube.bcolors import Bcolors
from bluetube.model import Playlist

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

    DBFILENAME = 'bluetube.db'

    class Decor(object):
        @staticmethod
        def pull_if_needed(func):
            def wrapper(*args, **kwargs):
                self = args[0]
                if not len(self._feeds):
                    self._pull()
                return func(*args, **kwargs)
            return wrapper


    def __init__(self, db_dir):
        self.db_file = os.path.join(db_dir, Feeds.DBFILENAME)
        self._feeds = []

    @Decor.pull_if_needed
    def add_playlist(self, author, title, url, out_format):
        pl = Playlist(title, url)
        pl.set_output_format_type(out_format)
        self._feeds[author].append(pl)
        self._push()

    @Decor.pull_if_needed
    def get_all_playlists(self):
        '''get all playlists'''
        return self._feeds

    def set_all_playlists(self, pls):
        '''update playlists'''
        self._feeds = pls

    def sync(self):
        '''persist all playlists'''
        self._push()

    @Decor.pull_if_needed
    def get_authors(self):
        return [a['author'] for a in self._feeds]

    def has_playlist(self, author, title):
        if not len(self._feeds):
            self._pull()
        a_t = [{a['author']: [ p['title'] for p in a['playlists']]}
               for a in self._feeds]
        return author in a_t and title in a_t[author]

    def _pull(self):
        'pull data from the DB'
        db = self._create_ro_connector()
        if db:
            raw_feeds = db.get('feeds', [])
            for author in raw_feeds:
                pls = []
                for raw_pl in author['playlists']:
                    pl = Playlist(raw_pl['title'], raw_pl['url'])
                    pl.last_update = raw_pl['last_update']
                    pl.set_output_format_type(raw_pl['out_format'])
                    pl.profile = raw_pl['profiles']
                    pls.append(pl)
                self._feeds.append({'author': author['author'],
                                    'playlists': pls})
            self._close(db)

    def _push(self):
        'push data to the db'
        if not len(self._feeds):
            db = self._create_rw_connector()
            if db:
                res = []
                for author, pllst in self._feeds:
                    o = {'author': author, 'playlists': []}
                    for ls in pllst:
                        o['playlists'].append(
                            {'title': ls.title,
                             'url': ls.url,
                             'last_update': ls.last_update,
                             'out_format': ls.output_format,
                             'profile': ls.profile,
                             'failed_links': ls.failed_links})
                    res.append(o)
                db['feeds'] = res
                self._close(db)

    def _create_rw_connector(self):
        '''create DB connector in read/write mode'''
        return shelve.open(self.db_file, flag='c', writeback=False)

    def _create_ro_connector(self):
        '''create DB connector in read-only mode'''
        try:
            return shelve.open(self.db_file, flag='r')
        except dbm.error:
            return None

    def _close(self, db):
        try:
            db.close()
        except ValueError as e:
            Bcolors.error('Probably your changes were lost. Try again')
            raise e
