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


import asyncio
import copy
import datetime
import logging
import os
import re
import shutil
import signal
import tempfile
import time
from typing import NoReturn
from urllib.error import HTTPError

import aiohttp
import feedparser

from bluetube.bluetoothclient import BluetoothClient
from bluetube.cli.events import Error, Event, Info, Success, Warn
from bluetube.cli.inputer import Inputer
from bluetube.componentfactory import ComponentFactory
from bluetube.configs import Configs
from bluetube.eventpublisher import EventPublisher
from bluetube.feeds import Feeds, SqlExporter
from bluetube.model import OutputFormatType, Playlist
from bluetube.profiles import Profiles, ProfilesException
from bluetube.utils import deemojify


class Bluetube(EventPublisher):
    ''' The main class of the script. '''

    CONFIG_FILE_NAME = 'bluetube.cfg'
    HOME_DIR = os.path.expanduser(os.path.join('~', '.bluetube'))
    ACCESS_MODE = 0o744

    def signal_handler(self, signum, _) -> NoReturn:
        '''Ctrl+c handler to quit the tool'''
        assert signum == signal.SIGINT, 'SIGINT expected in the handler'
        self.notify(Warn('Quit!'))
        os._exit(1)

    def __init__(self, home_dir=None, verbose=False, yes=False):
        super().__init__()

        self._config_logger(verbose)
        self._debug = logging.getLogger(__name__).debug
        signal.signal(signal.SIGINT, self.signal_handler)
        self.senders = {}
        self.factory = ComponentFactory()
        self.executor = self.factory.get_command_executor()
        self.inputer = self.factory.get_inputer(yes)
        self.temp_dir = None
        self.bt_dir = self._get_bt_dir(home_dir)

        self.subscribe(self.factory.get_outputer())

    def add_playlist(self, url, out_format, profiles):
        ''' add a new playlists to RSS feeds '''
        feed_url = self._get_feed_url(url)
        if not feed_url:
            return
        f = feedparser.parse(feed_url)
        title = deemojify(f.feed.title)
        author = deemojify(f.feed.author)
        feeds = Feeds(self.bt_dir)
        if feeds.has_playlist(author, title):
            event = Error('playlist exists', title, author)
        else:
            feeds.add_playlist(author, title, feed_url, out_format, profiles)
            event = Success('added', title, author)
        self.notify(event)

    def list_playlists(self):
        ''' list all playlists in RSS feeds '''
        feeds = Feeds(self.bt_dir)
        all_playlists = feeds.get_all_playlists()
        if len(all_playlists):
            for a in all_playlists:
                print(a['author'])
                for c in a['playlists']:
                    out_type = OutputFormatType.to_char(c.output_format)
                    profiles = ', '.join(c.profiles)
                    o = f"{' ' * 10}{c.title} |{out_type}, {profiles}|"
                    t = time.strftime('%Y-%m-%d %H:%M:%S',
                                      time.localtime(c.last_update))
                    o = f'{o} ({t})'
                    print(o)
        else:
            self.notify(Info('empty database'))

    def remove_playlist(self, author, title):
        ''' remove the playlist of the given author'''
        feeds = Feeds(self.bt_dir)
        if feeds.has_playlist(author, title):
            feeds.remove_playlist(author, title)
        else:
            self.notify('playlist not found', title, author)

    def run(self):
        ''' The main method. It does everything.'''

        self._debug(f'Bluetube home directory: {self.bt_dir}.')

        # self._check_media_player()

        feed = Feeds(self.bt_dir)
        pls = self._get_list(feed)

        if len(pls):
            self.notify(Success('feeds updated'))
        else:
            self.notify(Info('empty database'))
            return

        profiles = self._get_profiles(self.bt_dir)

        self._fetch_temp_dir()

        pls = self._process_playlists(pls)

        for pl in pls:
            if not self._check_profiles(pl, profiles):
                continue

            # combine entities (links with metadata to download) with profiles
            pl.entities = {profile: copy.deepcopy(pl.entities)
                           for profile in pl.profiles}

            # prepend previously failed entities
            for pr in pl.entities:
                if pr in pl.failed_entities:
                    pl.entities[pr] = pl.failed_entities[pr] + pl.entities[pr]
                    del pl.failed_entities[pr]

            self._debug(f"process {pl}")

            self._download_list(pl, profiles)

            self._convert_list(pl, profiles)

            self._send_list(pl, profiles)

        feed.set_all_playlists(self._prepare_list(pls))
        feed.sync()
        self._return_temp_dir()

    def send(self):
        '''send files from the bluetube download directory
        to all bluetooth devices'''
        profiles = self._get_profiles(self.bt_dir)
        self._fetch_temp_dir()
        if os.listdir(self.temp_dir):
            sent = []
            nbr_divices = 0
            for profile in profiles.get_profiles():
                s_op = profiles.get_send_options(profile)
                if s_op and 'bluetooth_device_id' in s_op:
                    sender = self._get_sender(s_op['bluetooth_device_id'])
                    if sender and sender.found:
                        nbr_divices += 1
                        sent += self._send_all_in_dir(sender)
                    else:
                        msg = 'Your bluetooth device is not accessible.'
                        self.notify(Error(msg))

            # remove the files that have been sent to all devices
            counts = {x: sent.count(x) for x in sent}
            for f, n in counts.items():
                if n == nbr_divices:
                    os.remove(f)
        else:
            self.notify(Warn('Nothing to send.'))
        self._return_temp_dir()

    def edit_profiles(self):
        '''open a profiles file and check after edit'''
        bt_dir = self.bt_dir
        Profiles.create_profiles_if_not_exist(bt_dir)
        self._edit_profiles()
        try:
            profiles = Profiles(bt_dir)
        except ProfilesException as e:
            self.notify(Error(e))
            self.notify(Error('edit profile filed'))
            return
        for pr in profiles.get_profiles():
            try:
                profiles.check_require_converter_configurations(pr)
                profiles.check_send_configurations(pr)
            except ProfilesException as e:
                self.notify(Error(e))
                msg = f'Profile "{pr}" are not configured properly. Try again.'
                self.notify(Warn(msg))

    def edit_playlist(self, author, title, output_type=None,
                      profiles=None, reset_failed=None, days_back=None):
        '''edit a playlist'''
        def print_help():
            prs = ' | '.join(Profiles(self.bt_dir).get_profiles())
            msg = 'Run this command with one or all options below:\n' \
                  f'-t (a or v) -pr ({prs})\n' \
                  '-r (to reset previously failed videos)' \
                  ' -d N (to set last updated date to N days before)'
            self.notify(Warn(msg))

        feed = Feeds(self.bt_dir)
        if feed.has_playlist(author, title):
            pl = feed.get_playlist(author, title)
            assert pl, 'no playlist'
            if not any((output_type, profiles, reset_failed, days_back)):
                print_help()
            elif profiles \
                and not all([p in Profiles(self.bt_dir).get_profiles()
                             for p in profiles]):
                print_help()
            else:
                if isinstance(output_type, OutputFormatType):
                    pl.output_format = output_type
                if profiles:
                    pl.profiles = profiles
                if reset_failed:
                    del pl.failed_entities
                if days_back:
                    delta = datetime.timedelta(days=int(days_back))
                    pl.last_update -= delta.total_seconds()
                feed.sync()
                self._debug('Done.')
        else:
            event = Error('playlist not found', title, author)
            self.notify(event)

    def open_more_help(self):
        '''open more help information'''
        link = ['https://github.com/oleksandr-dubrov',
                '/bluetube/blob/master/README.md']
        self.executor.open_url(''.join(link))

    def export_db(self):
        '''export DB into the bluetube.sql file for SQLite3'''
        feed = Feeds(self.bt_dir)
        exporter = SqlExporter(feed.get_all_playlists())
        with open('bluetube.sql', 'w') as f:
            exporter.export(f)

    def _send_all_in_dir(self, sender):
        '''send all files in the given directory'''
        sent = []
        files = os.listdir(self.temp_dir)
        for fl in files:
            if fl.endswith('.part') or fl.endswith('.ytdl'):
                # remove:
                #        partially downloaded files
                #        youtube-dl service files
                os.remove(os.path.join(self.temp_dir, fl))
        files = os.listdir(self.temp_dir)  # update the list of files
        if sender.found and sender.connect():
            sent += sender.send(files)
            sender.disconnect()
        return sent

    def _get_profiles(self, bt_dir):
        def get_instance():
            try:
                return Profiles(bt_dir)
            except ProfilesException as e:
                self.notify(Error(e))
                self.notify(Warn('Try to reinstall the application.'))
                raise

        profiles = get_instance()
        if self._check_profiles_consistency(profiles):
            return profiles
        else:
            if Inputer.do_continue():
                self._edit_profiles()
                # try to load profiles one more time
                profiles = get_instance()
                if self._check_profiles_consistency(profiles):
                    return profiles
            raise ProfilesException('invalid profile')

    def _get_list(self, feed: Feeds) -> list[Playlist]:
        '''Fetch and parse RSS data for all lists.'''
        pls = feed.get_all_playlists()

        async def task(session, author):
            '''task that fetches RSS for the author'''
            events: list[Event] = [Info(author['author'], capture='RSS')]
            for pl in author['playlists']:
                events.append(Info('feed is fetching',
                                   pl.title, capture='RSS'))
                response = await self._fetch_rss(session, pl)
                pl.feedparser_data = feedparser.parse(response)
                pl.author = author['author']
            return events

        async def process_tasks():
            '''process all async tasks'''
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                return await asyncio.gather(*[task(session, a) for a in pls],
                                            return_exceptions=False)

        self.notify(Info('Updating feeds...'))
        events = asyncio.run(process_tasks())
        for event in events:  # handles all event collected in the event loop
            for e in event:
                self.notify(e)

        pls = [pl for a in pls for pl in a['playlists']]  # make the list flat
        return pls

    async def _fetch_rss(self, session, pl):
        '''get URLs from the RSS
        that the user will selected for every playlist'''
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        try:
            async with session.get(pl.url, headers=headers) as response:
                response = await response.text()
        except HTTPError as e:
            self.notify(Error(e))  # notify the error immidiatelly
            response = ''
        return response

    def _process_playlists(self, pls):
        '''ask the user what to do with the entities'''
        ret = []
        for pl in pls:
            ret.append(self._process_playlist(pl))
        return ret

    def _download_list(self, pl, profiles):
        # keep path to successfully downloaded files for all profiles here
        downloader = self.factory.get_downloader(self, self.temp_dir)

        for profile, entities in pl.entities.items():
            if pl.output_format is OutputFormatType.audio:
                dl_op = profiles.get_audio_options(profile)
            elif pl.output_format is OutputFormatType.video:
                dl_op = profiles.get_video_options(profile)
            else:
                assert 0, 'unexpected output format type'

            s, f = downloader.download(entities,
                                       pl.output_format,
                                       dl_op)
            pl.entities[profile] = s
            if f:
                ens = [e.title for e in f]
                ens = ', '.join(ens)
                event = Error('failed to download', ens, profile)
                self.notify(event)
            pl.add_failed_entities({profile: f})

    def _convert_list(self, pl, profiles):
        # convert video, audio has been converted by the downloader
        converter = self.factory.get_converter(self, self.temp_dir)
        if pl.output_format is OutputFormatType.video:
            for profile, entities in pl.entities.items():
                c_op = profiles.get_convert_options(profile)
                if not c_op:
                    return
                v_op = profiles.get_video_options(profile)
                # convert unless the video has not been downloaded in
                # proper format
                if not c_op['output_format'] == v_op['output_format']:
                    s, f = converter.convert(entities, c_op)
                    pl.entities[profile] = s
                    if f and Inputer.do_continue():
                        return

    def _send_list(self, pl, profiles):
        for profile, entities in pl.entities.items():
            s_op = profiles.get_send_options(profile)
            links = [e['link'] for e in entities]
            if not s_op or not links:
                continue
            processed = []

            # send via bluetooth
            device_id = s_op.get('bluetooth_device_id')
            if device_id:
                sent = self._send_bt(device_id, links)
                processed.append(sent)

            # move to local directory
            local_path = s_op.get('local_path')
            if local_path:
                try:
                    os.makedirs(local_path,
                                Bluetube.ACCESS_MODE,
                                exist_ok=True)
                except PermissionError as e:
                    self.notify(Error(e))
                    continue
                copied = self._copy_to_local_path(local_path, links)
                processed.append(copied)

            for en in entities:
                lnk = en['link']
                if all([lnk in pr for pr in processed]):
                    try:
                        os.remove(os.path.join(self.temp_dir, lnk))
                    except FileNotFoundError:
                        pass  # ignore this exception
                else:
                    self._debug(f'{lnk} has not been sent')

    def _send_bt(self, device_id, links):
        '''sent all files defined by the links
        to the device defined by device_id'''
        sent = []
        sender = self._get_sender(device_id)
        if sender and sender.found and sender.connect():
            sent += sender.send(links)
            sender.disconnect()
        return sent

    def _copy_to_local_path(self, local_path, links):
        '''copy files defined by links to the local path'''
        copied = []
        for ln in links:
            self._debug(f'copying {ln} to {local_path}')
            try:
                shutil.copy2(os.path.join(self.temp_dir, ln), local_path)
                copied.append(ln)
            except shutil.SameFileError as e:
                self.notify(Error(e))
        return copied

    def _get_sender(self, device_id):
        '''return a sender from the cache for a device ID if possible
        or create a new one'''
        if device_id in self.senders:
            return self.senders[device_id]
        else:
            sender = BluetoothClient(device_id, self.temp_dir)
            if not sender.found:
                self.notify(Error('device not found'))
                return None
            else:
                self.senders[device_id] = sender
                return sender

    def _check_profiles(self, pl, profiles):
        '''check if profiles of the playlist do exist'''
        def check_profiles_internal(profile):
            if not profiles.check_profile(profile):
                event = Error('profile not found',
                              profile,
                              pl.title,
                              pl.author)
                self.notify(event)
                all_pr = ', '.join(profiles.get_profiles())
                self.notify(Warn(f'Possible profiles - {all_pr}.'))
                event = Info('This playlist is skipped.\n'
                             'Edit the playlist and try again')
                self.notify(event)
                return False
            return True

        return all([check_profiles_internal(pr) for pr in pl.profiles])

    def _check_profiles_consistency(self, profiles):
        '''check if profiles are configured properly'''

        for pr in profiles.get_profiles():
            try:
                profiles.check_require_converter_configurations(pr)
                profiles.check_send_configurations(pr)
            except ProfilesException as e:
                self.notify(Error(e))
                msg = f'Profile "{pr}" are not configured properly'
                self.notify(Warn(msg))
                return False

        return True

    def _check_media_player(self):
        configs = Configs(self.bt_dir)
        mp = configs.get_media_player()
        if mp and mp != '-':
            self.inputer.set_media_player(mp)
        elif mp == '-':
            return
        else:
            self.notify(Warn('no media player'))

            def set_media_player():
                mp = self.inputer.arbitrary_input()
                if mp == '-' or self.executor.does_command_exist(mp):
                    configs.set_media_player(mp)
                    self.inputer.set_media_player(mp)
                else:
                    self.notify(Error(f'"{mp}" not found. Try again.'))
                    set_media_player()
            set_media_player()

    def _edit_profiles(self) -> None:
        '''try to open the profile file in a text editor'''
        configs = Configs(self.bt_dir)
        ed = configs.get_editor()
        if ed:
            self.executor.call((ed, Profiles.PROFILES_NAME),
                               self.bt_dir,
                               suppress_stdout=False,
                               suppress_stderr=False)
        else:
            self.notify(Warn('no editor'))

            def set_editor():
                ed = self.inputer.arbitrary_input()
                if self.executor.does_command_exist(ed):
                    configs.set_editor(ed)
                else:
                    self.notify(Error(f'"{ed}" not found. Try again.'))
                    set_editor()
            set_editor()

    def _get_feed_url(self, url):
        p1 = re.compile(r'^(?:.*?)youtube\.com/' +
                        r'watch\?v=.+&list=(.+?)(?:&.*)?$')
        p2 = re.compile(r'^(?:.*?)youtube\.com/playlist\?list=(.+?)(?:&.*)?$')
        m = p1.match(url)
        if not m:
            m = p2.match(url)
        if m:
            msg = 'https://www.youtube.com/feeds/videos.xml?playlist_id={}'
            return msg.format(m.group(1))
        else:
            p = re.compile(r'^(?:.*?)youtube\.com/channel/(.+?)(/.*)?$')
            m = p.match(url)
            if m:
                msg = 'https://www.youtube.com/feeds/videos.xml?channel_id={}'
                return msg.format(m.group(1))
            self.notify(Error('misformatted URL'))
            return None

    def _prepare_list(self, pls):
        ret = {}
        for pl in pls:
            ret.setdefault(pl.author, [])
            ret[pl.author].append(pl)
            del pl.author
        return [{'author': a, 'playlists': ret[a]} for a in ret]

    def _process_playlist(self, pl):
        '''process the playlist'''
        entities = []
        channel_has_update = False
        new_last_update = last_update = pl.last_update
        assert pl.feedparser_data is not None, 'fetch RSS first'
        for e in pl.feedparser_data.entries:
            e_update = time.mktime(e['published_parsed'])
            if last_update < e_update:
                if not channel_has_update:
                    self.notify(Info(pl.author))
                    channel_has_update = True
                if self.inputer.ask(e):
                    entities.append(e)
                if new_last_update < e_update:
                    new_last_update = e_update
        pl.last_update = new_last_update
        pl.entities = entities
        return pl

    def _fetch_temp_dir(self):
        '''fetch a temporal directory;
        don't forget to return'''
        temp_dir = os.path.join(tempfile.gettempdir(), 'bluetube')
        if not os.path.isdir(temp_dir):
            os.mkdir(temp_dir)
        else:
            fs = os.listdir(temp_dir)
            if len(fs):
                msg = 'Ready to be sent:\n{}'.format('\n'.join(fs))
                self.notify(Warn(msg))
        self.temp_dir = temp_dir

    def _return_temp_dir(self):
        assert self.temp_dir, 'nothing to return, call fetch'
        if os.path.isdir(self.temp_dir):
            try:
                os.rmdir(self.temp_dir)
            except OSError:
                event = Warn('download directory not empty', self.temp_dir)
                self.notify(event)
                event = Warn('\n  '.join(os.listdir(self.temp_dir)))
                self.notify(event)

    def _get_bt_dir(self, home_dir):
        bt_dir = home_dir if home_dir else Bluetube.HOME_DIR
        if not os.path.exists(bt_dir) or not os.path.isdir(bt_dir):
            os.makedirs(bt_dir, Bluetube.ACCESS_MODE)
        return bt_dir

    def _config_logger(self, verbose: bool) -> None:
        level = logging.DEBUG if verbose else logging.WARNING
        f = '[verbose] %(name)s - %(message)s'
        logging.basicConfig(format=f, level=level)
