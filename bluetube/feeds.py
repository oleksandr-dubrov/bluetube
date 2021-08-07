import dbm
import functools
import os
import shelve

from bluetube import __version__
from bluetube.bcolors import Bcolors
from bluetube.model import OutputFormatType, Playlist

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
            @functools.wraps(func)
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
    def add_playlist(self, author, title, url, out_format, profiles):
        '''add a playlist'''
        pl = Playlist(title, url)
        pl.set_output_format_type(out_format)
        pl.profiles = profiles
        for a in self._feeds:
            if a['author'] == author:
                a['playlists'].append(pl)
                break
        else:
            self._feeds.append({'author': author,
                                'playlists': [pl]})
        self._push()

    @Decor.pull_if_needed
    def get_playlist(self, author, title):
        '''get a playlist'''
        for a in self._feeds:
            if a['author'] == author:
                pls = a['playlists']
                break
        else:
            return

        for pl in pls:
            if pl.title == title:
                return pl

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

    @Decor.pull_if_needed
    def has_playlist(self, author, title):
        a_t = {a['author']: [p.title for p in a['playlists']]
               for a in self._feeds}
        return author in a_t and title in a_t[author]

    @Decor.pull_if_needed
    def remove_playlist(self, author, title):
        '''remove the title of the author;
        remove the author if it has no more titles'''
        for a in self._feeds:
            if a['author'] == author:
                playlists = a['playlists']
                for ls in playlists:
                    if ls.title == title:
                        playlists.remove(ls)
                        if not len(playlists):
                            self._feeds.remove(a)
                        self._push()
                        return

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
                    pl.profiles = raw_pl['profiles']
                    pl.add_failed_entities(raw_pl.get('failed_entities', {}))
                    pls.append(pl)
                self._feeds.append({'author': author['author'],
                                    'playlists': pls})
            self._close(db)

    def _push(self):
        'push data to the db'
        db = self._create_rw_connector()
        res = []
        for author in self._feeds:
            o = {'author': author['author'], 'playlists': []}
            for ls in author['playlists']:
                o['playlists'].append(
                    {'title': ls.title,
                     'url': ls.url,
                     'last_update': ls.last_update,
                     'out_format': ls.output_format,
                     'profiles': ls.profiles,
                     'failed_entities': ls.failed_entities})
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


class SqlExporter(object):
    '''Export the DB to SQL'''

    DB_NAME = 'bluetube'
    ENGINE = 'ENGINE=INNODB'
    ID_INT = 'id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY'

    def __init__(self, feeds):
        self._feeds = feeds

    def export(self, file):
        '''export DB'''
        file.write(self._add_header())
        file.write(self._use_db())
        file.write(self._create_roles())
        file.write(self._create_users())
        file.write(self._create_authors())
        file.write(self._create_playlists())
        file.write(self._insert_authors_and_playlists())

    def _add_header(self):
        return f'/*\nBluetube {__version__} DB for MySQL.\n*/\n\n'

    def _use_db(self):
        return f'USE {SqlExporter.DB_NAME};\n'

    def _create_roles(self):
        r = ['']
        r.append('CREATE TABLE IF NOT EXISTS roles(')
        r.append('    id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,')
        r.append('    role CHAR(10) NOT NULL UNIQUE')
        r.append(f') {SqlExporter.ENGINE};')
        r.append('')
        r.append('INSERT INTO roles(id, role)')
        r.append("VALUES (1, 'admin'), (2, 'user');")
        r.append('')
        return '\n'.join(r)

    def _create_users(self):
        r = ['']
        r.append('CREATE TABLE IF NOT EXISTS users (')
        r.append(f'    {SqlExporter.ID_INT},')
        r.append('    name VARCHAR(100) NOT NULL,')
        r.append('    password VARCHAR(60) NOT NULL,')
        r.append('    email VARCHAR(100),')
        r.append('    role_id TINYINT UNSIGNED NOT NULL,')
        r.append('    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,')
        r.append('    FOREIGN KEY(role_id) REFERENCES roles(id)')
        r.append(f') {SqlExporter.ENGINE};')
        r.append('')
        r.append('INSERT INTO users(id, name, password, email, role_id)')
        r.append("VALUES (1, 'admin', 'admin', 'email@example.com', 1);")
        r.append('')
        return '\n'.join(r)

    def _create_authors(self):
        r = ['']
        r.append('CREATE TABLE IF NOT EXISTS authors(')
        r.append(f'    {SqlExporter.ID_INT},')
        r.append('    name VARCHAR(255) UNIQUE,')
        r.append('    user_id INT UNSIGNED NOT NULL,')
        r.append('    FOREIGN KEY(user_id) REFERENCES users(id)' +
                 ' ON UPDATE CASCADE ON DELETE CASCADE')
        r.append(f') {SqlExporter.ENGINE};')
        r.append('')
        return '\n'.join(r)

    def _create_playlists(self):
        r = ['']
        r.append('CREATE TABLE IF NOT EXISTS playlists(')
        r.append(f'    {SqlExporter.ID_INT},')
        r.append('    title VARCHAR(255) NOT NULL,')
        r.append('    URL VARCHAR(2048) NOT NULL,')
        r.append('    out_format CHAR(3) NOT NULL,')
        r.append('    last_update TIMESTAMP,')
        r.append('    author_id INT UNSIGNED NOT NULL,')
        r.append('    UNIQUE(title, author_id),')
        r.append('    FOREIGN KEY(author_id) REFERENCES authors(id)' +
                 'ON UPDATE CASCADE ON DELETE CASCADE')
        r.append(f') {SqlExporter.ENGINE};')
        r.append('')
        return '\n'.join(r)

    def _insert_authors_and_playlists(self):
        r = []
        for x in self._feeds:
            r.append('')
            author = x['author'].replace("'", "''")
            r.append("INSERT INTO authors(name, user_id)")
            r.append(f"VALUES ('{author}', 1);")
            r.append('SELECT LAST_INSERT_ID() INTO @author_id;')
            for y in x['playlists']:
                r.append('INSERT INTO playlists' +
                         '(title, URL, out_format, author_id)')
                a = OutputFormatType.audio
                nf = 'mp3' if y.output_format is a else 'mp4'
                title = y.title.replace("'", "''")
                r.append(f"VALUES ('{title}', '{y.url}', '{nf}', @author_id);")
        r.append('')
        return '\n'.join(r)
