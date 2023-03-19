from bluetube.cli.bcolors import Bcolors
from bluetube.cli.events import Error, Info, Success, Warn


class CLI(object):
    '''Command line interface of the tool'''

    def __init__(self):
        self._handlers = {Info.__name__: self._info,
                          Success.__name__: self._success,
                          Error.__name__: self._error,
                          Warn.__name__: self._warn}

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
        Bcolors.intense('[INFO] {}'.format(self._get_msg(event.msg,
                                                         Success.MSGS,
                                                         *event.args)))

    def _get_msg(self, msg, msgs, *args):
        if msg in msgs:
            msg = msgs[msg].format(*args)
        return msg
