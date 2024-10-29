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

from enum import Enum, unique
from pathlib import Path
from sqlalchemy import ForeignKey, TypeDecorator, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase
from typing import List
from typing import Optional
from sqlalchemy.orm import Mapped   # TODO: isort it properly   
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship, registry
from sqlalchemy import Table, Column, Integer, String
from sqlalchemy.schema import MetaData

mapper_registry = registry()


class PathType(TypeDecorator):
    impl = String

    def process_bind_param(self, value, dialect):
        if isinstance(value, Path):
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return Path(value)
        return value


@unique
class OutputFormatType(Enum):
    '''
    Defines types of output formats: audio or video.
    '''
    _reseved = 0
    audio = 1
    video = 2

    @staticmethod
    def from_char(ch):
        '''create a value from character'''
        if ch in ['a', 'audio']:
            return OutputFormatType.audio
        elif ch in ['v', 'video']:
            return OutputFormatType.video
        return None

    @staticmethod
    def get_values():
        '''get all actual values'''
        return (OutputFormatType.audio, OutputFormatType.video, )

    @staticmethod
    def to_char(t: Enum):
        '''get name from type'''
        if t is OutputFormatType.video:
            return 'video'
        elif t is OutputFormatType.audio:
            return 'audio'
        else:
            assert 0, 'unknown type'


@unique
class PublicationStatus(str, Enum):
    remote = "remote"  # a remote item
    chosen = "chosen"  # an item is selected to download
    downloaded = "downloaded"  # an item successfully downloaded
    converted = "converted"  # an item successfully converted
    failed = "failed"  # failed to downdload or converted
    sent = "sent"  # an item has been sent


@mapper_registry.mapped
class Author:
    """
    An author of the channel of playlist.
    """

    __tablename__ = "author"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    playlists: Mapped[List["Playlist"]] = relationship(back_populates="author", cascade="all, delete-orphan")



@mapper_registry.mapped
class Profile:
    """
    Profile is a name of downloading and converting configurations.
    """
    
    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)


@mapper_registry.mapped
class Publication:
    """
    Represent a single entity in the feed either an audio or video file.
    It corresponds with the RSS feed common Elements.
    See https://feedparser.readthedocs.io/en/latest/common-rss-elements.html#accessing-common-channel-elements
    """

    __tablename__ = "publication"

    id: Mapped[int] = mapped_column(primary_key=True)
    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlist.id"))

    title: Mapped[str] = mapped_column(String(255))
    link: Mapped[str] = mapped_column(String(2048))  # TODO: validate URL
    remove_id: Mapped[str] = mapped_column(String(255))  # an item id e.g. a Youtube video ID
    local_path: Mapped[Optional[Path]] = mapped_column(PathType(2048))  # TODO: validate local path
    description: Mapped[str] = mapped_column(String(2048))  # TODO: change to some text field not to limit the length
    published: Mapped[int]
    entry_id: Mapped[str] = mapped_column(String(2048))  # e.g. 'http://example.org/guid/1'
    playlist: Mapped["Playlist"] = relationship()
    status: Mapped[PublicationStatus]


@mapper_registry.mapped
class Playlist:
    """
    Represents a playlist or channel.
    """

    __tablename__ = 'playlist'

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("author.id"))
    profile_id: Mapped[int] = mapped_column(ForeignKey("profile.id"))

    author: Mapped["Author"] = relationship(back_populates="playlists")
    title: Mapped[str] = mapped_column(String(128))
    url: Mapped[str] = mapped_column(String(128), unique=True)
    last_update: Mapped[int]
    output_format: Mapped[OutputFormatType]
    profile: Mapped[Profile] = relationship()
    entities: Mapped[Optional[Publication]] = relationship()

    def set_output_format_type(self, output_format_type):
        if isinstance(output_format_type, str):
            t = {'audio': OutputFormatType.audio,
                 'video': OutputFormatType.video}[output_format_type]
        else:
            t = output_format_type
        self._output_format = t

    def __str__(self):
        return f'{type(self).__name__}: {self.author} - {self.title}'

    def __repl__(self):
        return f'{type(self).__name__}: {self.author} - {self.title}'
