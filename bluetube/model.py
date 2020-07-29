'''
Created on Jul 29, 2020

@author: olexandr

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


class Playlist(object):
    '''
    Represents a playlist or channel. 
    '''

    def __init__(self, title, url):
        self._title = title
        self._url = url
        self._last_update = None
        self._output_format = OutputFormatType.audio
        self._profile = None

    def set_last_update(self, last_update):
        self._last_update = last_update

    def set_output_format_type(self, output_format_type):
        if isinstance(output_format_type, str):
            t = {'a': OutputFormatType.audio,
                 'v': OutputFormatType.video}[output_format_type]
        else:
            t = output_format_type
        self._output_format = t

    @property
    def title(self):
        return self._title

    @property
    def url(self):
        return self._url

    @property
    def last_update(self):
        return self._last_update

    @property
    def output_format(self):
        return self._output_format

    @property
    def profile(self):
        return self._profile
