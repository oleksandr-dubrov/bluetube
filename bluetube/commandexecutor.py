import functools
import logging
import os
import subprocess
import webbrowser


def cache(func):
    '''a method decorator for cache'''
    cache.cache = {}

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        str_args = ' '.join(args[0])
        if str_args in cache.cache:
            return cache.cache[str_args]
        else:
            ret = func(self, *args, **kwargs)
            cache.cache[str_args] = ret
            return ret
    return wrapper


class CommandExecutor(object):
    '''This class run the commands in the shell'''

    def __init__(self):
        cache.cache = {}
        self._debug = logging.getLogger(__name__).debug

    @cache
    def call(self, args, cwd=None,
             suppress_stdout=False, suppress_stderr=False):
        if cwd is None:
            cwd = os.getcwd()
        call_env = os.environ
        return_code = 0
        stdout, stderr = None, None
        try:
            self._debug('RUN: {}'.format(' '.join([a for a in args])))
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
            self._debug(e.strerror)
        self._debug(f'Return code: {return_code}')
        return return_code

    def does_command_exist(self, name, dashes=2):
        '''call a command with the given name
        and expects that it has option --version'''
        return not self.call((name, '{}version'.format(dashes * '-')),
                             suppress_stdout=True,
                             suppress_stderr=True)

    def open_url(self, link):
        '''open URL in default browser'''
        print('Opening the link in the default browser...')
        webbrowser.open(link, new=2)

    def call_in_background(self, args):
        '''call args in background and forget'''
        try:
            p = subprocess.Popen(args,
                                 stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            self._debug('Background process has started.')
            self._debug(f'PID - {p.pid}, command - {" ".join(args)}')
        except FileNotFoundError as e:
            print(e)
