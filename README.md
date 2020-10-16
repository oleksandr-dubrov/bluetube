BLUETUBE
========


Bluetube is a Python script that downloads videos from Youtube by URLs get from RSS, converts them and sends to a bluetooth device.


1 Motivation.
-------------
1.1. I want to have audio and video files from subscribed by RSS Youtube lists and channels on my smartphone. So, the script should convert the files to an appropriate video format or, if it's a talk channel, extract audio.

1.2. I want to download only the files I choose in the list of updates of Youtube lists and channels.

1.3. I don't want to be always logged in Youtube to avoid surveillance and "informational bubble".
That is why I use RSS feed that can get updates on Youtube playlists anonymously.

1.4. I don't want to watch videos on Youtube to save my time. It is always a temptation to keep watching other recommended videos over and over.


2 Preconditions.
----------------
In order to use the script, you must have the next installed.

GNU packages:
+   Python 3
+   libbluetooth-dev - a bluetooth Python package.
+   [youtube-dl](https://rg3.github.io/youtube-dl/) - a downloader.
+   ffmpeg - for converting files into a desirable format.

Python packages:
+   _feedparser_
+   _PyOBEX_
+   _PyBluez_

Before using this script the user should pair the bluetooth device with the PC.
If the bluetooth device is not accessible, the script can download (and convert) files only.


3 Installing.
--------------

### 3.1 Install to a dictionary
In order to install *bluetube* to a specified directory you can run the next command:

    ./install *a_directory_to_install_in*

If *bluetube* is present in the specified directory then the files will be overwritten.

### 3.2 Install to a package manager - PIP.
You can run

    python setup.py install

to install the script to your environment.
After the script is installed, you can run

    python setup.py clean

to clean the repository from *setuptools* data.


4 Configurations.
-----------------
The configuration is kept in the INI file ***bluetooth.cfg*** in the script's directory.
The content of the file below:

	[bluetooth]
	; enter your device ID in the line below
	deviceID=YOUR_RECEIVER_DEVICE_ID
	;
	[download]
	; define video format to be download based on youtube-dl's format selection
	; note: make sure the codec for this format is available in the system
	; working examples:
	;    mp4[width<=640]+worstaudio
	video_format=FORMAT_IS_OPTIONAL
	;
	[video]
	; configure audio and video codecs like in the command line below
	; working examples:
	;    codecs_options=-vcodec h263 -acodec aac -s 352x288
	codecs_options=OPTIONS
	;
	; working examples:
	;    output_format=3gp
	output_format=FORMAT_IS_REQUIRED

If *bluetooth.cfg* is not found, the script prints the template of the configuration file. Edit this template and save to *bluetube.cfg* in the script's directory. Likely, it happens when the script is run for the first time.

You can get your device ID by running the next commands in the Python shell:

	import bluetooth
	[x['host'] for x in bluetooth.find_service() if x['name'] == 'OBEX Object Push'][0]

In order to set the download video format you can check the [FORMAT SELECTION](https://github.com/ytdl-org/youtube-dl/blob/master/README.md#format-selection) section on the *youtube-dl* website.

To configure codecs options please consult [ffmpeg options](https://ffmpeg.org/ffmpeg.html#Options).

5 Run.
------
In order to run *bluetube* you can start the command:

    ./bluetube

Alternatively, you can start the Python script directly from the bluetube directory:

    python bluetube.py


6 Command user interface.
-------------------------
The command user interface is a composition of options:

    usage: bluetube [-h] [--add ADD] [-t {a,v}] [--list] [--remove REMOVE REMOVE]
                    [--send] [--show_all] [--yes] [--no_noise] [--verbose]
                    [--version]

    The script downloads youtube video as video or audio and sends to a bluetooth
    client device.

    optional arguments:
      -h, --help            show this help message and exit
      --add ADD, -a ADD     add a URL to youtube playlist
      -t {a,v}              a type of a file you want to get (for --add)
      --list, -l            list all playlists
      --remove REMOVE REMOVE, -r REMOVE REMOVE
                            remove a playlist by names of the author and the
                            playlist
      --send, -s            send already downloaded files
      --show_all            show all available feed items despite last update time
      --yes, -y             answer positive to all questions
      --no_noise            don't beep when feeds updated
      --verbose, -v         print more information
      --version             show program's version number and exit


If no option specified the script shows feeds to choose, downloads and sends
via bluetooth.


7 Development.
-------------

This section contains information about the script internals.

### 7.1 How to get the feed.

#### 7.1.1 Get RSS feed from the list.
Let's look at the URL below:

`https://www.youtube.com/watch?v=TcA4hhX81cg&list=PLqWhsEuaxvZt3bwQpJfecWH3g0xDyvJs_.`

The list ID that follows `&list=` is `PLqWhsEuaxvZt3bwQpJfecWH3g0xDyvJs_`.
This ID should be placed in `https://www.youtube.com/feeds/videos.xml?playlist_id=YOURPLAYLISTIDHERE` instead of `YOURPLAYLISTIDHERE`.

#### 7.1.2 Get RSS feed from the channel.
Replace CHANNELID in the link below with a Youtube channel ID. The channel ID can be found in the address bar of your browser

`https://www.youtube.com/feeds/videos.xml?channel_id=CHANNELID`

**Note.** Sometimes Youtube changes its rules and the URL patterns might become not valid. In this case, the script must be fixed.

### 7.2 Commands.
#### 7.2.1 *youtube-dl* downloads videos from youtube.
The tool receives the next options for any requested output format:

+   *--ignore-config* - not read configuration files.
+   *--ignore-errors* - continue on download errors, for example to skip unavailable videos in a playlist
+   *--mark-watched* - make the author know you watch his/her videos.
+   *--dateafter DATE* - download only videos uploaded on or after this date (i.e. inclusive); the format of the date is *%Y%m%d* e.g 19700101.

If video requested:

+    *--format FORMAT* - video format code

If audio is requested:

+    *--extract-audio* - convert video files to audio-only files.
+    *--audio-format FORMAT* - specify audio format.
+    *--audio-quality QUALITY* - specify ffmpeg/avconv audio quality, 0 (better) or 9 (worse).

**FYI**. In order to get a list of formats available for downloading URL use *-F*.
For the time being, the most appropriate format is *'mp4[width<=640]+worstaudio'* - mp4 where the width is less or equals 640 and with the worst audio. In case there is no mp4 video with any audio track, then the audio is downloaded separately and merged into a *mkv* container.

#### 7.2.2 *ffmpeg* converts video files.
The tool is used to convert video into *3gp*. Youtube used to have *3gp* version, but now it doesn't.
The tool receives the next options:

+   *-y* -  overwrite output files.
+   *-hide_banner* - hide the banner.
+   *-i* - an input file.

You can configure audio and video codecs in **bluetube.cfg**.
Recommended *ffmpeg* options:
>	codecs_options=-vcodec libx264 -acodec aac -s 320x280
>	output_format=3gp

or

>	codecs_options=-vcodec h263 -acodec aac -s 352x288
>	output_format=3gp


### 7.3 Data structure.
The data are stored in *shelve* DB in the script's directory of the script.
The structure is represented in JSON.
Underlining DB doesn't support unicode keys, so all keys must be strings.

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


### 7.4 Bluetooth.
------------------
The script extends and uses PyOBEX (and PyBluez) to send files via bluetooth.
A few experiments showed that the most appropriate socket timeout is 120 seconds.
Unlike the base implementation, the extended version of the method reads the data from the file stream rather than reading all file in memory before sending.


### 7.5 Links.
[Feed parser](https://pythonhosted.org/feedparser/introduction.html).

[YouTube-dl](https://rg3.github.io/youtube-dl/).

[ffmpeg](https://ffmpeg.org/).

[Markdown](https://daringfireball.net/projects/markdown/).

[INI](https://en.wikipedia.org/wiki/INI_file).

[PyOBEX](https://bitbucket.org/dboddie/pyobex/src/default/).

[setuptools](https://setuptools.readthedocs.io/en/latest/).

[TOML](https://pypi.org/project/toml/).
