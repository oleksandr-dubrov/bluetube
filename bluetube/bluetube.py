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


import copy
import datetime
import io
import os
import re
import shutil
import signal
import tempfile
import time
import urllib
from urllib.error import HTTPError

import feedparser
from mutagen import MutagenError, id3, mp3, mp4

from bluetube.bluetoothclient import BluetoothClient
from bluetube.cli import CLI
from bluetube.commandexecutor import CommandExecutor
from bluetube.configs import Configs
from bluetube.feeds import Feeds
from bluetube.model import OutputFormatType
from bluetube.profiles import Profiles, ProfilesException


class Bluetube(object):
    ''' The main class of the script. '''

    CONFIG_FILE_NAME = 'bluetube.cfg'
    HOME_DIR = os.path.expanduser(os.path.join('~', '.bluetube'))
    DOWNLOADER = 'youtube-dl'
    CONVERTER = 'ffmpeg'
    ACCESS_MODE = 0o744
    # keep files that failed to be converted here
    NOT_CONV_DIR = '[not yes converted files]'

    def signal_handler(self, signum, _):
        '''Ctrl+c handler to quit the tool'''
        assert signum == signal.SIGINT, 'SIGINT expected in the handler'
        self.event_listener.warn('Quit!')
        os._exit(1)

    def __init__(self, home_dir=None, verbose=False):
        signal.signal(signal.SIGINT, self.signal_handler)
        self.verbose = verbose
        self.senders = {}
        self.executor = CommandExecutor(verbose)
        self.event_listener = CLI(self.executor)
        self.temp_dir = None
        self.bt_dir = self._get_bt_dir(home_dir)

    def add_playlist(self, url, out_format, profiles):
        ''' add a new playlists to RSS feeds '''
        feed_url = self._get_feed_url(url)
        f = feedparser.parse(feed_url)
        title = f.feed.title
        author = f.feed.author
        feeds = Feeds(self.bt_dir)
        if feeds.has_playlist(author, title):
            self.event_listener.error('playlist exists', title, author)
        else:
            feeds.add_playlist(author, title, feed_url, out_format, profiles)
            self.event_listener.success('added', title, author)

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
                    if self.verbose:
                        t = time.strftime('%Y-%m-%d %H:%M:%S',
                                          time.localtime(c.last_update))
                        o = f'{o} ({t})'
                    print(o)
        else:
            self.event_listener.inform('empty database')

    def remove_playlist(self, author, title):
        ''' remove the playlist of the given author'''
        feeds = Feeds(self.bt_dir)
        if feeds.has_playlist(author, title):
            feeds.remove_playlist(author, title)
        else:
            self.event_listener.error('playlist not found', title, author)

    def run(self):
        ''' The main method. It does everything.'''

        if self.verbose:
            self._dbg(f'Bluetube home directory: {self.bt_dir}.')

        if not self._check_downloader():
            self.event_listener.error('downloader not found',
                                      Bluetube.DOWNLOADER)
            return
        if not self._check_video_converter():
            return
        self._check_media_player()

        feed = Feeds(self.bt_dir)
        pls = self._get_list(feed)

        if len(pls):
            self.event_listener.success('feeds updated')
        else:
            self.event_listener.inform('empty database')
            return

        profiles = self._get_profiles(self.bt_dir)

        self._fetch_temp_dir()

        pls = self._proccess_playlists(pls)

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
                        self.event_listener.error(msg)

            # remove the files that have been sent to all devices
            counts = {x: sent.count(x) for x in sent}
            for f, n in counts.items():
                if n == nbr_divices:
                    os.remove(f)
        else:
            self.event_listener.warn('Nothing to send.')
        self._return_temp_dir()

    def edit_profiles(self):
        '''open a profiles file and check after edit'''
        bt_dir = self.bt_dir
        Profiles.create_profiles_if_not_exist(bt_dir)
        self._edit_profiles()
        try:
            profiles = Profiles(bt_dir)
        except ProfilesException as e:
            self.event_listener.error(e)
            self.event_listener.error('edit profile filed')
            return
        for pr in profiles.get_profiles():
            try:
                profiles.check_require_converter_configurations(pr)
                profiles.check_send_configurations(pr)
            except ProfilesException as e:
                self.event_listener.error(e)
                msg = f'Profile "{pr}" are not configured properly. Try again.'
                self.event_listener.warn(msg)

    def edit_playlist(self, author, title, output_type=None,
                      profiles=None, reset_failed=None, days_back=None):
        '''edit a playlist'''
        def print_help():
            prs = ' | '.join(Profiles(self.bt_dir).get_profiles())
            msg = 'Run this command with one or all options below:\n' \
                  f'-t (a or v) -pr ({prs})\n' \
                  '-r (to reset previously failed videos)' \
                  ' -d N (to set last updated date to N days before)'
            self.event_listener.warn(msg)

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
                if self.verbose:
                    self._dbg('Done.')
        else:
            self.event_listener.error('playlist not found', title, author)

    def open_more_help(self):
        '''open more help information'''
        link = ['https://github.com/oleksandr-dubrov',
                '/bluetube/blob/master/README.md']
        self.executor.open_url(''.join(link))

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
                self.event_listener.error(e)
                self.event_listener.warn('Try to reinstall the application.')
                raise

        profiles = get_instance()
        if self._check_profiles_consistency(profiles):
            return profiles
        else:
            if self.event_listener.do_continue():
                self._edit_profiles()
                # try to load profiles one more time
                profiles = get_instance()
                if self._check_profiles_consistency(profiles):
                    return profiles
            raise ProfilesException('invalid profile')

    def _get_list(self, feed):
        '''fetch and parse RSS data for all lists'''
        pls = feed.get_all_playlists()
        fetch_rss = self._get_rss_fetcher()
        for a in pls:
            self.event_listener.inform(a['author'], capture='RSS')
            for pl in a['playlists']:
                fetch_rss(pl)
                pl.author = a['author']
        pls = [pl for a in pls for pl in a['playlists']]  # make the list flat
        return pls

    def _proccess_playlists(self, pls):
        '''ask the user what to do with the entities'''
        ret = []
        for pl in pls:
            ret.append(self._process_playlist(pl))
        return ret

    def _download_list(self, pl, profiles):
        # keep path to successfully downloaded files for all profiles here
        cache = {}
        for profile, entities in pl.entities.items():
            if pl.output_format is OutputFormatType.audio:
                dl_op = profiles.get_audio_options(profile)
            elif pl.output_format is OutputFormatType.video:
                dl_op = profiles.get_video_options(profile)
            else:
                assert 0, 'unexpected output format type'

            s, f = self._download(entities,
                                  pl.output_format,
                                  dl_op,
                                  cache)
            pl.entities[profile] = s
            if f:
                ens = [e.title for e in f]
                ens = ', '.join(ens)
                self.event_listener.error('failed to download',
                                          ens, profile)
            pl.add_failed_entities({profile: f})

    def _convert_list(self, pl, profiles):
        # convert video, audio has been converted by the downloader
        if pl.output_format is OutputFormatType.video:
            for profile, entities in pl.entities.items():
                c_op = profiles.get_convert_options(profile)
                if not c_op:
                    return
                v_op = profiles.get_video_options(profile)
                # convert unless the video has not been downloaded in
                # proper format
                if not c_op['output_format'] == v_op['output_format']:
                    s, f = self._convert_video(entities, c_op)
                    pl.entities[profile] = s
                    if f and self.event_listener.do_continue():
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
                    self.event_listener.error(e)
                    continue
                copied = self._copy_to_local_path(local_path, links)
                processed.append(copied)

            for en in entities:
                lnk = en['link']
                if all([lnk in pr for pr in processed]):
                    try:
                        os.remove(lnk)
                    except FileNotFoundError:
                        pass  # ignore this exception
                else:
                    self._dbg(f'{lnk} has not been sent')

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
            self._dbg(f'copying {ln} to {local_path}')
            try:
                shutil.copy2(ln, local_path)
                copied.append(ln)
            except shutil.SameFileError as e:
                self.event_listener.error(e)
        return copied

    def _get_sender(self, device_id):
        '''return a sender from the cache for a device ID if possible
        or create a new one'''
        if device_id in self.senders:
            return self.senders[device_id]
        else:
            sender = BluetoothClient(device_id, self.temp_dir)
            if not sender.found:
                self.event_listener.error('device not found')
                return None
            else:
                self.senders[device_id] = sender
                return sender

    def _check_video_converter(self):
        if not self.executor.does_command_exist(Bluetube.CONVERTER, dashes=1):
            self.event_listener.error('converter not found',
                                      Bluetube.CONVERTER)
            self.event_listener.inform('converter not found')
            return self.event_listener.do_continue()
        return True

    def _check_profiles(self, pl, profiles):
        '''check if profiles if the playlist do exist'''
        def check_profiles_internal(profile):
            if not profiles.check_profile(profile):
                self.event_listener.error('profile not found',
                                          profile,
                                          pl.title,
                                          pl.author)
                all_pr = ', '.join(profiles.get_profiles())
                self.event_listener.warn(f'Possible profiles - {all_pr}.')
                self.event_listener.inform('This playlist is skipped.\n'
                                           'Edit the playlist and try again')
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
                self.event_listener.error(e)
                msg = f'Profile "{pr}" are not configured properly'
                self.event_listener.warn(msg)
                return False

        return True

    def _check_media_player(self):
        configs = Configs(self.bt_dir)
        mp = configs.get_media_player()
        if mp and mp != '-':
            self.event_listener.set_media_player(mp)
        elif mp == '-':
            return
        else:
            self.event_listener.warn('no media player')

            def set_media_player():
                mp = self.event_listener.arbitrary_input()
                if mp == '-' or self.executor.does_command_exist(mp):
                    configs.set_media_player(mp)
                    self.event_listener.set_media_player(mp)
                else:
                    self.event_listener.error(f'"{mp}" not found. Try again.')
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
            self.event_listener.warn('no editor')

            def set_editor():
                ed = self.event_listener.arbitrary_input()
                if self.executor.does_command_exist(ed):
                    configs.set_editor(ed)
                else:
                    self.event_listener.error(f'"{ed}" not found. Try again.')
                    set_editor()
            set_editor()

    def _convert_video(self, entities, configs):
        '''convert all videos in the playlist,
        return a list of succeeded an and a list of failed links'''
        options = ('-y',  # overwrite output files
                   '-hide_banner',)
        codecs_options = configs.get('codecs_options', '')
        codecs_options = tuple(codecs_options.split())
        output_format = configs['output_format']
        success, failure = [], []
        for en in entities:
            orig = en['link']
            new = os.path.splitext(orig)[0] + '.' + output_format
            if orig == new:
                self.event_listener.warn('conversion is not needed')
                success.append(en)
                continue
            args = (Bluetube.CONVERTER,) + ('-i', orig) + options + \
                codecs_options + (new,)
            if not 1 == self.executor.call(args, cwd=self.temp_dir):
                os.remove(os.path.join(self.temp_dir, orig))
                en['link'] = new
                success.append(en)
            else:
                failure.append(en)
                d = os.path.join(self.temp_dir, Bluetube.NOT_CONV_DIR)
                os.makedirs(d, Bluetube.ACCESS_MODE, exist_ok=True)
                os.rename(orig, os.path.join(d, os.path.basename(orig)))
                self.event_listener.error(os.path.basename(orig))
                self.event_listener.inform(f'Command: \n{" ".join(args)}')
                self.event_listener.inform(f'Check {d} after '
                                           f'the script is done.')
        return success, failure

    def _check_downloader(self):
        return self.executor.does_command_exist(Bluetube.DOWNLOADER)

    def _get_feed_url(self, url):
        p1 = re.compile(r'^https://www\.youtube\.com/watch\?v=.+&list=(.+)$')
        p2 = re.compile(r'^https://www\.youtube\.com/playlist\?list=(.+)$')
        m = p1.match(url)
        if not m:
            m = p2.match(url)
        if m:
            msg = 'https://www.youtube.com/feeds/videos.xml?playlist_id={}'
            return msg.format(m.group(1))
        else:
            p = re.compile(r'^https://www\.youtube\.com/channel/(.+)/.*$')
            m = p.match(url)
            if m:
                msg = 'https://www.youtube.com/feeds/videos.xml?channel_id={}'
                return msg.format(m.group(1))
            self.event_listener.error('misformatted URL')
            return None

    def _get_rss_fetcher(self):
        '''make and return a function to get RSS'''
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

        def fetch_rss(pl):
            '''get URLs from the RSS
            that the user will selected for every playlist'''
            self.event_listener.inform('feed is fetching',
                                       pl.title,
                                       capture='RSS')
            try:
                req = urllib.request.Request(pl.url, headers=headers)
                response = urllib.request.urlopen(req).read()
            except HTTPError as e:
                self.event_listener.error(e)
                response = b''
            f = feedparser.parse(io.BytesIO(response))
            pl.feedparser_data = f

        return fetch_rss

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
                    self.event_listener.inform(pl.author)
                    channel_has_update = True
                if self.event_listener.ask(e):
                    entities.append(e)
                if new_last_update < e_update:
                    new_last_update = e_update
        pl.last_update = new_last_update
        pl.entities = entities
        return pl

    def _download(self, entities, output_format, configs, cache):
        options = self._build_converter_options(output_format, configs)
        # create a temporal directory to download a file by its link
        # to be sure that the file belongs to the link
        tmp = os.path.join(self.temp_dir, 'tmp')
        os.makedirs(tmp, Bluetube.ACCESS_MODE, exist_ok=True)
        success, failure = [], []

        for en in entities:
            all_options = options + (en['link'],)

            # check the value in the given cache
            # to avoid downloading the same file twice
            new_link = cache.get(' '.join(all_options))
            if new_link:
                self._dbg(f'this link has been downloaded - {new_link}')
                en['link'] = new_link
                success.append(en)
            else:
                status = self.executor.call(all_options, cwd=tmp)
                if status:
                    failure.append(en)
                    # clear the tmp directory that may have parts of
                    # not completely downloaded file.
                    for f in os.listdir(tmp):
                        os.unlink(os.path.join(tmp, f))
                else:
                    fs = os.listdir(tmp)
                    assert len(fs) == 1, \
                        'one link should match one file in tmp'
                    self._add_metadata(en, os.path.join(tmp, fs[0]))
                    new_link = os.path.join(self.temp_dir,
                                            os.path.basename(fs[0]))
                    # move the file out of the tmp directory
                    os.rename(os.path.join(tmp, fs[0]), new_link)
                    en['link'] = new_link
                    success.append(en)

                    # put the link to just downloaded file into the cache
                    cache[' '.join(all_options)] = new_link

        shutil.rmtree(tmp)
        return success, failure

    def _build_converter_options(self, output_format, configs):
        options = ('--ignore-config',
                   '--ignore-errors',
                   '--mark-watched',)
        if output_format == OutputFormatType.audio:
            output_format = configs['output_format']
            spec_options = ('--extract-audio',
                            f'--audio-format={output_format}',
                            '--audio-quality=9',  # 9 means worse
                            '--postprocessor-args', '-ac 1',  # convert to mono
                            )
        elif output_format == OutputFormatType.video:
            of = configs.get('output_format')
            spec_options = ('--format', of,) if of else ()
        else:
            assert 0, 'unexpected output format'

        all_options = (Bluetube.DOWNLOADER,) + options + spec_options
        return all_options

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
                self.event_listener.warn(msg)
        self.temp_dir = temp_dir

    def _return_temp_dir(self):
        assert self.temp_dir, 'nothing to return, call fetch'
        if os.path.isdir(self.temp_dir):
            try:
                os.rmdir(self.temp_dir)
            except OSError:
                self.event_listener.warn('download directory not empty',
                                         self.temp_dir)
                self.event_listener.out('\n  '.join(os.listdir(self.temp_dir)))

    def _get_bt_dir(self, home_dir):
        bt_dir = home_dir if home_dir else Bluetube.HOME_DIR
        if not os.path.exists(bt_dir) or not os.path.isdir(bt_dir):
            os.makedirs(bt_dir, Bluetube.ACCESS_MODE)
        return bt_dir

    def _dbg(self, msg):
        '''print debug info to console'''
        if self.verbose:
            print(f'[verbose] {msg}')

    def _add_metadata(self, entity, file_path):
        '''add metadata to a downloaded file'''
        ext = os.path.splitext(file_path)[1]
        try:
            if ext == '.mp3':
                audio = mp3.MP3(file_path)
                audio['TPE1'] = id3.TPE1(text=entity.author)
                audio['TIT2'] = id3.TIT2(text=entity.title)
                audio['COMM'] = id3.COMM(text=entity.summary[:256])
                audio.save()
            elif ext == '.mp4':
                video = mp4.MP4(file_path)
                video["\xa9ART"] = entity.author
                video["\xa9nam"] = entity.title
            else:
                self._dbg(f'cannot add metadata to {ext}')
        except MutagenError as e:
            self.event_listener.error(e)
