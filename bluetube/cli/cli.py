

from bluetube.cli.bcolors import Bcolors

INDENTATION = 10


class Event(object):
    '''The base event class.'''
    def __init__(self, msg: str, *args, **kwargs) -> None:
        self.msg = msg
        self.args = args
        self.kwargs = kwargs


class Success(Event):
    '''A successfull event.'''
    MSGS = {
        'added': '{} by {} added successfully.',
        'feeds updated': "Feeds have been updated successfully."
        }

    def __init__(self, msg: str, *args, **kwargs) -> None:
        super().__init__(msg, *args, **kwargs)


class Error(Event):
    '''An error event.'''
    MSGS = {
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

    def __init__(self, msg: str, *args, **kwargs) -> None:
        super().__init__(msg, *args, **kwargs)


class Info(Event):
    '''An informational event.'''
    MSGS = {
        'empty database': 'No subscribed playlists.\n'
                          'Run "bluetube add -h" for more info.',
        'feed is fetching': ' ' * INDENTATION + '{}',
        'converter not found': 'Please install the converter.',
        }

    def __init__(self, msg: str, *args, **kwargs) -> None:
        super().__init__(msg, *args, **kwargs)


class Warn(Event):
    '''A warning event.'''
    MSGS = {
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
        'no media player': 'Specify a media player that can open a remote URI'
                           ' (e.g. vlc) '
                           'or put "-" if you do not want to use it',
        }

    def __init__(self, msg: str, *args, **kwargs) -> None:
        super().__init__(msg, *args, **kwargs)


class CLI(object):
    '''Command line interface of the tool'''

    def __init__(self, executor, yes=False):
        self._executor = executor
        self._player = None
        self._yes = yes
        self._handlers = {Info.__name__: self._info,
                          Success.__name__: self._success,
                          Error.__name__: self._error,
                          Warn.__name__: self._warn}

    def update(self, event: Event):
        '''todo'''
        self._handlers[type(event).__name__](event)

    def set_media_player(self, mp: str):
        self._player = mp

    def _warn(self, event):
        '''warn the user by an arbitrary or predefined message'''
        Bcolors.warn('[WARNING] {}'.format(self._get_msg(event.msg,
                                                         Warn.MSGS,
                                                         *event.args)))

    def _info(self, event: Info):
        '''inform the user by an arbitrary or predefined message,
        set "capture" to specify the header of the message
        instead of [info]'''
        header = event.kwargs['capture']\
            if 'capture' in event.kwargs else 'info'
        print('[{}] {}'.format(header,
                               self._get_msg(event.msg,
                                             Info.MSGS,
                                             *event.args)))

    def _error(self, event: Error):
        '''show an error to the user'''
        Bcolors.error('[ERROR] {}'.format(
            self._get_msg(event.msg, Error.MSGS, *event.args)))

    def _success(self, event: Success):
        '''inform about success'''
        if event.msg == 'feed updated':
            self._sound()
            return
        Bcolors.intense('[INFO] {}'.format(self._get_msg(event.msg,
                                                         Success.MSGS,
                                                         *event.args)))

    def _get_msg(self, msg, msgs, *args):
        if msg in msgs:
            msg = msgs[msg].format(*args)
        return msg

    def _sound(self):
        ''' inform the user by voice'''
        self._executor.call(('spd-say', '--wait', 'beep, beep.'))

    def do_continue(self):
        input('Press Enter to continue, Ctrl+c to interrupt.')
        return True

    def ask(self, feed_entry):
        '''ask if perform something'''
        if self._yes:
            return True
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
            i = i.strip()
            if i in d:
                return True
            elif i in r:
                return False
            elif i in s:
                print('Summary:\n{}'.format(feed_entry['summary']))
            elif i in open_browser:
                self._executor.open_url(link)
            elif i in open_player:
                print(f'Opening the link by {self._player}...')
                self._executor.call_in_background((self._player, link))
            else:
                msg = '{}{} to download, {} to reject, {} to open in a browser'
                params = (Bcolors.FAIL, d[0], r[0], open_browser[0])
                if self._player:
                    msg += ', {} to open in a media player'
                    params += (open_player[0], )
                if feed_entry['summary']:
                    msg += ', {} to get a summary'
                    params += (s[0], )
                msg += '.{}'.format(Bcolors.ENDC)
                Bcolors.error(msg.format(*params))

    def _make_question_to_ask(self, feed_entry):
        pub = feed_entry['published_parsed']
        params = {'ind': 2 * INDENTATION * ' ',
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
        if self._player:
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
        o = input(f'[{default}] -> ').strip()
        try:
            if len(o) == 0:
                return default
            elif int(o) > len(lst):
                raise ValueError(o)
            else:
                return lst[int(o)]
        except ValueError as e:
            self._error(e)
            return self.selection_list(msg, lst, default)

    def multi_selection_list(self, msg, lst, default):
        '''select items from the list'''
        self.inform(f'{msg}')
        for i, e in enumerate(lst):
            self.inform(f'{i} - {e}')
        o = input(f'Choose items, separate by space [{default}]').strip()
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
            self._error(e)
            self.multi_selection_list(msg, lst, default)
        return ret

    def arbitrary_input(self):
        '''arbitrary input '''
        return input('>').strip()
