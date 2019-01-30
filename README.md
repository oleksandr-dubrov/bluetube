BLUETUBE
========

Bluetube is a script that downloads videos from youtube by URLs get from RSS and send them to a bluetooth device.

1 Motivation.
-------------
1.1. I don't want to be always logged in youtube to avoid surveillance and "informational bubble".
That is why I use RSS feed that can get updates on youtube channels anonymously.

1.2. I don't want to watch videos on youtube site to save my time. It is always temptation that I keep watching other recommended videos over and over.
So, the script will download selected videos and if it is needed converts it to audio.

1.3. The script will send the video or audio files to my bluetooth device. In my case it is Nokia N73 under Symbian S60 v9.1.
If the transfer is done successfully the the script should removed the files.

2 How to get the feed.
----------------------
Let's look at the URL below:

`https://www.youtube.com/watch?v=TcA4hhX81cg&list=PLqWhsEuaxvZt3bwQpJfecWH3g0xDyvJs_.`

The list ID that follows `&list=` is `PLqWhsEuaxvZt3bwQpJfecWH3g0xDyvJs_`.
This ID should be placed in `https://www.youtube.com/feeds/videos.xml?playlist_id=YOURPLAYLISTIDHERE` instead of `YOURPLAYLISTIDHERE`.

**Note.** Sometimes youtube changes its rules and the URL might become not valid. In this case, the script must be fixed.

3 Command user interface.
---------------------
The command user interface is a composition of options:

		usage: bluetube.py [-h] [-add ADD | -t {a,v}] [-list]
	                   [-remove REMOVE | -au AUTHOR]
		optional arguments:
		  -h, --help            show this help message and exit
		  -add ADD, -a ADD      add a URL to youtube channel
		  -t {a,v}              a type of a file you want to get - (v)ideo (default)
	                        or (a)udio
		  -list, -l             list all channels
		  -remove REMOVE, -r REMOVE
	                        remove the channel by its name
		  -au AUTHOR            an author (required when -remove)
		
		   no option            run the main flow - show feeds, download, send via bluetooth.

4 Preconditions.
-----------------

**Note.** In order to use the script, you must have the next installed:

+	_feedparser_ - the python package
+	_youtube-dl_ - the GNU package (https://rg3.github.io/youtube-dl/)
+	_bluetooth-send_ or other tool that sends files via bluetooth and accept the target divice ID and file names.

*youtube-dl* and *a bluetooth-send tool* can be configured in the INI configuration file in the root directory of the script.

*bluetube.cfg* must be provided together with the script.

5 Configurations.
------------------
The configuration is kept in the INI file *bluetooth.cfg* in the root directory.
The default content of the file please see below:
> [bluetube]
> ; a comment
> downloader=youtube-dl
> sender=bluetooth-send
> diviceID=YOUR_RECEIVER_DEVICE_ID

If *bluetooth.cfg* was not found, then please create it manually.

6 Commands.
------------
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

The script downloads media to `~/Downloads/bluetube`. If there is no such path it will be created. After success sending the `bluetube` is removed.

7 Data structure.
------------------
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
    				    "last_update": "2019.01.01",
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

8 Tests.
--------
There are some unit tests provided to verify that the script is not broken.
I don't have a goal to rich good code coverage, so passed tests don't guarantee the 
correct work of the script. In order to get more information reed the test's output.
Run test from *tests* directory:

    python test_bluetube.py

The tests are base on *unittests* and *mock*. Don't forget to install *mock* before 
run the tests.

9 Error handling.
-----------------
If a command fails it returns -1 to OS. Otherwise - 0.


**See also.**

[Feed parser](https://pythonhosted.org/feedparser/introduction.html).

[YouTube-dl](https://rg3.github.io/youtube-dl/).

[Markdown](https://daringfireball.net/projects/markdown/).


0 Troubleshooting
-----------------
On Windows if you see
>   UnicodeEncodeError: 'charmap' codec can't encode characters in position 
it means that CMD cannot display a symbol. In this case try to use *install win-unicode-console*.
First, it should be installed:
> pip install install win-unicode-console
Once the package is installed, you should run the script like this:
> python -mrun bluetube.py

0 Glossary
--------
0.1. Bluetooth.
SDP - Service Discovery Protocol.

TODO
----
1. Check if *ffmpeg* (or avconv and ffprobe or avprobe) is in PATH. If not, inform the user that no conversion is available.
  Recommend the user to install *ffmpeg*.
2. Use PyOBEX instead of external tool. Try to improve the library. See [PyOBEX](https://bitbucket.org/dboddie/pyobex/src/abcfb31c3609c7408e47c10ae30d46438e35018f/PyOBEX/client.py?at=default&fileviewer=file-view-default)

