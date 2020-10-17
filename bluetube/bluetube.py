#!/usr/bin/python3

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


import argparse
import copy
import io
import os
import re
import sys
import tempfile
import time
import urllib
import feedparser
import shutil

from bluetube import __version__
from bluetube.bluetoothclient import BluetoothClient
from bluetube.commandexecutor import CommandExecutor
from bluetube.cli import CLI
from bluetube.feeds import Feeds
from bluetube.model import OutputFormatType
from bluetube.profiles import Profiles, ProfilesException


class ToolNotFoundException(Exception):
    '''Raise this exception in case an external tool is not found'''

    def __init__(self, msg, tool):
        self.msg = msg
        self.tool = tool


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
    # keep files that failed to be converted here
    NOT_CONV_DIR = 'not_converted'

    def __init__(self, verbose=False):
        self.verbose = verbose,
        self.senders = {}
        self.executor = CommandExecutor(verbose)
        self.event_listener = CLI(self.executor)

    def add_playlist(self, url, out_format, profiles):
        ''' add a new playlists to RSS feeds '''
        feed_url = self._get_feed_url(url)
        f = feedparser.parse(feed_url)
        title = f.feed.title
        author = f.feed.author
        feeds = Feeds(self._get_bt_dir())
        if feeds.has_playlist(author, title):
            self.event_listener.error('playlist exists'. title, author)
        else:
            feeds.add_playlist(author, title, feed_url, out_format, profiles)
            self.event_listener.success('added', title, author)

    def list_playlists(self):
        ''' list all playlists in RSS feeds '''
        feeds = Feeds(self._get_bt_dir())
        all_playlists = feeds.get_all_playlists()
        if len(all_playlists):
            for a in all_playlists:
                print(a['author'])
                for c in a['playlists']:
                    o = '{}{}'.format(' ' * 10, c.title)  # TODO: INDENTATION
                    t = time.strftime('%Y-%m-%d %H:%M:%S',
                                      time.localtime(c.last_update))
                    o = '{} ({})'.format(o, t)
                    print(o)
        else:
            pass
            # Bcolors.warn('The list of playlist is empty.\n'
            #             'Use --add to add a playlist.')

    def remove_playlist(self, author, title):
        ''' remove a playlist be given title '''
        feeds = Feeds(self._get_bt_dir())
        if feeds.has_playlist(author, title):
            feeds.remove_playlist(author, title)
        else:
            pass
            # Bcolors.error('{} by {} not found'.format(title, author))

    def _get_list(self, feed):
        pls = feed.get_all_playlists()
        fetch_rss = self._get_rss_fetcher()
        for a in pls:
            self.event_listener.inform(a['author'])
            for pl in a['playlists']:
                fetch_rss(pl)
                pl.author = a['author']
        pls = [pl for a in pls for pl in a['playlists']]  # make the list flat
        return pls

    def proccess_playlists(self, pls, show_all):
        ret = []
        for pl in pls:
            self.event_listener.inform(pl.author)
            ret.append(self._process_playlist(pl, show_all))
        return ret

    def _download_list(self, pls, profiles, download_dir):
        for pl in pls:
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
                                      cache,
                                      download_dir)
                pl.entities[profile] = s
                pl.add_failed_entities({profile: f})


    def _convert_list(self, pls, profiles, download_dir):
        for pl in pls:
            # convert video, audio has been converted by the downloader
            if pl.output_format is OutputFormatType.video:
                for profile, entities in pl.entities.items():
                    c_op = profiles.get_convert_options(profile)
                    v_op = profiles.get_video_options(profile)
                    # convert unless the video has not been downloaded in
                    # proper format
                    if not c_op['output_format'] == v_op['output_format']:
                        s, f = self._convert_video(entities,
                                                   c_op,
                                                   download_dir)
                        pl.entities[profile] = s
                        pl.add_failed_entities({profile: f})


    def _send_list(self, pls, profiles, download_dir):
        for pl in pls:
            for profile, entities in pl.entities.items():
                s_op = profiles.get_send_options(profile)
                links = [e['link'] for e in entities]
                if not s_op or not links:
                    continue
                sent, copied = [], []

                # send via bluetooth
                device_id = s_op.get('bluetooth_device_id')
                if device_id:
                    sent = self._send_bt(device_id, links, download_dir)

                # move to local directory
                local_path = s_op.get('local_path')
                if local_path:
                    copied = self._copy_to_local_path(local_path, links)

                # select failed entities
                failure = []
                for en in entities:
                    lnk = en['link']
                    if lnk in sent and lnk in copied:
                        os.remove(lnk)
                    else:
                        failure.append(en)
                pl.add_failed_entities({profile: failure})

    def _send_bt(self, device_id, links, download_dir):
        '''sent all files defined by the links
        to the device defined by device_id'''
        sent = []
        sender = self._get_sender(device_id, download_dir)
        if sender and sender.found and sender.connect():
            sent += sender.send(links)
            sender.disconnect()
        return sent

    def _copy_to_local_path(self, local_path, links):
        '''copy files defined by links to the local path'''
        copied = []
        for l in links:
            try:
                shutil.copy2(l, local_path)
                copied.append(l)
            except shutil.SameFileError as e:
                self.event_listener.error(e)
        return copied


    def run(self, show_all=False):
        ''' The main method. It does everything.'''

        feed = Feeds(self._get_bt_dir())
        pls = self._get_list(feed)

        if len(pls):
            self.event_listener.inform('feeds updated')
        else:
            self.event_listener.inform('empty database')
            return

        pls = self.proccess_playlists(pls, show_all)

        try:
            profiles = Profiles(self._get_bt_dir())
        except ProfilesException as e:
            self.event_listener.error(e)
            return

        # check if profiles do exist in the configurations
        for pl in pls:
            for profile in pl.profiles:
                # TODO: ask to edit configurations
                assert profiles.check_profile(profile)
            
        # combine entities (links with metadata to download) with profiles
        for pl in pls:
            en = {}
            for profile in pl.profiles:
                en[profile] = copy.deepcopy(pl.entities)
            pl.entities = en

        if not self._check_downloader():
            self.event_listener.error('downloader not found',
                                      Bluetube.DOWNLOADER)
            # TODO: move all entities to failed.
            return

        download_dir = self._fetch_download_dir()
        self._download_list(pls, profiles, download_dir)

        if not self._check_vidoe_converter():
            self.event_listener.error('converter not found', Bluetube.CONVERTER)
            self.event_listener.inform('converter not found')
            if not self.event_listener.do_continue():
                return
        self._convert_list(pls, profiles, download_dir)

        self._send_list(pls, profiles, download_dir)

        feed.set_all_playlists(self._prepare_list(pls))
        feed.sync()
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
                pass
                #Bcolors.warn('Your bluetooth device is not accessible.')
        else:
            pass
            #Bcolors.warn('Nothing to send.')
        self._return_download_dir(download_dir)

    def _get_sender(self, device_id, download_dir):
        '''return a sender from the cache for a device ID if possible
        or create a new one'''
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
        return self.executor.does_command_exist(Bluetube.CONVERTER, dashes=1)

    def _convert_video(self, entities, configs, download_dir):
        '''convert all videos in the playlist,
        return a list of succeeded an and a list failed links''' 
        options = ('-y',  # overwrite output files
                   '-hide_banner',)
        codecs_options = configs['codecs_options']
        codecs_options = tuple(codecs_options.split())
        output_format = configs['output_format']
        success, failure = [], []
        for en in entities:
            orig = en['link']
            new = os.path.splitext(orig)[0] + '.' + output_format
            args = (Bluetube.CONVERTER,) + ('-i', orig) + options + \
                codecs_options + (new,)
            if not 1 == self.executor.call(args, cwd=download_dir):
                os.remove(os.path.join(download_dir, orig))
                en['link'] = new
                success.append(en)
            else:
                failure.append(en)
                d = os.path.join(download_dir, Bluetube.NOT_CONV_DIR)
                os.makedirs(d, Bluetube.ACCESS_MODE, exist_ok=True)
                os.rename(orig, os.path.join(d, os.path.basename(orig)))
                self.event_listener.error(os.path.basename(orig))
                self.event_listener.inform('Command: \n{}'.format(' '.join(args)))
                self.event_listener.inform('Check {} after the script is done.'.format(d))
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
            p = re.compile(r'^https://www\.youtube\.com/channel/(.+)$')
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
            self.event_listener.inform('feed is fetching', pl.title)
            req = urllib.request.Request(pl.url, headers=headers)
            response = urllib.request.urlopen(req).read()
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

    def _process_playlist(self, pl, show_all):
        '''process the playlist'''
        entities = []
        is_need_update = False
        new_last_update = last_update = pl.last_update
        assert pl.feedparser_data is not None, 'fetch RSS first'
        for e in pl.feedparser_data.entries:
            e_update = time.mktime(e['published_parsed'])
            if last_update < e_update or show_all:
                if not is_need_update:
                    is_need_update = True
                if self.event_listener.ask(e):
                    entities.append(e)
                if new_last_update < e_update:
                    new_last_update = e_update
        pl.last_update = new_last_update
        pl.entities = entities
        return pl

    def _download(self, entities, output_format, configs, cache, download_dir):
        options = self._build_converter_options(output_format, configs)
        # create a temporal directory to download a file by its link
        # to be sure that the file belongs to the link
        tmp = os.path.join(download_dir, 'tmp')
        os.makedirs(tmp, Bluetube.ACCESS_MODE, exist_ok=True)
        success, failure = [], []

        for en in entities:
            options = options + (en['link'],)

            # check the value in the given cache
            # to avoid downloading the same file twice
            new_link = cache.get(' '.join(options))
            if new_link:
                en['link'] = new_link
                success.append(en)
            else:
                status = self.executor.call(options, cwd=tmp)
                if status:
                    failure.append(en)
                    # clear the tmp directory that may have parts of
                    # not completely downloaded file. 
                    for f in os.listdir(tmp):
                        os.unlink(os.path.join(tmp, f))
                else:
                    fs = os.listdir(tmp)
                    assert len(fs) == 1, 'one link should march one file in tmp'
                    new_link = os.path.join(download_dir,
                                            os.path.basename(fs[0]))
                    # move the file out of the tmp directory
                    os.rename(os.path.join(tmp, fs[0]), new_link)
                    en['link'] = new_link
                    success.append(en)

                    # put the link to just downloaded file into the cache 
                    cache[' '.join(options)] = new_link

        os.rmdir(tmp)
        return success, failure

    def _build_converter_options(self, output_format, configs):
        options = ('--ignore-config',
                   '--ignore-errors',
                   '--mark-watched',)
        if output_format == OutputFormatType.audio:
            output_format = configs['output_format']
            spec_options = ('--extract-audio',
                            '--audio-format={}'.format(output_format),
                            '--audio-quality=9',  # 9 means worse
                            )
        elif output_format == OutputFormatType.video:
            of = configs.get('output_format')
            spec_options = ('--format', of,) if of else ()
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
        files = os.listdir(download_dir)  # update the list of files
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
            if len(fs):
                msg = 'Ready to be sent:\n{}'.format(' '.join(fs))
                self.event_listener.warn(msg)
        return bluetube_dir

    def _return_download_dir(self, bluetube_dir):
        if os.path.isdir(bluetube_dir):
            try:
                os.rmdir(bluetube_dir)
            except OSError:
                self.event_listener.warn('download directory not empty',
                                         bluetube_dir)
                self.event_listener.warn('\n  '.join(os.listdir(bluetube_dir)))

    def _get_bt_dir(self):
        if not os.path.exists(Bluetube.CUR_DIR) \
            or not os.path.isdir(Bluetube.CUR_DIR):
                os.makedirs(Bluetube.CUR_DIR, Bluetube.ACCESS_MODE)
        return Bluetube.CUR_DIR

