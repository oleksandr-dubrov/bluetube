# Bluetube. Contributing

# 1 Obtain sources

    git clone https://github.com/oleksandr-dubrov/bluetube.git

# 2 Installing
It's recommended to install the sources into a [virtual environment](https://docs.python.org/3/tutorial/venv.html):

    python3 -m virtualenv ve
    . ve/bin/activate

To install *bluetube* in the development mode, run:

    cd bluetube
    pip install -r dependencies-dev.txt
    pip install -e .

# 3 Get RSS feed from the list
Let's look at the URL below:

`https://www.youtube.com/watch?v=TcA4hhX81cg&list=PLqWhsEuaxvZt3bwQpJfecWH3g0xDyvJs_.`

The list ID that follows `&list=` is `PLqWhsEuaxvZt3bwQpJfecWH3g0xDyvJs_`.
This ID should be placed in `https://www.youtube.com/feeds/videos.xml?playlist_id=YOURPLAYLISTIDHERE` instead of `YOURPLAYLISTIDHERE`.

# 4 Download and convert
The script uses *youtube-dl* to download videos.
In order to set the download video format you can check the [FORMAT SELECTION](https://github.com/ytdl-org/youtube-dl/blob/master/README.md#format-selection) section on the *youtube-dl* website.

For more flexible converting use *ffmpeg*. To configure codecs options please consult [ffmpeg options](https://ffmpeg.org/ffmpeg.html#Options).


# 5 Data structure
The data are stored in *shelve* DB in the home directory of the script.
The structure is represented in JSON, which looks like this:

     {
        feeds: [
            {
                "author": "author1":
                "playlists": [
                   {
                      "title": "the name of an entity",
                      "url": "url of the entity",
                      "last_update": 1548951984,
                      "out_format": "audio" or "video",
                      "profile": "_default"
                      ...
                   },
                   {
                       ...
                   }
                ],
            },
            {
                "author": "author2":
                "playlists: [
                    ...
                 ],
              ...
            }
        ]
    }


# 6 Bluetooth
The script extends and uses PyOBEX (and PyBluez) to send files via bluetooth.
A few experiments showed that the most appropriate socket timeout is 120 seconds.
Unlike the base implementation, the extended version of the method reads the data from the file stream rather than reading all file in memory before sending.

# 7 Tests
All tests are based on the *unittest* framework. To start all tests, run

    python -m unittest

Don't forget to run *tox* before commit:

    tox

# 8 Links
[Python 3](https://www.python.org).

[Feed parser](https://pythonhosted.org/feedparser/introduction.html).

[YouTube-dl](https://rg3.github.io/youtube-dl/).

[ffmpeg](https://ffmpeg.org/).

[Markdown](https://daringfireball.net/projects/markdown/).

[libbluetooth-dev](https://packages.debian.org/sid/libbluetooth-dev).

[PyOBEX](https://pypi.org/project/PyOBEX/).

[setuptools](https://setuptools.readthedocs.io/en/latest/).

[TOML](https://pypi.org/project/toml/).

[unittest](https://docs.python.org/3/library/unittest.html).
