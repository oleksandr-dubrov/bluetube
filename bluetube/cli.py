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


from bluetube.bcolors import Bcolors


class CLI(object):
    '''Command line interface of the tool'''

    INDENTATION = 10
    MEDIA_PLAYER = 'vlc'

    INFORMS = {
        'empty database': 'No subscribed playlists.\n'
                          'Run "bluetube add -h" for more info.',
        'feed is fetching': ' ' * INDENTATION + '{}',
        'converter not found': 'Please install the converter.',
        }

    WARNS = {
        'device not found': 'Your bluetooth device is not accessible.\n'
                            'The script will download files to {} directory.',
        'download directory not empty': 'The download directory {} '
                                        'is not empty. Run "bluetube -s" '
                                        'to send the files or remove them.',
        'conversion is not needed': 'The files is in required format. '
                                    'No conversion needed.',
        'no editor': 'Specify your favorite text editor '
                     '(e.g. nano, vim, emacs, gedit) '
                     'and try again:',
        }

    ERRORS = {
        'profile not found': 'The profile "{}" for "{}"({}) not found',
        'playlist not found': '"{}" by "{}" not found',
        'downloader not found': 'The tool for downloading "{}"'
                                ' is not found in PATH',
        'failed to download': 'Failed to download "{}" for "{}"',
        'converter not found': 'The tool for converting video "{}"'
                               ' is not found in PATH',
        'failed to convert': 'Failed to convert the file {}.',
        'misformatted URL': '''Misformatted URL of the youtube list.
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
        'edit profile filed': '''Profiles are not correct.
Please try to edit them again''',
        }

    SUCCESSES = {
        'added': '{} by {} added successfully.',
        'feeds updated': "Feeds have been updated successfully."
        }

    def __init__(self, executor):
        self._executor = executor
        self._is_player = None

    def warn(self, msg, *args):
        '''warn the user by an arbitrary or predefined message'''
        Bcolors.warn('[WARNING] {}'.format(self._get_msg(msg,
                                                         CLI.WARNS, *args)))

    def inform(self, msg, *args, **kwargs):
        '''inform the user by an arbitrary or predefined message,
        set "capture" to specify the header of the message
        instead of [info]'''
        header = kwargs['capture'] if 'capture' in kwargs else 'info'
        print('[{}] {}'.format(header,
                               self._get_msg(msg, CLI.INFORMS, *args)))

    def error(self, msg, *args):
        '''show an error to the user'''
        Bcolors.error('[ERROR] {}'.format(self._get_msg(msg,
                                                        CLI.ERRORS, *args)))

    def success(self, msg, *args):
        '''inform about success'''
        if msg == 'feed updated':
            self.sound()
            return
        Bcolors.intense('[INFO] {}'.format(self._get_msg(msg,
                                                         CLI.SUCCESSES,
                                                         *args)))

    def out(self, msg):
        '''simple output'''
        print(msg)

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
                self._executor.open_url(link)
            elif i in open_player:
                print(f'Opening the link by {CLI.MEDIA_PLAYER}...')
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

    def selection_list(self, msg, lst, default):
        '''select an item from the list'''
        self.inform(f'{msg}')
        for i, e in enumerate(lst):
            self.inform(f'{i} - {e}')
        o = input(f'[{default}] -> ')
        try:
            if len(o) == 0:
                return default
            elif int(o) > len(lst):
                raise ValueError(o)
            else:
                return lst[int(o)]
        except ValueError as e:
            self.error(e)
            return self.selection_list(msg, lst, default)

    def multi_selection_list(self, msg, lst, default):
        '''select items from the list'''
        self.inform(f'{msg}')
        for i, e in enumerate(lst):
            self.inform(f'{i} - {e}')
        o = input(f'Choose items, separate by space [{default}]')
        items = o.split()
        ret = []
        try:
            for i in items:
                o = int(i.strip())
                if o > len(lst):
                    raise ValueError(o)
                else:
                    ret.append(lst[o])
        except ValueError as e:
            self.error(e)
            self.multi_selection_list(msg, lst, default)
        return ret

    def arbitrary_input(self):
        '''arbitrary input '''
        return input('>')
