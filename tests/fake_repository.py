import json
import random
import time

from feedparser.util import FeedParserDict

from bluetube.model import (Author, OutputFormatType, Playlist, Profile,
                            Publication, PublicationStatus)
from tests.fake_db import FAKE_DB


def get_id():
    return random.randrange(1, 9999)


class FakeRepository:

    def __init__(self):
        data = json.loads(FAKE_DB)
        profile = Profile()
        profile.id = get_id()
        profile.name = "mobile"

        authors: dict[str, Author] = {}
        for en in data:
            author = Author()
            author.id = get_id()
            author.name = en["author"]
            author.playlists = []
            authors[author.name] = author

        for en in data:
            for pl in en["playlists"]:
                author = authors[en["author"]]
                playlist = Playlist()
                playlist.id = get_id()
                playlist.author = author  # this assignment also adds the playlist to author
                playlist.author_id = author.id
                playlist.output_format = OutputFormatType.from_char(pl["out_format"])
                playlist.profile = profile
                playlist.profile_id = profile.id
                playlist.publications = []
                playlist.title = pl["title"]
                playlist.url = pl["url"]
                pub = Publication()  # add a dummy publication to get the last update time
                pub.published = pl["last_update"]
                playlist.publications.append(pub)

        self.authors = authors
        self.publications = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def get_all_authors(self) -> list[Author]:
        return list(self.authors.values())

    def add_publications(self, playlist: Playlist, publications: list[FeedParserDict]) -> list[Publication]:
        """Add publications to the playlist."""
        added = []
        for pub in publications:
            p = Publication(playlist=playlist,
                            title=pub.title,
                            link=pub.link,
                            remote_id=pub['yt_videoid'],
                            description=pub.description,
                            published=time.mktime(pub.published_parsed),
                            entry_id=pub.id,
                            status=PublicationStatus.remote)
            p.id = get_id()
            added.append(p)
        self.publications.extend(added)
        return added

    def update_publication(self, publication: Publication) -> Publication:
        self.publications = [publication if p.id == publication.id else p for p in self.publications]
        return self.publications

    def get_all_publications(self):
        self.publications.sort(key=lambda x: x.published, reverse=True)
        return self.publications
