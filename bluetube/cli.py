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

import webbrowser

from bluetube.bcolors import Bcolors


class CLI(object):
    '''Command line interface of the tool'''

    INDENTATION = 10
    MEDIA_PLAYER = 'vlc'

    INFORMS = {
        'empty database': 'The list of playlist is empty.\n'
                          'Use --add to add a playlist.',
        'feed is fetching': ' ' * INDENTATION + '{}',
        'converter not found': 'Please install the converter.',
        }

    WARNS = {
        'device not found': 'Your bluetooth device is not accessible.\n'
                            'The script will download files to {} directory.',
        'download directory not empty': 'The download directory {} '
                                        'is not empty. Cannot delete it.',
        }

    ERRORS = {
        'downloader not found': 'The tool for downloading "{}"'
                                ' is not found in PATH',
        'failed to download': 'Failed to download {} for {}',
        'converter not found': 'The tool for converting video "{}"'
                               ' is not found in PATH',
        'failed to convert': 'Failed to convert the file {}.',
        'misformatted URL':'''Misformatted URL of the youtube list.
Should be https://www.youtube.com/watch?v=XXX&list=XXX for a playlist,
or https://www.youtube.com/feeds/videos.xml?playlist_id=XXX for a channel.''',
        'playlist exists': 'The playlist {} by {} has already existed',
        'the base profile not found': '''The base profile is not found.
Check the config file. It must have something like this
[__base__]
    [__common__.audio]
    output_format = "mp3"
    [__common__.video]
    output_format = "mp4"
''',
        }

    SUCCESS = {
        'added': '{} by {} added successfully.'
        }

    def __init__(self, executor):
        self._executor = executor
        self._is_player = None

    def warn(self, msg, *args):
        '''warn the user by an arbitrary or predefined message'''
        Bcolors.warn(self._get_msg(msg, CLI.WARNS, args))

    def inform(self, msg, *args):
        '''inform the user by an arbitrary or predefined message'''
        if msg == 'feed updated':
            self.sound()
            return
        print(self._get_msg(msg, CLI.INFORMS, *args))

    def error(self, msg, *args):
        '''show an error to the user'''
        Bcolors.error(self._get_msg(msg, CLI.ERRORS, *args))

    def success(self, msg, *args):
        '''inform about success'''
        Bcolors.intense(self._get_msg(msg, CLI.SUCCESS, *args))

    def _get_msg(self, msg, msg_collection, *args):
        if msg in msg_collection:
            msg = msg_collection[msg].format(*args)
        return msg

    def sound(self):
        ''' inform the user by voice'''
        self._executor.call(('spd-say', '--wait', 'beep, beep.'))

    def do_continue(self):
        input('Press Enter to continue, Ctrl+c to interrupt.')
        return True

    def ask(self, feed_entry):
        '''ask if perform something'''
        # d for download
        d = ['d', 'D', 'В', 'в', 'Y', 'y', 'Н', 'н', 'yes', 'YES']
        # r for reject
        r = ['r', 'R', 'к', 'К', 'n', 'N', 'т', 'Т', 'no', 'NO']
        s = ['s', 'S', 'і', 'І']
        open_browser = ['b', 'B', 'и', 'И']
        open_player = ['p', 'P', 'З', 'з']

        if self._is_player is None:
            self._is_player = \
                self._executor.does_command_exist(CLI.MEDIA_PLAYER)

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
                    msg += ', {} to get a summary'
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
