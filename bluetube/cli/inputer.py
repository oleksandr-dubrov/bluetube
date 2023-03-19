from bluetube.cli.bcolors import Bcolors
from bluetube.cli.cli import CLI
from bluetube.cli.events import INDENTATION, Event
from bluetube.commandexecutor import CommandExecutor


class Inputer(CLI):
    '''The class gathers user input.'''

    def __init__(self, executor: CommandExecutor, yes: bool = False) -> None:
        self._executor = executor
        self._yes = yes
        self._player = None

    def set_media_player(self, mp: str):
        self._player = mp

    @staticmethod
    def do_continue():
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
        self._info(Event(f'{msg}'))
        for i, e in enumerate(lst):
            self._info(Event(f'{i} - {e}'))
        o = input(f'[{default}] -> ').strip()
        try:
            if len(o) == 0:
                return default
            elif int(o) > len(lst):
                raise ValueError(o)
            else:
                return lst[int(o)]
        except ValueError as e:
            self._error(Event(e))
            return self.selection_list(msg, lst, default)

    def multi_selection_list(self, msg, lst, default):
        '''select items from the list'''
        self._info(Event(f'{msg}'))
        for i, e in enumerate(lst):
            self._info(Event(f'{i} - {e}'))
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
            self._error(Event(e))
            self.multi_selection_list(msg, lst, default)
        return ret

    def arbitrary_input(self):
        '''arbitrary input '''
        return input('>').strip()
