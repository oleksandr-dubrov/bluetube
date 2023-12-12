'''
A set of events the CLI package should be able to handle.
'''

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
        'no internet': 'Check your Internet connection.',
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
