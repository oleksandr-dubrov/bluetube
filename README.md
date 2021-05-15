# BLUETUBE


Bluetube is a Python script that downloads videos from Youtube by URLs get from RSS, converts them and sends to a bluetooth device.

Bluetube allows you to do next:
* see updates on subscribed playlists and channels;
* open a video in browser or local media player;
* download a video;
* convert it to a suitable format or extract audio for talk shows.
* send it via bluetooth (to a paired device) or to a local directory.


## 1 Preconditions
In order to use the script, you must have the next installed.

GNU packages:
+   Python 3
+   libbluetooth-dev - a bluetooth Python package.
+   [youtube-dl](https://rg3.github.io/youtube-dl/) - a downloader.
+   ffmpeg - for converting files into a desirable format.

Before using this script the user should pair the bluetooth device with the PC.
If the bluetooth device is not accessible, the script can download (and convert) files only.


## 2 Installing

    pip install bluetube_cli-2.*-py3-none-any.whl

You might need *sudo* privileges.


## 3 Run

To start the script, run

    bluetube

Use *--home* to specify other bluetube's home directory. Default home is *~/.bluetube*.

To get a quick help, run

    bluetube --help

A **profile** is a set of actions the script should perform on a downloaded video e.g. extract audio, convert and send. You can define how to convert and where to send videos in the profiles. To get more information about profiles and configure them, run 

    bluetube --edit_profiles

To track a playlist or a channel, add it by

    bluetube add "https://www.youtube.com/watch?v=XXXXXXXX&list=XXXXXXX"

Use the next options as well:

* *-t* - *a* to get audio, *v* - video (default).
* *-p* - names of *profiles*, if omitted - the "default" profile is used.

Use *list* to see all subscribed playlists, *remove* - to remove a playlist.

The command *edit* allows to:
* change a output type - video or audio;
* change profiles assigned to a playlist;
* reset failed videos (in case Bluetube failed to download a video, it will try to do that next time, this option makes Bluetube give up);
* roll back last update time to download previous videos again.

Run `bluetube edit --help` for details.

## 4 Links.
[Python 3](https://www.python.org).

[libbluetooth-dev](https://packages.debian.org/sid/libbluetooth-dev).

[ffmpeg](https://ffmpeg.org/).
