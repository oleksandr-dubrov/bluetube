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
    BASE_PROFILE = '__base__'

    def __init__(self, bt_dir):
        path = os.path.join(bt_dir, Profiles.PROFILES_NAME)
        try:
            configs = toml.load(path)
            self._verify_configurations(configs)
            base = configs[Profiles.BASE_PROFILE]
        except TypeError:
            raise ProfilesException('Cannot open {}'.format(path))
        except toml.TomlDecodeError:
            raise ProfilesException('Error while decoding TOML')
        except FileNotFoundError as e:
            raise ProfilesException(e)

        self._profiles = {}
        for c in configs:
            base.update(configs[c])
            self._profiles[c] = base

    def get_audio_options(self, profile):
        if profile in self._profiles:
            return self._profiles[profile].get('audio', {})
        return None

    def get_video_options(self, profile):
        if profile in self._profiles:
            return self._profiles[profile].get('video', {})
        return None

    def get_sender_options(self, profile):
        if profile in self._profiles:
            return self._profiles[profile].get('send')

    def check_profile(self, profile):
        '''check if the given profile exists'''
        return profile in self._profiles.keys()

    def _verify_configurations(self, configs):
        if configs and Profiles.BASE_PROFILE in configs:
            base = configs[Profiles.BASE_PROFILE]
            if 'audio' in base and 'video' in base:
                return 
        raise ProfilesException('the base profile not found')


class ProfilesException(Exception):
    '''The exception class for Profiles'''

    def __init__(self, msg):
        self._msg = 'Profiles exception: {}'.format(msg)

    def __str__(self):
        return self._msg
