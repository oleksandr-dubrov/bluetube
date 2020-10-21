# This is a test DB.
# It has 2 authors with 1 + 2 = 3 playlists.
# NOTE. It it is changed, *mocked_data.zip*
#     and all asserts related to this should be updated.

# mocked_data.zip has 10 new videos in case THESE last update values.
NEW_LINKS = 10

FAKE_DB = '''
[{"playlists": [
    {"url":
"https://www.youtube.com/feeds/videos.xml?channel_id=UCemEkBcOpHNi1yZ4UjVi9EA",
    "out_format": "video",
    "title": "ТаТоТаке",
    "last_update": 1595950278.0,
    "profiles": ["mobile", "local"]}],
"author": "ТаТоТаке"
},
{"playlists": [
    {"url":
"https://www.youtube.com/feeds/videos.xml?playlist_id=PL9o6bQUWYNvKejzvt2yclyZfJ-461xHB4",
    "out_format": "audio",
    "last_update": 1590085510.0,
    "title": "Право на гідність",
    "profiles": ["mobile"]},
    {"url":
"https://www.youtube.com/feeds/videos.xml?playlist_id=PL9o6bQUWYNvLV7m3tATsU1Fodjy7ZGxXM",
    "out_format": "audio",
    "last_update": 1595014123.0,
    "title": "Чесна політика",
    "profiles": ["mobile"]}],
"author": "24 Канал"}]
''' # noqa E501
