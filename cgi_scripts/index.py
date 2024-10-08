#!/usr/bin/python3

'''
Created on May 15, 2021

@author: olexandr
'''

import cgi
import cgitb
import copy
import os
import re
import urllib.parse
from enum import Enum

cgitb.enable()


PAT_NAME = re.compile('^(.+)-(.+)$')
BASE = 'data'
TEMPLATE = 'index.html'
ICONS = {'audio': '&#x266B;',  # ♫
         'video': '&#x1F4F9;',  # a video camera
         'dir': '&#x1F4C1;',  # a directory
         'other': '&#x1F4C4;'
         }

# Tags:
_icon = '$icon'
_name = '$name'
_size = '$size'
_link = '$link'
_remove_link = '$remove_link'
_msg = '$msg'
_path = '$path'

_nbr_audios = '$nbr_audios'
_nbr_videos = '$nbr_videos'
_total_size = '$total_size'


class SortBy(Enum):
    '''Sort by these values.'''
    NAME = 'name'
    SIZE = 'size'
    MTIME = 'mtime'


def sort_all(full_paths, sort_by):
    reverse = False

    if sort_by == SortBy.NAME.value:
        def cb_file_sort(x): return os.path.basename(x)
    elif sort_by == SortBy.SIZE.value:
        reverse = True
        def cb_file_sort(x): return os.path.getsize(x)
    else:
        def cb_file_sort(x): return os.path.getmtime(x)

    if sort_by not in [SortBy.NAME.value, SortBy.SIZE]:
        # redefine sort of dirs to have sort by int
        def cb_dir_sort(x): return ord(os.path.basename(x)[0]) - pow(2, 16)
    else:
        def cb_dir_sort(x):
            "prepend '.' to get directories on top"
            return '.' + os.path.basename(x)

    full_paths.sort(key=lambda x:
                    cb_file_sort(x)
                    if os.path.isfile(x)
                    else cb_dir_sort(x),
                    reverse=reverse)
    return full_paths


def get_data(sort_by=None):
    data = []
    full_paths = []
    summary = {_nbr_audios: 0,
               _nbr_videos: 0,
               _total_size: 0}
    for x in os.listdir(BASE):
        full_paths.append(os.path.join(BASE, x))

    full_paths = sort_all(full_paths, sort_by)

    for full_path in full_paths:
        d = {}
        x = os.path.basename(full_path)
        if os.path.isdir(full_path):
            d[_icon] = ICONS['dir']
            d[_name] = x
            d[_size] = '-'
            d[_link] = '?path=' + urllib.parse.quote_plus(x)
            d[_remove_link] = '$remove_link" class="disabled'
        else:
            ext = os.path.splitext(x)[1]
            if ext == '.mp3':
                d[_icon] = ICONS['audio']
                summary[_nbr_audios] += 1
            elif ext in ['.mkv', '.mp4', '.3gp']:
                d[_icon] = ICONS['video']
                summary[_nbr_videos] += 1
            else:
                d[_icon] = ICONS['other']

            enc_x = urllib.parse.quote(x)
            d[_name] = get_name(x)
            size = round(os.path.getsize(full_path) / 1000000, 1)
            summary[_total_size] += size
            d[_size] = str(size)
            d[_link] = os.path.join(BASE, enc_x)
            d[_remove_link] = f'?path={BASE[5:]}&remove={enc_x}'
        summary[_total_size] = round(summary[_total_size])
        data.append(d)
    return {'data': data, 'summary': summary}


def get_template():
    open_tag = '<!-- begin -->'
    close_tag = '<!-- end -->'
    with open(TEMPLATE, 'r') as f:
        template = f.read()
    bi = template.index(open_tag)
    ei = template.index(close_tag)
    pre = template[:bi]
    temp = template[bi+len(open_tag):ei]
    post = template[ei+len(close_tag):]
    return pre, temp, post


def insert_data(data, temp):
    all_temps = ""
    for d in data:
        t = copy.deepcopy(temp)
        for k, v in d.items():
            t = t.replace(k, v)
        all_temps += t
    return all_temps


def insert_summary(summary, temp):
    for k, v in summary.items():
        temp = temp.replace(k, str(v))
    return temp


def remove_file(fl):
    full_path = os.path.join(BASE, fl)
    if os.path.exists(full_path) and os.path.isfile(full_path):
        os.remove(full_path)
        msg = f'{fl} removed!'
    else:
        msg = f'{fl} not found!'
    return msg


def get_name(name):
    m = PAT_NAME.match(name)
    if m:
        return m.group(1)
    else:
        return name

# =======================================


msg = ''

form = cgi.FieldStorage()
path = None

if 'path' in form:
    path = form['path'].value
    BASE = os.path.join(BASE, urllib.parse.unquote_plus(path))

if 'remove' in form:
    msg = remove_file(form['remove'].value)
    print('Status: 302 Found')
    print('Location: {}'.format('/' if path is None else '/?path=' + path))

print('Content-Type: text/html')
print()

data = get_data(form.getvalue('sort', None))
pre, temp, post = get_template()
pre = pre.replace(_msg, msg)
pre = pre.replace(_path, path if path else '.')
temp = insert_data(data['data'], temp)
post = insert_summary(data['summary'], post)
post = post.replace(_path, path if path else '.')

print(pre)
print(temp)
print(post)
