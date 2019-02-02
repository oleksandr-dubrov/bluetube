BLUETUBE
========


Bluetube is a script that downloads videos from Youtube by URLs get from RSS and sends them to a bluetooth device.
The script downloads media to `~/Downloads/bluetube.tmp`. If there is no such path it will be created. After success sending the `bluetube` directory 
is removed. If some file failed to be sent then the file is not removed and stays in the 
directory.


1 Motivation.
-------------
1.1. I don't want to be always logged in Youtube to avoid surveillance and "informational bubble".
That is why I use RSS feed that can get updates on Youtube channels anonymously.

1.2. I don't want to watch videos on Youtube site to save my time. It is always temptation that I keep watching other recommended videos over and over.
So, the script will download selected videos and if it is needed converts it to audio.

1.3. The script will send the video or audio files to my bluetooth device. In my case it is Nokia N73 under Symbian S60 v9.1.
If the transfer is done successfully the the script should remove the files.


2 Preconditions.
----------------
In order to use the script, you must have the next installed.

Python packages:
+   _feedparser_
+   _PyOBEX_
+   _PyBluez_

GNU packages:
+   [_youtube-dl_] (https://rg3.github.io/youtube-dl/).
+   ffmpeg - for converting files in desirable  format.

*youtube-dl* and *a bluetooth-send tool* can be configured in the INI configuration file in the root directory of the script.

*bluetube.cfg* must be provided together with the script.


3 Installing.
--------------
In order to install *bluetube* to a specified directory you can run the next command:
>./install *directory_to_install_in*


4 Configurations.
------------------
The configuration is kept in the INI file ***bluetooth.cfg*** in the root directory.
The content of the file please see below:

    ; Configurations for bluetube.
    [bluetube]
    downloader=youtube-dl
    ; enter your device ID in the line below
    deviceID=YOUR_RECEIVER_DEVICE_ID

If *bluetooth.cfg* was not found, then please create it manually.


5 Run.
------
In order to run the script you can start the *bash* script:

    ./bluetube

Alternatively, you can start the Python script directly:

    python bluetube.py


6 Command user interface.
-------------------------
The command user interface is a composition of options:

	usage: bluetube.py [-h] [--add ADD] [-t {a,v}] [--list]
                   [--remove REMOVE REMOVE] [--version]
	
	optional arguments:
	  -h, --help            show this help message and exit
	  --add ADD, -a ADD     add a URL to youtube channel
	  -t {a,v}              a type of a file you want to get (for --add)
	  --list, -l            list all channels
	  --remove REMOVE REMOVE, -r REMOVE REMOVE
                            remove a channel by names of the author and the
                            channel
	  --version             show program's version number and exit

If no option specified the script shows feeds to choose, downloads and sends
via bluetooth.


7 Tests.
--------
There are some unit tests provided to verify that the script is not broken.
I don't have a goal to rich good code coverage, so passed tests don't guarantee the 
correct work of the script. In order to get more information reed the test's output.
Run test from *tests* directory:

    python test_bluetube.py

The tests are base on *unittests* and *mock*. Don't forget to install *mock* before 
run the tests.

8 Development.
-------------

This section contains information of the script internals.

8.1 How to get the feed.
------------------------
Let's look at the URL below:

`https://www.youtube.com/watch?v=TcA4hhX81cg&list=PLqWhsEuaxvZt3bwQpJfecWH3g0xDyvJs_.`

The list ID that follows `&list=` is `PLqWhsEuaxvZt3bwQpJfecWH3g0xDyvJs_`.
This ID should be placed in `https://www.youtube.com/feeds/videos.xml?playlist_id=YOURPLAYLISTIDHERE` instead of `YOURPLAYLISTIDHERE`.

**Note.** Sometimes Youtube changes its rules and the URL might become not valid. In this case, the script must be fixed.

8.2 Commands.
-------------
*youtube-dl* downloads vidoes from youtube.
The tool receives the next options for any requested output format:

+   *--ignore-config* - not read configuration files.
+   *--mark-watched* - videos watched (YouTube only). Make the author know you watch his/her videos.
+   *--dateafter DATE* - download only videos uploaded on or after this date (i.e. inclusive); the format of the date is *%Y%m%d* e.g 19700101.

If video requested:

+    *--format FORMAT* - video format code, see the "FORMAT SELECTION" for all the info

If audio is requested:

+    *--extract-audio* - convert video files to audio-only files.
+    *--audio-format FORMAT* - specify audio format.
+    *--audio-quality QUALITY* - specify ffmpeg/avconv audio quality, 0 (better) or 9 (worse).


8.3 Data structure.
-------------------
The data are stored in *shelve* DB in the root directory.
The structure is represented in JSON.
Underlining DB doesn't support unicode, so all keys must be strings.

	{
        feeds: [
            {
                "author": "author1":
                "channels: [
    			     {
    				    "title": "the name of an entity",
    				    "url": "url of the entity",
    				    "last_update": 1548951984,
                        "out_format": "a" or "v" 
    			     },
    			     {
    			         ...
    			     }
		          ],
            },
            {
                "author": "author1":
		         "channels: [
			      ...
		          ],
		      ...
            }
        ]
	}


8.4 Error handling.
-------------------
If a method fails it returns -1. Otherwise - 0.


8.5 Links.
----------

[Feed parser](https://pythonhosted.org/feedparser/introduction.html).

[YouTube-dl](https://rg3.github.io/youtube-dl/).

[Markdown](https://daringfireball.net/projects/markdown/).

[INI](https://en.wikipedia.org/wiki/INI_file)


9 Bluetooth.
------------
The script extends and uses PyOBEX (and PyBluez) to send files via bluetooth.
For more information see [PyOBEX](https://bitbucket.org/dboddie/pyobex/src/default/)


10 Troubleshooting
------------------
On Windows if you see
    UnicodeEncodeError: 'charmap' codec can't encode characters in position 
it means that CMD cannot display a symbol. In this case try to use *install win-unicode-console*.
First, it should be installed:
    pip install install win-unicode-console
Once the package is installed, you should run the script like this:
    python -mrun bluetube.py


TODO
----
1. Check if *ffmpeg* (or avconv and ffprobe or avprobe) is in PATH. If not, inform the user that no conversion is available.
  Recommend the user to install *ffmpeg*.
2. Change mode for files
> bluetube.py and bluetube -> read-only
> install.sh -> read-only and executable
3. Configurations should keep a bt device name rather than id.