# ============================================================================ #


def main():

    def add(bluetube, args):
        profiles = args.profiles if args.profiles else ['__download__']
        if not bluetube.add_playlist(args.add,
                                     OutputFormatType.from_char(args.type),
                                     profiles):
            sys.exit(-1)

    description='The script downloads youtube video as video or audio and sends to a bluetooth client device.'
    epilog = 'If no option specified the script shows feeds to choose, downloads and sends via bluetooth client.'
    parser = argparse.ArgumentParser(prog='bluetube', description=description)
    parser.epilog = epilog

    subparsers = parser.add_subparsers(title='Commands',
                                       description='Use the commands below to'
                                       'modify or show subscribed playlists.',
                                        help='')
    parser_add = subparsers.add_parser('add',
                                       help='add a URL to youtube playlist')
    parser_add.add_argument('-t', dest='type',
                            choices=['a', 'v'],
                            default='v',
                            help='a type of a file you want to get')
    parser_add.add_argument('-p', nargs='*',
                        dest='profiles',
                        help='one or multiple profiles')
    parser_add.set_defaults(func=add)

    parser_list = subparsers.add_parser('list', help='list all playlists')
    parser_list.set_defaults(func=lambda bt, _: bt.list_playlists())
    

    parser_remove = subparsers.add_parser('remove',
            help='remove a playlist by names of the author and the playlist')
    parser_remove.add_argument('--author', '-a',
                               type=str,
                               help='an author of a playlist to be removed')
    parser_remove.add_argument('--playlist', '-p',
                               type=str,
                               help='a playlist to be removed')
    parser_remove.set_defaults(func=lambda bt, args:
                                bt.remove_playlist(args.remove[0].strip(),
                                                   args.remove[1].strip()))

    parser.add_argument('--send', '-s',
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
    if hasattr(args, 'func'):
        args.func(bluetube, args)

    if args.send:
        bluetube.send()
    else:
        bluetube.run(args.show_all)
    print('Done')


if __name__ == '__main__':
    main()
