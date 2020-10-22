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
import re

import toml

import importlib.resources as pkg_resources


class Profiles(object):
    '''
    Manages profiles in the TOML file.
    '''

    PROFILES_NAME = 'profiles.toml'
    BASE_PROFILE = '__download__'
    BT_DEVICE_ID = re.compile('^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')

    def __init__(self, bt_dir):
        path = os.path.join(bt_dir, Profiles.PROFILES_NAME)
        try:
            configs = self._read_file(path)
        except FileNotFoundError:
            # probably the script has just been installed
            # create the file from the template
            template = pkg_resources.read_text(__package__,
                                               Profiles.PROFILES_NAME)
            with open(path, 'w') as f:
                f.write(template)

            # retry
            configs = self._read_file(path)

        base = configs[Profiles.BASE_PROFILE]
        self._profiles = {}
        del configs[Profiles.BASE_PROFILE]
        for c in configs:
            b = copy.deepcopy(base)
            b.update(configs[c])
            self._profiles[c] = b

    def _read_file(self, path):
        try:
            configs = toml.load(path)
            self.check_base_download_configurations(configs)
            return configs
        except TypeError:
            raise ProfilesException(f'Cannot open {path}')
        except toml.TomlDecodeError:
            raise ProfilesException('Error while decoding TOML')

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
            opt = self._profiles[profile].get('send')
            if 'local_path' in opt:
                opt['local_path'] = os.path.expanduser(opt['local_path'])
            return self._profiles[profile].get('send')
        return None

    def check_profile(self, profile):
        '''check if the given profile exists'''
        return profile in self._profiles.keys()

    def get_profiles(self):
        '''get names of profiles'''
        return self._profiles.keys()

    def check_base_download_configurations(self, configs):
        if configs and Profiles.BASE_PROFILE in configs:
            base = configs[Profiles.BASE_PROFILE]
            if 'audio' in base and 'video' in base \
                and 'output_format' in base['audio'] \
                    and 'output_format' in base['video']:
                return
        raise ProfilesException(f'the {Profiles.BASE_PROFILE}'
                                'profile not found')

    def check_require_converter_configurations(self, profile):
        options = self.get_convert_options(profile)
        msg = f'no required "convert.output_format" in {profile}'
        if options is not None and 'output_format' not in options:
            raise ProfilesException(msg)

    def check_send_configurations(self, profile):
        opts = self.get_send_options(profile)
        if opts is not None:
            if 'local_path' in opts:
                local_path = os.path.expanduser(opts['local_path'])
                if not os.path.exists(local_path):
                    msg = f'local path does not exist in {profile}'
                    raise ProfilesException(msg)
                if not os.path.isdir(local_path):
                    msg = f'local path must be a directory, see {profile}'
                    raise ProfilesException(msg)
            if 'bluetooth_device_id' in opts:
                bt_id = opts['bluetooth_device_id']
                if not Profiles.BT_DEVICE_ID.match(bt_id):
                    msg = f'bluetooth device ID is malformatted in {profile}'
                    raise ProfilesException(msg)


class ProfilesException(Exception):
    '''The exception class for Profiles'''

    def __init__(self, msg):
        self._msg = msg

    def __str__(self):
        return self._msg
