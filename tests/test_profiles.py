import os
import unittest
from unittest.mock import patch

from bluetube.bluetube import Profiles, ProfilesException


class TestProfile(unittest.TestCase):

    TOML = 'toml.load'

    def setUp(self):
        this_path = os.path.dirname(os.path.abspath(__file__))
        self.sut = Profiles(os.path.normpath(this_path))

    def test_file_not_found(self):
        fn = 'bad_dirrr'
        with patch('builtins.open'):
            with self.assertRaises(FileNotFoundError) as e:
                Profiles(fn)
        exp_msg = 'No such file or directory'
        self.assertTrue(exp_msg in str(e.exception))

    def test_get_video_options(self):
        v_op = self.sut.get_video_options('mobile')
        self.assertTrue(v_op, 'no video options')
        self.assertTrue('output_format' in v_op, 'a key not found')

    def test_get_convert_options(self):
        c_op = self.sut.get_convert_options('mobile')
        self.assertTrue(c_op, 'no convert options')
        self.assertTrue('output_format' in c_op, 'a key not found')

    def test_no_required_configs(self):
        with patch('os.path.join'):
            no_base = {}
            with patch(TestProfile.TOML, return_value=no_base):
                with self.assertRaises(ProfilesException) as e:
                    Profiles('')
                    exp_msg = f'ProfilesException: the ' \
                              f'{Profiles.BASE_PROFILE} profile not found'
                    self.assertTrue(exp_msg == str(e.exception))

            no_base = {Profiles.BASE_PROFILE:
                       {'audio': {'output_format': 'mp3'},
                        'video': {'output_format': ''}},
                       'profile': {'convert': {}}}
            with patch(TestProfile.TOML, return_value=no_base):
                with self.assertRaises(ProfilesException) as e:
                    sut = Profiles('')
                    sut.check_send_configurations('profile')
                    sut.check_require_converter_configurations('profile')
                    exp_msg = 'Profiles exception: ' +\
                        'no required "convert.output_format" in profile'
                    self.assertTrue(exp_msg == str(e.exception))

    def test_merge_profile_to_base(self):
        configs = {Profiles.BASE_PROFILE:
                   {'audio': {'output_format': 'mp3'},
                    'video': {'output_format': 'mp4'}},
                   'profile1': {'convert': {'output_format': '3gp'}},
                   'profile2': {'send': {'local': 'path'}}}
        with patch(TestProfile.TOML, return_value=configs):
            sut = Profiles(' ')
        self.assertEqual(len(sut._profiles['profile1']), 3)
        self.assertEqual(len(sut._profiles['profile2']), 3)
        self.assertTrue(sut.get_convert_options('profile1'))
        self.assertTrue(sut.get_send_options('profile2'))
        self.assertFalse(sut.get_convert_options('profile2'))
        self.assertFalse(sut.get_send_options('profile1'))


if __name__ == "__main__":
    unittest.main()
