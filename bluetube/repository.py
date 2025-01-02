import dbm
import functools
import logging
import shelve
import time
from pathlib import Path
from typing import Optional, final

import sqlalchemy
from feedparser.util import FeedParserDict
from sqlalchemy import asc, create_engine, select
from sqlalchemy.orm import Session, joinedload

from bluetube.model import (Author, OutputFormatType, Playlist, Profile,
                            Publication, PublicationStatus, mapper_registry)

logger = logging.getLogger(__name__)


class RepositoryException(Exception):
    """Repository exception"""


def catch_db_exception(target):
    '''A decorator that catches AWS client errors,
    logs it and returns an empty list.'''

    @functools.wraps(target)
    def _catch(*args, **kwargs):
        try:
            return target(*args, **kwargs)
        except sqlalchemy.exc.IntegrityError as e:
            logging.error(str(e))
            raise RepositoryException(e.args[0])  # TODO: convert to user-readble
    return _catch


@final
class Repository(object):

    DBFILENAME = "bluetube.db"
    SQLITE_FILE = "bluetube.sqlite.db"

    verbose = False

    def __init__(self, db_dir: Path):
        self.db_file = db_dir / Repository.DBFILENAME
        sqlite_file = db_dir / Repository.SQLITE_FILE
        self._engine = create_engine(f"sqlite+pysqlite:///{sqlite_file}", echo=Repository.verbose)
        self._session = None

    def __enter__(self):
        # add this contex manager to avoid all troubles with closed sessions
        self._session = Session(self._engine, expire_on_commit=False)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._session.close()
        self._session = None

    @catch_db_exception
    def add_playlist(self,
                     author: Author,
                     title: str,
                     url: str,
                     output_format: OutputFormatType,
                     profile: Profile) -> Playlist:
        pl = Playlist(
            author=author,
            title=title,
            url=url,
            output_format=output_format,
            profile=profile)
        self._session.add(pl)
        self._session.commit()
        return pl

    def get_playlist(self, author: Author, title: str) -> Optional[Playlist]:
        smth = select(Playlist).where(Playlist.title == title).where(Playlist.author_id == author.id)
        return self._session.scalars(smth).first()

    def remove_playlist(self, playlist: Playlist) -> None:
        self._session.delete(playlist)
        if not len(playlist.author.playlists):
            # remove author without playlists
            self.remove_author(playlist.author)
        self._session.commit()

    def add_author(self, name: str) -> Author:
        author = Author(name=name)
        self._session.add(author)
        self._session.commit()
        return author

    def get_author(self, name: str) -> Optional[Author]:
        smth = select(Author).where(Author.name == name)
        return self._session.scalars(smth).first()

    def upsert_author(self, name: str) -> Author:
        smth = select(Author).where(Author.name == name)
        resutl = self._session.scalars(smth).first()
        if resutl:
            return resutl
        else:
            return self.add_author(name)

    def remove_author(self, author: Author):
        self._session.delete(author)
        self._session.commit()

    def add_profile(self, name: str) -> Profile:
        profile = Profile(name=name)
        self._session.add(profile)
        self._session.commit()
        return profile

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
            added.append(p)
        self._session.add_all(added)
        self._session.commit()
        return added

    def update_publication(self, publication: Publication) -> Publication:
        """Update a publication"""
        self._session.add(publication)
        self._session.commit()

    def get_all_publications(self):
        stmt = select(Publication).join(Publication.playlist
                                        ).join(Playlist.author
                                               ).order_by(Author.name
                                                          ).order_by(asc(Publication.published))
        return self._session.scalars(stmt).all()

    def get_all_playlists(self) -> list[Playlist]:
        stmt = select(Playlist)
        return self._session.scalars(stmt).all()

    def get_all_authors(self) -> list[Author]:
        stmt = select(Author).options(joinedload("*"))
        return self._session.scalars(stmt).unique().all()

    def upsert_profile(self, name: str) -> Profile:
        smth = select(Profile).where(Profile.name == name)
        result = self._session.scalars(smth).first()
        if result:
            return result
        else:
            return self.add_profile(name)

    def is_empty(self) -> bool:
        stmt = select(Author).options(joinedload("*"))
        return self._session.scalars(stmt).all().count() == 0

    def create_schema(self) -> None:
        """Create a DB schema if it does not exist."""
        mapper_registry.metadata.create_all(self._engine)


class DbConverter(object):
    """This class migrates JSON to DB."""

    DB_NAME = 'bluetube'

    def __init__(self, bt_dir: Path):
        self.bt_dir = bt_dir
        self.db_file = bt_dir / Repository.DBFILENAME
        self.sqlite = bt_dir / Repository.SQLITE_FILE

    def migrate(self):
        '''migrate DB'''
        logger.info('exporting db...')
        repo = Repository(self.bt_dir)
        repo.create_schema()

        pls = []
        profiles = {}
        authors = {}
        entities = self._pull()
        if not entities:
            logger.info("nothing to convert")
            return
        for x in entities:
            author = authors.setdefault(x['author'], Author(name=x["author"]))
            for y in x['playlists']:
                profile = ",".join(y["profiles"])
                profile = profiles.setdefault(profile, Profile(name=profile))
                p = Playlist(author=author,
                             title=y["title"],
                             url=y["url"],
                             output_format=y["out_format"],
                             profile=profile)
                pls.append(p)
        logger.info("Migrated:")
        logger.info(f" - {len(profiles)} profiles,")
        logger.info(f" - {len(authors)} authors")
        logger.info(f" - {len(pls)} playlists")

        with Session(repo._engine) as session:
            session.add_all(pls)
            session.commit()

    def _create_ro_connector(self):
        '''create DB connector in read-only mode'''
        try:
            return shelve.open(self.db_file, flag='r')
        except dbm.error:
            return None

    def _pull(self):
        'pull data from the DB'
        if (db := self._create_ro_connector()):
            authors = db.get('feeds', [])
            self._close(db)
            return authors
        return None

    def _close(self, db):
        try:
            db.close()
        except ValueError as e:
            logger.info('Probably your changes were lost. Try again')
            raise e
