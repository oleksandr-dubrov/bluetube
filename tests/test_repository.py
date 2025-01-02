import shutil
import tempfile
import time
import unittest
from pathlib import Path

import sqlalchemy
from feedparser.util import FeedParserDict

from bluetube.model import OutputFormatType
from bluetube.repository import Repository, RepositoryException


class TestPlaylist(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix='bt_dir'))
        self.sut = Repository(self.tmp_dir).__enter__()
        self.sut.create_schema()

    def tearDown(self) -> None:
        self.sut.__exit__(None, None, None)
        if self.tmp_dir:
            shutil.rmtree(self.tmp_dir)

    def add_playlist(self, url, author, profile):
        return self.sut.add_playlist(
            title="playlist_1",
            url=url,
            output_format=OutputFormatType.audio,
            author=author,
            profile=profile)

    def make_author_playlist(self, author="author_1", profile="profile_1"):
        author = self.sut.add_author(name=author)
        profile = self.sut.upsert_profile(profile)
        url = f"http://example.com/rss/{author}/{profile}/"
        return author, self.add_playlist(url, author, profile)

    def build_publication(self, published):
        return FeedParserDict({"title": "title", "link": "link", "description": "description", "published_parsed": time.gmtime(published), "id": "id", "yt_videoid": "123"})

    def test_unique_by_url(self): 
        author = self.sut.add_author(name="author_1")
        profile = self.sut.add_profile("profile_1")
        url = "http://example.com/rss"
        self.add_playlist(url, author, profile)

        with self.assertRaises(RepositoryException) as err:
            self.sut.add_playlist(
                title="playlist_2",
                url=url,
                output_format=OutputFormatType.audio,
                author=author,
                profile=profile)
        self.assertIn("UNIQUE constraint failed: playlist.url", str(err.exception))

    def test_delete_playlists_if_author_deleted(self):
        author, _ = self.make_author_playlist()

        self.sut.remove_author(author)

        playlists = self.sut.get_all_playlists()
        self.assertFalse(len(playlists))

    def test_delete_author_without_playlist(self):
        _, playlist = self.make_author_playlist()

        self.sut.remove_playlist(playlist)

        authors = self.sut.get_all_authors()
        self.assertFalse(len(authors))


    def test_get_publication_sorted(self):
        _, pl1 = self.make_author_playlist(author="author_1")
        _, pl2 = self.make_author_playlist(author="author_2")
        pubs = [self.build_publication(published=2),
                self.build_publication(published=1)]
        self.sut.add_publications(pl2, pubs)
        self.sut.add_publications(pl1, pubs)

        pubs = self.sut.get_all_publications()
        self.assertEqual(4, len(pubs))

        # check sorted by authors
        self.assertEqual("author_1", pubs[0].playlist.author.name)
        self.assertEqual("author_1", pubs[1].playlist.author.name)
        self.assertEqual("author_2", pubs[2].playlist.author.name)
        self.assertEqual("author_2", pubs[3].playlist.author.name)

        # check sorted by time
        self.assertTrue(pubs[1].published > pubs[0].published)
        self.assertTrue(pubs[3].published > pubs[2].published)


if __name__ == "__main__":
    unittest.main()

