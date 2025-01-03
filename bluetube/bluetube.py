import asyncio
import logging
import os
import re
import signal
import tempfile
import time
from pathlib import Path
from typing import NoReturn, Optional

import aiohttp
import feedparser

from bluetube.cli.events import Error, Event, Info, Success, Warn
from bluetube.cli.inputer import Inputer
from bluetube.componentfactory import ComponentFactory
from bluetube.configs import Configs
from bluetube.eventpublisher import EventPublisher
from bluetube.model import (OutputFormatType, Playlist, Publication,
                            PublicationStatus)
from bluetube.profiles import Profiles, ProfilesException
from bluetube.repository import DbConverter, Repository, RepositoryException
from bluetube.sender import SenderException
from bluetube.utils import deemojify


class Bluetube(EventPublisher):
    ''' The main class of the script. '''

    TMP_DIR = "bluetube"
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
        Repository.verbose = verbose
        self._debug = logging.getLogger(__name__).debug
        signal.signal(signal.SIGINT, self.signal_handler)
        self.factory = ComponentFactory()
        self.executor = self.factory.get_command_executor()
        self.inputer = self.factory.get_inputer(yes)
        self.temp_dir: Path = self._fetch_temp_dir()
        self.bt_dir = self._get_bt_dir(Path(home_dir) if home_dir else None)
        self.repository = self.factory.get_repository(self.bt_dir)

        self.subscribe(self.factory.get_outputer())

    def add_playlist(self, url, out_format, profile) -> Optional[Playlist]:
        ''' add a new playlists to RSS feeds '''
        feed_url = self._get_feed_url(url)
        if not feed_url:
            self.notify(Error("bad feed URL"))
            return None

        if (of := OutputFormatType.from_char(out_format)) is None:
            self.notify(Error("unexpected output format"))
            return None

        profiles = self._get_profiles(self.bt_dir)
        if profile not in profiles.get_profiles():
            self.notify(Error("unknown profile"))  # TODO: does the user know what to do next?
            return None

        f = feedparser.parse(feed_url)
        title = deemojify(f.feed.title)
        author = deemojify(f.feed.author)
        playlist = None
        try:
            with self.repository as repo:
                db_profile = repo.upsert_profile(profile)
                db_author = repo.upsert_author(author)
                playlist = repo.add_playlist(db_author, title, feed_url, of, db_profile)
                success = Success('added', title, author)
                self.notify(success)
        except RepositoryException:
            error = Error("playlist exists", title, author)
            self.notify(error)

        return playlist

    def list_playlists(self):
        ''' list all playlists in RSS feeds '''
        with self.repository as repo:
            all_playlists = repo.get_all_playlists()
            author_playlists = {}
            for p in all_playlists:
                author_playlists.setdefault(p.author.name, []).append(p)

            if len(author_playlists):
                for a, p in author_playlists.items():
                    print(a)
                    for c in p:
                        out_type = OutputFormatType.to_char(c.output_format)
                        o = f"{' ' * 10}{c.title} |{out_type}, {c.profile.name}|"
                        # add pubs after the last one
                        last_update = c.publications[0].published if c.publications else 0
                        t = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_update))
                        o = f'{o} ({t})'
                        print(o)
            else:
                self.notify(Info('empty database'))

    def remove_playlist(self, author_name: str, title: str) -> None:
        ''' remove the playlist of the given author'''
        with self.repository as repo:
            if (author := repo.get_author(author_name)):
                playlist = repo.get_playlist(author, title)
                if playlist:
                    repo.remove_playlist(playlist)
                    return
        self.notify(Error('playlist not found', title, author_name))

    def run(self):
        ''' The main method. It does everything.'''

        self._debug(f'Bluetube home directory: {self.bt_dir}.')

        self._check_media_player()

        with self.repository as repo:

            if repo.is_empty():
                self.notify(Info('empty database'))
                return

            pubs = self.update(repo)

            if len(pubs):
                self.notify(Success('feeds updated'))

            profiles = self._get_profiles(self.bt_dir)

            chosen = self.choose_publications(pubs)

            # TODO: combine this update with `choose_pubs`
            for p in chosen:
                p.status = PublicationStatus.chosen
                repo.update_publication(p)

        # ----

        with self.repository as repo:

            pubs = repo.get_all_publications()
            for p in pubs:
                if p.status in [PublicationStatus.chosen, PublicationStatus.failed]:
                    self._download_publication(p, profiles)
                    repo.update_publication(p)

            pubs = repo.get_all_publications()
            for p in pubs:
                self._convert_publication(p, profiles)
                repo.update_publication(p)

            pubs = repo.get_all_publications()
            for p in pubs:
                if p.status in [PublicationStatus.downloaded, PublicationStatus.converted]:
                    self._send_publication(p, profiles)
                    repo.update_publication(p)

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

    def edit_playlist(self, author: str, title: str, output_type: Optional[str] = None,
                      profile: Optional[str] = None, reset_failed: bool = False) -> None:
        '''Edit a playlist.'''

        def print_help():
            prs = ' | '.join(Profiles(self.bt_dir).get_profiles())
            msg = 'Run this command with one or all options below:\n' \
                  f'-t (a or v) -pr ({prs})\n' \
                  '-r (to reset previously failed videos)'
            self.notify(Warn(msg))

        if not any((output_type, profile, reset_failed)):
            print_help()
            return None

        with self.repository as repo:
            if (author := repo.get_author(author)):
                playlist = repo.get_playlist(author, title)
                if not playlist:
                    event = Error('playlist not found', title, author)
                    self.notify(event)
                    return None

                if isinstance(output_type, OutputFormatType):
                    playlist.output_format = output_type
                if profile:
                    if profile not in Profiles(self.bt_dir).get_profiles():
                        event = Error(
                            'profile not found',
                            profile,
                            playlist.title,
                            playlist.author.name)
                        self.notify(event)
                    else:
                        db_profile = repo.upsert_profile(profile)
                        playlist.profile = db_profile
                if reset_failed:
                    for pub in playlist.publications:
                        if pub.status is PublicationStatus.failed:
                            pub.status = PublicationStatus.remote
                repo.update_playlist(playlist)
                self._debug('Done.')

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

    def _get_profiles(self, bt_dir: Path) -> Profiles:
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

    def migrate_to_db(self):
        """
        Migrate all data from JSON to DB tables
        if not DB exists.
        """
        sqlite_file = self.bt_dir / Repository.SQLITE_FILE
        if not sqlite_file.exists():
            exporter = DbConverter(self.bt_dir)
            exporter.migrate()

    def update(self, repo: Repository) -> list[Playlist]:
        '''Fetch and parse RSS data for all lists.'''
        authors = repo.get_all_authors()
        publications = []

        async def task(session, author):
            '''task that fetches RSS for the author'''
            events: list[Event] = [Info(author.name, capture='RSS')]
            nonlocal publications
            for pl in author.playlists:
                events.append(Info('feed is fetching', pl.title, capture='RSS'))
                response = await self._fetch_rss(session, pl)
                rss_response = feedparser.parse(response)
                # add pubs after the last one
                last_update = pl.publications[0].published if pl.publications else 0
                new_entries = [e for e in rss_response.entries
                               if last_update < int(time.mktime(e['published_parsed']))]
                added = repo.add_publications(pl, new_entries)
                publications += added

            return events

        async def process_tasks():
            '''process all async tasks'''
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                return await asyncio.gather(*[task(session, a) for a in authors],
                                            return_exceptions=False)

        self.notify(Info('Updating feeds...'))
        try:
            events = asyncio.run(process_tasks())
            # handles all event collected in the event loop
            for event in events:
                for e in event:
                    self.notify(e)
        except aiohttp.ClientConnectorError as e:
            self.notify(Warn(str(e)))  # notify the error immediately
            self.notify(Error('no internet'))
            os._exit(1)

        return publications

    async def _fetch_rss(self, session, pl):
        '''get URLs from the RSS
        that the user will selected for every playlist'''
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = ''
        async with session.get(pl.url, headers=headers) as response:
            response = await response.text()

        return response

    def _download_publication(self, pub, profiles):
        downloader = self.factory.get_downloader(self, self.temp_dir)

        if pub.playlist.output_format is OutputFormatType.audio:
            dl_op = profiles.get_audio_options(pub.playlist.profile)
        elif pub.playlist.output_format is OutputFormatType.video:
            dl_op = profiles.get_video_options(pub.playlist.profile)
        else:
            assert 0, 'unexpected output format type'

        downloader.download(pub,
                            pub.playlist.output_format,
                            dl_op)

    def _convert_publication(self, pub: Publication, profiles: Profiles) -> None:
        # convert video, audio has been converted by the downloader
        converter = self.factory.get_converter(self, self.temp_dir)
        if pub.playlist.output_format is OutputFormatType.video:
            c_op = profiles.get_convert_options(pub.playlist.profile)
            v_op = profiles.get_video_options(pub.playlist.profile)
            if not c_op or not v_op:
                return
            # convert unless the video has not been downloaded in
            # proper format
            if not c_op['output_format'] == v_op['output_format']:
                converter.convert(pub, c_op)

    def _send_publication(self, pub: Publication, profiles: Profiles) -> None:
        s_op = profiles.get_send_options(pub.playlist.profile.name)

        local_path = s_op.get("local_path")
        bt_id = s_op.get("bluetooth_device_id")

        senders = self.factory.get_senders(self, self.temp_dir, local_path=local_path, device_id=bt_id)

        assert pub.local_path, "no local path"
        try:
            if local_path in senders:
                senders[local_path].send(pub.local_path, local_path)
            if bt_id in senders:
                senders[bt_id].send(pub.local_path, bt_id)
        except SenderException as e:
            self.notify(Error(str(e)))

        try:
            os.remove(self.temp_dir / pub.local_path)
        except FileNotFoundError:
            pass  # ignore this exception

        pub.status = PublicationStatus.sent
        pub.local_path = None  # TODO or set the destination path

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

    def choose_publications(self, pubs: list[Publication]):
        '''ask the user what to do with the publications'''
        chosen_pubs = []
        for p in pubs:
            # copy some fields for backward compatibility with the inputer
            entry = {"link": p.link,
                     "summary": p.description,
                     "published_parsed": p.published,
                     "title": p.title}
            if self.inputer.ask(entry):
                chosen_pubs.append(p)
        return chosen_pubs

    def _fetch_temp_dir(self) -> Path:
        '''fetch a temporal directory'''
        temp_dir = Path(tempfile.gettempdir()) / self.TMP_DIR
        temp_dir.mkdir(exist_ok=True)
        fs = os.listdir(temp_dir)
        if len(fs):
            # TODO: no need
            msg = 'Ready to be sent:\n{}'.format('\n'.join(fs))
            self.notify(Warn(msg))
        return temp_dir

    def _get_bt_dir(self, home_dir: Optional[Path]):
        bt_dir = home_dir if home_dir else Path(Bluetube.HOME_DIR)
        if not bt_dir.is_dir():
            bt_dir.expanduser().mkdir(mode=Bluetube.ACCESS_MODE, exist_ok=True)
        else:
            self.notify(Error(f"{bt_dir} is not a directory"))
        return bt_dir.expanduser()

    def _config_logger(self, verbose: bool) -> None:
        level = logging.DEBUG if verbose else logging.WARNING
        f = '[verbose] %(name)s - %(message)s'
        logging.basicConfig(format=f, level=level)
