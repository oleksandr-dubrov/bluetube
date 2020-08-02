#!/usr/bin/python3

__version__ = '1.5'
__author__ = 'Olexandr Dubrov <olexandr.dubrov@gmail.com>'
__license__ = '''
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


import argparse
import io
import os
import re
import StringIO
import subprocess
import sys
import tempfile
import time
import urllib
import webbrowser
from configparser import SafeConfigParser

import feedparser
from bluetube.bcolors import Bcolors
from bluetube.bluetoothclient import BluetoothClient
from bluetube.feeds import Feeds
from bluetube.model import OutputFormatType
from bluetube.profiles import Profiles, ProfilesException


class CommandExecutor(object):
    '''This class run the commands in the shell'''

    def __init__(self, verbose):
        self._verbose = verbose
        
    def call(self, args, cwd=None, suppress_stdout=False, suppress_stderr=False):
        if cwd == None:
            cwd = os.getcwd()
        call_env = os.environ
        return_code = 0
        stdout, stderr = None, None
        try:
            if self._verbose:
                print('RUN: {}'.format([a for a in args]))
            if suppress_stdout:
                stdout = open(os.devnull, 'wb')
            if suppress_stderr:
                stderr = open(os.devnull, 'wb')
            return_code = subprocess.call(args,
                                        env=call_env,
                                        stdout=stdout,
                                        stderr=stderr,
                                        cwd=cwd)
        except OSError as e:
            return_code = e.errno
            print(e.strerror)
        if self._verbose:
            print('Return code: {}'.format(return_code))
        return return_code

    def does_command_exist(self, name, dashes=2):
        '''call a command with the given name
        and expects that it has option --version'''
        return not self.call((name,
                            '{}version'.format(dashes * '-')),
                            suppress_stdout=True,
                            suppress_stderr=True)


class CLI(object):
    '''Command line interface of the tool'''

    INDENTATION = 10
    MEDIA_PLAYER = 'vlc'

    def __init__(self, verbose):
        self._executor = CommandExecutor(verbose)
        self._is_player = self._executor.does_command_exist(CLI.MEDIA_PLAYER)

    def warn(self, msg):
        '''warn the user by an arbitrary message'''
        Bcolors.warn(msg)

    def inform(self, msg):
        '''inform the user by an arbitrary message'''
        print (msg)

    def feed_is_feaching(self, pl):
        '''a feed is about to be fetched'''
        print('{ind}{tit}'.format(ind=' ' * CLI.INDENTATION, tit=pl.title))

    def feeds_updated(self):
        ''' inform the user by voice that the update has been done'''
        self._executor.call(('spd-say', '--wait', 'beep, beep.'))

    def device_not_found(self, download_dir, is_fatal=False):
        Bcolors.warn('Your bluetooth device is not accessible.')
        Bcolors.warn('The script will download files to {} directory.'
                     .format(download_dir))
        if not is_fatal:
            input('Press Enter to continue, Ctrl+c to interrupt.')

    def downloader_not_found(self, downloader):
        Bcolors.error('The tool for downloading "{}" is not found in PATH'
                      .format(downloader))

    def download_dir_not_empty(self, download_dir):
        Bcolors.warn('The download directory {} is not empty. Cannot delete it.'
                    .format(download_dir))
        Bcolors.warn('\n  '.join(os.listdir(download_dir)))

    def failed_to_convert(self, args, filepath, where):
        Bcolors.error('Failed to convert the file {}.'
                      .format(os.path.basename(filepath)))
        Bcolors.warn('Command: \n{}'.format(' '.join(args)))
        Bcolors.warn('Check {} after the script is done.'
                    .format(where))

    def ask(self, feed_entry):
        '''ask if perform something'''
        # d for download
        d = ['d', 'D', 'В', 'в', 'Y', 'y', 'Н', 'н', 'yes', 'YES']
        # r for reject
        r = ['r', 'R', 'к', 'К', 'n', 'N', 'т', 'Т', 'no', 'NO']
        s = ['s', 'S', 'і', 'І']
        open_browser = ['b', 'B', 'и', 'И']
        open_player = ['p', 'P', 'З', 'з']

        link = feed_entry['link']
        while True:
            i = input('{}\n'.format(self._make_question_to_ask(feed_entry)))
            if i in d:
                return True
            elif i in r:
                return False
            elif i in s:
                print('Summary:\n{}'.format(feed_entry['summary']))
            elif i in open_browser:
                print('Opening the link in the default browser...')
                webbrowser.open(link, new=2)
            elif i in open_player:
                print('Opening the link by {}...'.format(CLI.MEDIA_PLAYER))
                self._executor.call((CLI.MEDIA_PLAYER, link),
                                    suppress_stderr=True)
            else:
                msg = '{}{} to download, {} to reject, {} to open in a browser'
                params = (Bcolors.FAIL, d[0], r[0], open_browser[0])
                if self._is_player:
                    msg += ', {} to open in a media player'
                    params += (open_player[0], )
                if feed_entry['summary']:
                    msg +=', {} to get a summary'
                    params += (s[0], )
                msg += '.{}'.format(Bcolors.ENDC)
                Bcolors.error(msg.format(*params))

    def _make_question_to_ask(self, feed_entry):
        pub = feed_entry['published_parsed']
        params = {'ind': 2 * CLI.INDENTATION * ' ',
                  'tit': feed_entry['title'],
                  'h': pub.tm_hour,
                  'min': pub.tm_min,
                  'd': pub.tm_mday,
                  'mon': pub.tm_mon}
        msg = '{ind}{tit} ({h}:{min:0>2} {d}.{mon:0>2})'.format(**params)
        question = '{}\n'.format(msg)
        question += ('{b}d{e}ownload | '
                     '{b}r{e}eject | '
                     'open in a {b}b{e}rowser').format(b=Bcolors.HEADER,
                                                     e=Bcolors.ENDC)
        if self._is_player:
            msg = ' | open in a media {b}p{e}layer'.format(b=Bcolors.HEADER,
                                                           e=Bcolors.ENDC)
            question += msg 
        if feed_entry['summary']:
            question += ' | {b}s{e}ummary'.format(b=Bcolors.HEADER,
                                                  e=Bcolors.ENDC)
        return question


class Bluetube(object):
    ''' The main class of the script. '''

    CONFIG_FILE_NAME = 'bluetube.cfg'
    CUR_DIR = os.path.expanduser(os.path.join('~', '.bluetube'))
    CONFIG_FILES = [os.path.join(CUR_DIR, CONFIG_FILE_NAME),
                    os.path.expanduser(os.path.join('~',
                                                    '.bluetube',
                                                    CONFIG_FILE_NAME))]
    CONFIG_TEMPLATE = os.path.join(CUR_DIR, 'bt_config.template')
    DOWNLOADER = 'youtube-dl'
    CONVERTER = 'ffmpeg'
    ACCESS_MODE = 0o744
    NOT_CONV_DIR = 'not_converted' # keep files that failed to be converted here


    def __init__(self, verbose=False):
        self.verbose = verbose,
        self.senders = {}
        self.executor = CommandExecutor(verbose)
        self.event_listener = CLI(verbose)

    def add_playlist(self, url, out_format):
        ''' add a new playlists to RSS feeds '''
        out_format = self._get_type(out_format)
        feed_url = self._get_feed_url(url)
        if out_format and feed_url:
            f = feedparser.parse(feed_url)
            title = f.feed.title
            author = f.feed.author
            feeds = Feeds(self._get_bt_dir())
            if feeds.has_playlist(author, title):
                Bcolors.error('The playlist {} by {} has already been existed'
                            .format(title, author))
            else:
                feeds.add_playlist(author, title, feed_url, out_format)
                Bcolors.intense('{} by {} added successfully.'.format(title,
                                                                    author))
            return True
        return False

    def list_playlists(self):
        ''' list all playlists in RSS feeds '''
        feeds = Feeds(self._get_bt_dir())
        all_playlists = feeds.get_all_playlists()
        if len(all_playlists):
            for a in all_playlists:
                print(a['author'])
                for c in a['playlists']:
                    o = '{}{}'.format(' ' * 10, c.title) # Bluetube.INDENTATION
                    o = '{} ({})'.format(o, time.strftime('%Y-%m-%d %H:%M:%S',
                                            time.localtime(c.last_update)))
                    print(o)
        else:
            Bcolors.warn('The list of playlist is empty.\n'
                         'Use --add to add a playlist.')

    def remove_playlist(self, author, title):
        ''' remove a playlist be given title '''
        feeds = Feeds(self._get_bt_dir())
        if feeds.has_playlist(author, title):
            feeds.remove_playlist(author, title)
        else:
            Bcolors.error('{} by {} not found'.format(title, author))

    def run(self, show_all=False):
        ''' The main method. It does everything.'''

        pls = Feeds(self._get_bt_dir()).get_all_playlists()

        fetch_rss = self._get_rss_fetcher()
        for a in pls:
            self.event_listener.inform(a['author'])
            for pl in a['playlists']:
                fetch_rss(pl)

        self.event_listener.feeds_updated()

        def proccess_playlist(pls):
            self.event_listener.inform(pls['author'])
            return [self._process_playlist(pl, show_all)
                    for pl in pls['playlists']]
        pls = [proccess_playlist(pl) for pl in pls]
        pls = [p for pl in pls for p in pl] # make the list flat

        try:
            profiles = Profiles(self._get_bt_dir())
        except ProfilesException as e:
            Bcolors.error(e)
            return

        download_dir = self._fetch_download_dir()
        if not self._check_downloader():
            return
        for pl in pls:
            if pl.output_format is OutputFormatType.audio:
                dl_op = profiles.get_audio_options(pl.profile)
            elif pl.output_format is OutputFormatType.video:
                dl_op = profiles.get_video_options(pl.profile)
            else:
                assert 0, 'unexpected output format type'
            self._download(pl, dl_op, download_dir)

        for pl in pls:
            # convert video, audio has been converted by the downloader
            if pl.output_format is OutputFormatType.video:
                v_op = profiles.get_video_options(pl.profile)
                self._convert_video(pl, v_op, download_dir)

        for pl in pls:
            s_op = profiles.get_sender_options(pl.profile)
            sender = self._get_sender(s_op, download_dir)
            sent = []
            if sender.found and sender.connect():
                sent += sender.send(pl.links)
                sender.disconnect()
                del pl.links
            for f in sent:
                os.remove(f)

        self._return_download_dir(download_dir)

    def send(self):
        '''send files from the bluetube download directory
        to a bluetooth device'''
        self.configs = self._get_configs()
        download_dir = self._fetch_download_dir()
        if os.listdir(download_dir):
            sender = self._get_sender(download_dir)
            if sender.found:
                self._send(sender, download_dir)
            else:
                Bcolors.warn('Your bluetooth device is not accessible.')
        else:
            Bcolors.warn('Nothing to send.')
        self._return_download_dir(download_dir)

    def _get_sender(self, configs, download_dir):
        '''return a sender from the cache for a device ID if possible
        or create a new one'''
        device_id = configs['deviceID']
        if device_id in self.senders:
            return self.senders[device_id]
        else:
            sender = BluetoothClient(device_id, download_dir)
            if not sender.found:
                self.event_listener.device_not_found(download_dir)
                return None
            else:
                self.senders[device_id] = sender
                return sender

    def _check_vidoe_converter(self):
        if self.executor.does_command_exist(Bluetube.CONVERTER, dashes=1):
            return True
        else:
            Bcolors.warn('ERROR: The tool for converting video "{}" is not found in PATH'
                        .format(Bluetube.CONVERTER))
            Bcolors.warn('Please install the converter.')
            input('Press Enter to continue, Ctrl+c to interrupt.')
            return False

    def _convert_video(self, pl, configs, download_dir):
        options = ('-y',  # overwrite output files
                   '-hide_banner',)
        codecs_options = configs['codecs_options']
        codecs_options = tuple(codecs_options.split())
        output_format = configs['output_format']
        for idx in range(len(pl.links)):
            orig = pl.links[idx]
            new = os.path.splitext(pl.links[idx])[0] + '.' + output_format
            args = (Bluetube.CONVERTER,) + \
                    ('-i', orig) + \
                    options + \
                    codecs_options + \
                    (new,)
            if not 1 == self.executor.call(args, cwd=download_dir):
                os.remove(os.path.join(download_dir, orig))
                pl.links[idx] = new
            else:
                del pl.links[idx]
                d = os.path.join(download_dir, Bluetube.NOT_CONV_DIR)
                os.makedirs(d, Bluetube.ACCESS_MODE, exist_ok=True)
                os.rename(orig, os.path.join(d, os.path.basename(orig)))
                self.event_listener.failed_to_convert(args, orig, d)

    def _get_configs(self):
        parser = SafeConfigParser()
        return None if len(parser.read(Bluetube.CONFIG_FILES)) == 0 else parser

    def _check_config_file(self):
        ok = True
        if self.configs == None:
            Bcolors.error('Configuration file is not found.')
            ok = False

        if ok and not (self.configs.has_section('bluetooth')
            and self.configs.has_section('video')
            and self.configs.has_option('bluetooth', 'deviceID')
            and self.configs.has_option('video', 'output_format')):
            Bcolors.error('The configuration file has no needed options.')
            ok = False

        if not ok:
            with open(Bluetube.CONFIG_TEMPLATE, 'r') as f:
                Bcolors.error('You must create {} or {} with the content below manually:\n{}'
                            .format(Bluetube.CONFIG_FILES[0],
                                    Bluetube.CONFIG_FILES[1],
                                    f.read()))
            return False

        if not self.configs.has_option('video', 'codecs_options'):
            Bcolors.error('ffmpeg codecs are not configured in {}'
                        .format(Bluetube.CONFIG_FILE))

        return ok

    def _check_downloader(self):
        if self.executor.does_command_exist(Bluetube.DOWNLOADER):
            return True
        else:
            self.event_listener.downloader_not_found(Bluetube.DOWNLOADER)
            return False

    def _get_type(self, out_format):
        if out_format in ['a', 'audio']:
            return OutputFormatType.audio
        elif out_format in ['v', 'video']:
            return OutputFormatType.video
        else:
            Bcolors.error('Unexpected output type.'
                          'Should be v (or video) or a (audio).')
        return None

    def _get_feed_url(self, url):
        p1 = re.compile('^https://www\.youtube\.com/watch\?v=.+&list=(.+)$')
        p2 = re.compile('^https://www\.youtube\.com/playlist\?list=(.+)$')
        m = p1.match(url);
        if not m:
            m = p2.match(url)
        if m:
            return 'https://www.youtube.com/feeds/videos.xml?playlist_id={}'.format(m.group(1))
        else:
            p = re.compile('^https://www\.youtube\.com/channel/(.+)$')
            m = p.match(url);
            if m:
                return 'https://www.youtube.com/feeds/videos.xml?channel_id={}'.format(m.group(1))
            Bcolors.error('ERROR: misformatted URL of a youtube list provided.\n\
    Should be https://www.youtube.com/watch?v=XXX&list=XXX for a playlist,\n\
    or https://www.youtube.com/feeds/videos.xml?playlist_id=XXX for a channel.')
            return None

    def _get_rss_fetcher(self):
        '''make and return a function to get RSS'''
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

        def fetch_rss(pl):
            '''get URLs from the RSS
            that the user will selected for every playlist'''
            self.event_listener.feed_is_feaching(pl)
            req = urllib.request.Request(pl.url, headers=headers)
            response = urllib.request.urlopen(req).read()
            f = feedparser.parse(io.BytesIO(response))
            pl.feedparser_data = f

        return fetch_rss

    def _process_playlist(self, pl, show_all):
        '''process the playlist'''
        urls = []
        is_need_update = False
        new_last_update = last_update = pl.last_update
        assert pl.feedparser_data is not None, 'fetch RSS first'
        for e in pl.feedparser_data.entries:
            e_update = time.mktime(e['published_parsed'])
            if last_update < e_update or show_all:
                if not is_need_update:
                    is_need_update = True
                if self.event_listener.ask(e):
                    urls.append(e['link'])
                if new_last_update < e_update:
                    new_last_update = e_update
        pl.last_update = new_last_update
        pl.links = urls
        return pl

    def _download(self, pl, configs, download_dir):
        options = self._build_converter_options(pl, configs)
        # create a temporal directory to download a file by its link
        # to be sure that the file belongs to the link 
        tmp = os.path.join(download_dir, 'tmp')
        os.makedirs(tmp, Bluetube.ACCESS_MODE, exist_ok=True)

        for idx in range(len(pl.links)):
            status = self.executor.call(options + (pl.links[idx],), cwd=tmp)
            if status:
                pl.add_failed_links(pl.links[idx])
                pl.links[idx] = None
                for f in os.listdir(tmp): # clear the tmp directory
                    os.unlink(os.path.join(tmp, f))
            else:
                fs = os.listdir(tmp)
                assert len(fs) == 1, 'one link should march one file in tmp'
                new_link = os.path.join(download_dir, os.path.basename(fs[0]))
                # move the file out of the tmp directory
                os.rename(os.path.join(tmp, fs[0]), new_link)
                pl.links[idx] = new_link
        os.rmdir(tmp)

    def _build_converter_options(self, pl, configs):
        options = ('--ignore-config',
                    '--ignore-errors',
                    '--mark-watched',)
        if pl.output_format == OutputFormatType.audio:
            spec_options = ('--extract-audio',
                            '--audio-format=mp3',
                            '--audio-quality=9',  # 9 means worse
                            '--embed-thumbnail',
                            )
        elif pl.output_format == OutputFormatType.video:
            if 'video_format' in configs:
                video_format = self.configs['video_format']
            else:
                video_format = 'mp4[width<=640]+worstaudio'
            spec_options = ('--format', video_format,)
        else:
            assert 0, 'unexpected output format'

        all_options = (Bluetube.DOWNLOADER,) + options + spec_options
        return all_options

    def _send(self, sender, download_dir):
        '''Send all files in the given directory'''
        sent = []
        files = os.listdir(download_dir)
        for fl in files:
            if fl.endswith('.part') or fl.endswith('.ytdl'):
                # remove:
                #        partially downloaded files
                #        youtube-dl service files
                os.remove(os.path.join(download_dir, fl))
        files = os.listdir(download_dir) # update the list of files
        if sender.found and sender.connect():
                sent += sender.send(files)
                sender.disconnect()
        for f in sent:
            os.remove(f)

    def _fetch_download_dir(self):
        bluetube_dir = os.path.join(tempfile.gettempdir(), 'bluetube')
        if not os.path.isdir(bluetube_dir):
            os.mkdir(bluetube_dir)
        else:
            fs = os.listdir(bluetube_dir)
            if Bluetube.NOT_CONV_DIR in fs:
                msg = 'Not converted.\n {}'\
                    .format(' '.join(
                        os.listdir(
                            os.path.join(bluetube_dir,
                                         Bluetube.NOT_CONV_DIR))))
                self.event_listener.warn(msg)
                fs.remove(Bluetube.NOT_CONV_DIR)
            if len(fs):
                msg = 'Ready to be sent:\n{}'.format(' '.join(fs))
                self.event_listener.warn(msg)
        return bluetube_dir

    def _return_download_dir(self, bluetube_dir):
        if os.path.isdir(bluetube_dir):
            try:
                os.rmdir(bluetube_dir)
            except OSError:
                self.event_listener.download_dir_not_empty(bluetube_dir)

    def _get_bt_dir(self):
        if not os.path.exists(Bluetube.CUR_DIR) \
            or not os.path.isdir(Bluetube.CUR_DIR):
            os.makedirs(Bluetube.CUR_DIR, Bluetube.ACCESS_MODE)
        return Bluetube.CUR_DIR

# ============================================================================ #


def main():
    description='The script downloads youtube video as video or audio and sends to a bluetooth client device.'
    epilog = 'If no option specified the script shows feeds to choose, downloads and sends via bluetooth client.'
    parser = argparse.ArgumentParser(prog='bluetube', description=description)
    parser.epilog = epilog
    me_group = parser.add_mutually_exclusive_group()

    me_group.add_argument('--add', '-a',
                        help='add a URL to youtube playlist', type=str)
    parser.add_argument('-t',
                    dest='type',
                    help='a type of a file you want to get (for --add)',
                    choices=['a', 'v'],
                    default='v')
    me_group.add_argument('--list', '-l',
                        help='list all playlists', action='store_true')
    me_group.add_argument('--remove', '-r',
                        nargs=2, 
                        help='remove a playlist by names of the author and the playlist',
                        type=lambda s: str(s, 'utf8'))

    me_group.add_argument('--send', '-s',
                        help='send already downloaded files',
                        action='store_true')

    parser.add_argument('--show_all',
                    action='store_true',
                    help='show all available feed items despite last update time')
    parser.add_argument('--verbose', '-v',
                    action='store_true',
                    help='print more information')
    parser.add_argument('--version', action='version',
                    version='%(prog)s {}'.format(__version__))

    args = parser.parse_args()
    bluetube = Bluetube(args.verbose)
    if args.add:
        if not bluetube.add_playlist(args.add, args.type):
            sys.exit(-1)
    elif args.list:
        bluetube.list_playlists()
    elif args.remove:
        bluetube.remove_playlist(args.remove[0].strip(), args.remove[1].strip())
    elif args.send:
        bluetube.send()
    else:
        bluetube.run(args.show_all)
    print('Done')

if __name__ == '__main__':
    main()
