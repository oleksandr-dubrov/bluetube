import os
import unittest

from bluetube.bluetube import Profiles, ProfilesException


class Test(unittest.TestCase):

    def setUp(self):
        this_path = os.path.dirname(os.path.abspath(__file__))
        self.sut = Profiles(os.path.normpath(this_path))

    def test_file_not_found(self):
        fn = 'bad_dirrr'
        with self.assertRaises(ProfilesException) as e:
            Profiles(fn)
        exp_msg = 'No such file or directory'
        self.assertTrue(exp_msg in str(e.exception))

    def test_get_video_options(self):
        v_op = self.sut.get_video_options('_default')
        self.assertTrue(v_op, 'no video options')
        self.assertTrue('output_format' in v_op, 'a key not found')


if __name__ == "__main__":
    unittest.main()