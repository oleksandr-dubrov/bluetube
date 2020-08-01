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

import os

import toml


class Profiles(object):
    '''
    Manages profiles in the TOML file.
    '''

    PROFILES_NAME = 'profiles.toml'

    def __init__(self, bt_dir):
        path = os.path.join(bt_dir, Profiles.PROFILES_NAME)
        try:
            self._profiles = toml.load(path)
        except TypeError:
            raise ProfilesException('Cannot open {}'.format(path))
        except toml.TomlDecodeError:
            raise ProfilesException('Error while decoding TOML')
        except FileNotFoundError as e:
            raise ProfilesException(e)

    def get_download_options(self, profile):
        if self._profiles.has_key(profile):
            return self._profiles[profile].get('download', {})
        return None

    def get_video_options(self, profile):
        if self._profiles.has_key(profile):
            return self._profiles[profile].get('video', {})
        return None

    def get_sender_options(self, profile):
        if self._profiles.has_key(profile):
            return self._profiles[profile].get('bluetooth')


class ProfilesException(Exception):
    '''The exception class for Profiles'''

    def __init__(self, msg):
        self._msg = 'Profiles exception: {}'.format(msg)

    def __str__(self):
        return self._msg
