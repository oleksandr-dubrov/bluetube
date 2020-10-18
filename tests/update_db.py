#######
# Reset DB.
# A helper for manual testing.

import os
import json
import shelve


feeds = '''[{"playlists": [
    {"url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCemEkBcOpHNi1yZ4UjVi9EA",
    "out_format": "audio",
    "title": "ТаТоТаке",
    "last_update": 1602288000.0,
    "profiles": ["mobile", "local"]}],
"author": "ТаТоТаке"
},
{"playlists": [
    {"url": "https://www.youtube.com/feeds/videos.xml?playlist_id=PL9o6bQUWYNvKejzvt2yclyZfJ-461xHB4",
    "out_format": "video",
    "last_update": 1602288000.0,
    "title": "Право на гідність",
    "profiles": ["mobile", "local"]},
    {"url": "https://www.youtube.com/feeds/videos.xml?playlist_id=PL9o6bQUWYNvLV7m3tATsU1Fodjy7ZGxXM",
    "out_format": "audio",
    "last_update": 1602288000.0,
    "title": "Чесна політика",
    "profiles": ["mobile", "local"]}],
"author": "24 Канал"}]
'''

fl = os.path.expanduser('~/.bluetube/bluetube.db')

s = shelve.open(fl, flag='r', writeback=False)
s['feeds'] = json.loads(feeds)
s.close()
