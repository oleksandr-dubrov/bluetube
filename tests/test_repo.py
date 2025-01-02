import json
import random

from sqlalchemy import create_engine

from bluetube.model import OutputFormatType, Publication, PublicationStatus
from bluetube.repository import Repository
from tests.fake_db import FAKE_DB


def get_id():
    return random.randrange(1, 9999)


class TestRepository(Repository):

    def __init__(self):
        self._engine = create_engine("sqlite+pysqlite:///:memory:", echo=True)
        self._session = None

        self.create_schema()

    def store_test_data(self):
        data = json.loads(FAKE_DB)

        with self:
            profile = self.upsert_profile(name="mobile")
            for en in data:
                author = self.add_author(en["author"])
                for pl in en["playlists"]:
                    playlist = self.add_playlist(
                        author, pl["title"], pl["url"],
                        OutputFormatType.from_char(pl["out_format"]), profile)

                    pub = Publication()  # add a dummy publication to get the last update time
                    pub.title = "title"
                    pub.link = "link"
                    pub.remote_id = "remote id"
                    pub.description = "description"
                    pub.entry_id = "entry id"
                    pub.status = PublicationStatus.sent
                    pub.published = pl["last_update"]
                    playlist.publications.append(pub)
                    self.update_playlist(playlist)

    @property
    def publications(self):
        with self:
            return self.get_all_publications()
