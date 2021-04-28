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

from enum import Enum, unique


@unique
class OutputFormatType(Enum):
    '''
    Defines types of output formats: audio or video.
    '''
    _reseved = 0
    audio = 1
    video = 2

    @staticmethod
    def from_char(ch):
        '''create a value from character'''
        if ch in ['a', 'audio']:
            return OutputFormatType.audio
        elif ch in ['v', 'video']:
            return OutputFormatType.video
        return None

    @staticmethod
    def get_values():
        '''get all actual values'''
        return (OutputFormatType.audio, OutputFormatType.video, )

    @staticmethod
    def to_char(t: Enum):
        '''get name from type'''
        if t is OutputFormatType.video:
            return 'video'
        elif t is OutputFormatType.audio:
            return 'audio'
        else:
            assert 0, 'unknown type'


class Playlist(object):
    '''
    Represents a playlist or channel.
    '''

    def __init__(self, title, url):
        self.author = None
        self._title = title
        self._url = url
        self._last_update = 0
        self._output_format = OutputFormatType.audio
        self._profiles = []
        self._feedparser_data = None
        self._failed_entities = {}
        self._entities = []

    def set_output_format_type(self, output_format_type):
        if isinstance(output_format_type, str):
            t = {'audio': OutputFormatType.audio,
                 'video': OutputFormatType.video}[output_format_type]
        else:
            t = output_format_type
        self._output_format = t

    @property
    def feedparser_data(self):
        return self._feedparser_data

    @feedparser_data.setter
    def feedparser_data(self, fd):
        self._feedparser_data = fd

    @feedparser_data.deleter
    def feedparser_data(self):
        self._feedparser_data = None

    @property
    def title(self):
        return self._title

    @property
    def url(self):
        return self._url

    @property
    def last_update(self):
        return self._last_update

    @last_update.setter
    def last_update(self, lu):
        self._last_update = lu

    @property
    def output_format(self):
        return self._output_format

    @output_format.setter
    def output_format(self, output_format):
        self._output_format = output_format

    @property
    def profiles(self):
        return self._profiles

    @profiles.setter
    def profiles(self, p):
        self._profiles = p

    @property
    def entities(self):
        # TODO: dont! self._entities.extend(self.failed_entities)
        return self._entities

    @entities.setter
    def entities(self, ln):
        self._entities = ln

    @entities.deleter
    def entities(self):
        self._entities = []

    @property
    def failed_entities(self):
        return self._failed_entities

    def add_failed_entities(self, fl):
        for p in fl:
            if len(fl[p]):
                self._failed_entities.setdefault(p, []).extend(fl[p])

    @failed_entities.deleter
    def failed_entities(self):
        self._failed_entities.clear()
