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

import copy
import os

import toml


class Profiles(object):
    '''
    Manages profiles in the TOML file.
    '''

    PROFILES_NAME = 'profiles.toml'
    BASE_PROFILE = '__download__'

    def __init__(self, bt_dir):
        path = os.path.join(bt_dir, Profiles.PROFILES_NAME)
        try:
            configs = toml.load(path)
            self._verify_configurations(configs)
        except TypeError:
            raise ProfilesException('Cannot open {}'.format(path))
        except toml.TomlDecodeError:
            raise ProfilesException('Error while decoding TOML')
        except FileNotFoundError as e:
            raise ProfilesException(e)

        base = configs[Profiles.BASE_PROFILE]
        self._profiles = {}
        del configs[Profiles.BASE_PROFILE]
        for c in configs:
            b = copy.deepcopy(base)
            b.update(configs[c])
            self._profiles[c] = b

    def get_audio_options(self, profile):
        '''get options for audio'''
        if profile in self._profiles:
            return self._profiles[profile].get('audio', {})
        return None

    def get_video_options(self, profile):
        '''get options for video'''
        if profile in self._profiles:
            return self._profiles[profile].get('video', {})
        return None

    def get_convert_options(self, profile):
        if profile in self._profiles:
            return self._profiles[profile].get('convert')
        return None

    def get_send_options(self, profile):
        if profile in self._profiles:
            return self._profiles[profile].get('send')
        return None

    def check_profile(self, profile):
        '''check if the given profile exists'''
        return profile in self._profiles.keys()

    def _verify_configurations(self, configs):
        self.check_base_download_configurations(configs)
        self.check_require_converter_configurations(configs)
        self.check_send_configurations(configs)

    def check_base_download_configurations(self, configs):
        if configs and Profiles.BASE_PROFILE in configs:
            base = configs[Profiles.BASE_PROFILE]
            if 'audio' in base and 'video' in base:
                return
        raise ProfilesException('the base profile not found')

    def check_require_converter_configurations(self, configs):
        msg = 'no required "convert.output_format" in {}'
        for d in configs:
            if 'convert' in configs[d] \
                and 'output_format' not in configs[d]['convert']:
                    raise ProfilesException(msg.format(d))

    def check_send_configurations(self, configs):
        for d in configs:
            if 'send' in d and 'local_path' in d['send']:
                local_path = d['send']['local_path']
                if not os.path.exists(local_path):
                    msg = 'local path does not exist in {}'
                    raise ProfilesException(msg.format(d))
                if not os.path.isdir(local_path):
                    msg = 'local path must be a directory, see {}'
                    raise ProfilesException(msg.format(d))


class ProfilesException(Exception):
    '''The exception class for Profiles'''

    def __init__(self, msg):
        self._msg = 'Profiles exception: {}'.format(msg)

    def __str__(self):
        return self._msg
