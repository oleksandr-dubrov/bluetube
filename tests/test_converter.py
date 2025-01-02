import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock

from feedparser.util import FeedParserDict

from bluetube.converter import FfmpegConverter
from bluetube.model import OutputFormatType, PublicationStatus
from bluetube.profiles import Profiles
from bluetube.repository import Repository


class TestConverter(TestCase):

    def setUp(self):
        self.executor = MagicMock()
        publisher = MagicMock()
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="bt_dir"))
        self.sut = FfmpegConverter(self.executor, publisher, self.tmp_dir)
        self.repo = Repository(self.tmp_dir).__enter__()
        self.profiles = Profiles(Path(__file__).parent)
        self.populate_db()

    def tearDown(self) -> None:
        self.repo.__exit__(None, None, None)
        if self.tmp_dir:
            shutil.rmtree(self.tmp_dir)

    def populate_db(self):
        self.repo.create_schema()

        author = self.repo.add_author(name="author_1")
        profile = self.repo.add_profile("mobile")
        return self.repo.add_playlist(
            title="playlist_1",
            url="http://example.com/rss",
            output_format=OutputFormatType.audio,
            author=author,
            profile=profile)

    def make_publications(self):
        pl = self.repo.get_all_playlists()[0]
        pub = FeedParserDict({"title": "title", "link": "link", "description": "description", "published_parsed": time.gmtime(1), "id": "id", "yt_videoid": 123})
        return self.repo.add_publications(pl, [pub])

    def test_no_local_path_faled(self):
        pub = self.make_publications()[0]
        pub.local_path = None
        config = self.profiles.get_video_options(pub.playlist.profile)

        new_pub = self.sut.convert(pub, config)
        self.assertIsNone(pub.local_path, "local path should not be changed")
        self.assertTrue(PublicationStatus.failed is new_pub.status)

    def test_converted_success(self):
        self.executor.call = MagicMock(return_value=0)

        pub = self.make_publications()[0]
        pub.local_path = Path(__file__)  # set this file since it exists
        config = self.profiles.get_video_options(pub.playlist.profile)

        new_pub = self.sut.convert(pub, config)
        self.assertEquals(".mp4", new_pub.local_path.suffix)
        self.assertTrue(PublicationStatus.converted is new_pub.status)

    def test_converted_failed(self):
        self.executor.call = MagicMock(return_value=1)

        pub = self.make_publications()[0]
        pub.local_path = Path(__file__)  # set this file since it exists
        config = self.profiles.get_video_options(pub.playlist.profile)

        new_pub = self.sut.convert(pub, config)
        self.assertNotEquals(".mp4", new_pub.local_path.suffix)
        self.assertTrue(PublicationStatus.failed is new_pub.status)

    def test_is_ready(self):
        self.executor.call = MagicMock(return_value=1)
        status = self.sut.is_ready()
        self.assertFalse(status)


if __name__ == "__main__":
    unittest.main()
