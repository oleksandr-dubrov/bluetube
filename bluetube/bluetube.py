#!/usr/bin/env python
# -*- coding: utf-8 -*-


__version__ = '1.2'
__author__ = 'Olexandr Dubrov <olexandr.dubrov@gmail.com>'
__license__ = '''
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


import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
import webbrowser
from ConfigParser import SafeConfigParser

from bcolors import Bcolors
from feeds import Feeds

try:
	from bluetoothclient import BluetoothClient
	import feedparser
except ImportError:
	print('''Dependencies is not satisfied.
	Run pip install -r dependencies.txt''')
	sys.exit(-1)


class CommandExecutor(object):
	'''This class run the commands in the shell'''

	def __init__(self, verbose):
		self._verbose = verbose
		
	def call(self, args, cwd=None, suppress_stdout=False, suppress_stderr=False):
		if cwd == None:
			cwd = os.getcwd()
		call_env = os.environ
		return_code = 0
		stdout, stderr = None, None
		try:
			if self._verbose:
				print(u'RUN: {}'.format([a.decode('utf-8') for a in args]))
			if suppress_stdout:
				stdout = open(os.devnull, 'wb')
			if suppress_stderr:
				stderr = open(os.devnull, 'wb')
			return_code = subprocess.call(args,
										env=call_env,
										stdout=stdout,
										stderr=stderr,
										cwd=cwd)
		except OSError as e:
			return_code = e.errno
			print(e.strerror)
		if self._verbose:
			print('Return code: {}'.format(return_code))
		return return_code

	def does_command_exist(self, name, dashes=2):
		'''call a command with the given name and expects that it has option --version'''
		return not self.call((name,
							'{}version'.format(dashes * '-')),
							suppress_stdout=True);


class Bluetube(object):
	''' The main class of the script. '''

	CONFIG_FILE_NAME = 'bluetube.cfg'
	CUR_DIR = os.path.dirname(os.path.realpath(__file__))
	CONFIG_FILES = [os.path.join(CUR_DIR, CONFIG_FILE_NAME),
					os.path.expanduser(os.path.join('~',
													'.bluetube',
													CONFIG_FILE_NAME))]
	CONFIG_TEMPLATE = os.path.join(CUR_DIR, 'bt_config.template')
	INDENTATION = 10
	DOWNLOADER = 'youtube-dl'
	CONVERTER = 'ffmpeg'


	def add_playlist(self, url, out_format):
		''' add a new playlists to RSS feeds '''
		out_format = self._get_type(out_format)
		feed_url = self._get_feed_url(url)
		if out_format and feed_url:
			f = feedparser.parse(feed_url)
			title = f.feed.title
			author = f.feed.author
			feeds = Feeds(self._get_bt_dir())
			if feeds.has_playlist(author, title):
				Bcolors.error(u'The playlist {} by {} has already been existed'
							.format(title, author))
			else:
				feeds.add_playlist(author, title, feed_url, out_format)
				Bcolors.intense(u'{} by {} added successfully.'.format(title,
																	author))
			return True
		return False

	def list_playlists(self):
		''' list all playlists in RSS feeds '''
		feeds = Feeds(self._get_bt_dir(), 'r')
		all_playlists = feeds.get_all_playlists()
		if len(all_playlists):
			for a in all_playlists:
				print(a['author'])
				for c in a['playlists']:
					o = u'{}{}'.format(u' ' * Bluetube.INDENTATION, c['title'])
					o = u'{} ({})'.format(o, time.strftime('%Y-%m-%d %H:%M:%S',
														time.localtime(c['last_update'])))
					print(o)
		else:
			Bcolors.warn('The list of playlist is empty. Use --add to add a playlist.')

	def remove_playlist(self, author, title):
		''' remove a playlist be given title '''
		feeds = Feeds(self._get_bt_dir())
		if feeds.has_playlist(author, title):
			feeds.remove_playlist(author, title)
		else:
			Bcolors.error(u'{} by {} not found'.format(title, author))

	def run(self, verbose=False, show_all=False):
		''' The main method. It does everything.'''
		self.configs = self._get_configs()
		self.executor = CommandExecutor(verbose)

		if self._check_config_file() and self._check_downloader():
				return self._run(verbose, show_all)
		return False

	def send(self):
		'''send files from the bluetube download directory
		to a bluetooth device'''
		self.configs = self._get_configs()
		download_dir = self._fetch_download_dir()
		if os.listdir(download_dir):
			sender = self._get_sender(download_dir)
			if sender.found:
				self._send(sender, download_dir)
			else:
				Bcolors.warn('Your bluetooth device is not accessible.')
		else:
			Bcolors.warn('Nothing to send.')
		self._return_download_dir(download_dir)

	def _run(self, verbose, show_all):
		feeds = Feeds(self._get_bt_dir())
		download_dir = self._fetch_download_dir()
		playlists = self._get_playlists_with_urls(feeds, show_all)
		if len(playlists):
			if self._download_and_send_playlist(feeds,
												playlists,
												download_dir,
												verbose):
				self._return_download_dir(download_dir)
		else:
			Bcolors.warn('No playlists in the list. Use --add to add a playlist.')
			return False
		return True

	def _get_sender(self, download_dir):
		'''create and return a sender'''
		sender = BluetoothClient(self.configs.get('bluetooth', 'deviceID'),
								download_dir)
		if not sender.found:
			Bcolors.warn('Your bluetooth device is not accessible.')
			Bcolors.warn('The script will download files to {} directory.'
						.format(download_dir))
			raw_input('Press Enter to continue, Ctrl+c to interrupt.')

		return sender

	def _download_and_send_playlist(self, feeds, playlists, download_dir, verbose):
		sender = self._get_sender(download_dir)
		is_converter = self._check_vidoe_converter()
		for ch in playlists:
			if ch['urls'] == None:
				continue
			if len(ch['urls']):
				if self._download(ch, download_dir):
					if not self._convert_if_needed(ch['playlist']['out_format'],
													ch['playlist']['title'],
													is_converter,
													download_dir):
						continue
					feeds.update_last_update(ch)
				else:
					Bcolors.error(u'Failed to download this playlist: \n\t{}'
								.format(ch['playlist']['title']))
				if sender.found:
					self._send(sender, download_dir)
			else:
				feeds.update_last_update(ch)
				if verbose:
					Bcolors.warn(u'Nothing to download from {}.'
								.format(ch['playlist']['title']))
		return True

	def _convert_if_needed(self, out_format, title, is_converter, download_dir):
		ret = True
		if is_converter:
			if out_format == 'video' and not self._convert_video(download_dir):
				Bcolors.error(u'Failed to convert video for {}'.format(title))
				Bcolors.warn(u'The files is here {}'.format(download_dir))
				ret = False
		else:
			Bcolors.warn(u'Video from "{}" will be sent without converting'
						.format(title.decode('utf-8')))
		return ret

	def _check_vidoe_converter(self):
		if self.executor.does_command_exist(Bluetube.CONVERTER, dashes=1):
			return True
		else:
			Bcolors.warn(u'ERROR: The tool for converting video "{}" is not found in PATH'
						.format(Bluetube.CONVERTER))
			Bcolors.warn(u'Pease install the converter.')
			raw_input('Press Enter to continue, Ctrl+c to interrupt.')
			return False

	def _convert_video(self, download_dir):
		options = ('-y',  # overwrite output files
					'-hide_banner',)
		codecs_options = self.configs.get('video', 'codecs_options')
		codecs_options = tuple(codecs_options.split())
		output_format = self.configs.get('video', 'output_format')
		files = os.listdir(download_dir)
		for f in [x for x in files if os.path.splitext(x)[-1] in ['.mp4', '.mkv']]:
			args = ('ffmpeg',) + \
					('-i', f) + \
					options + \
					codecs_options + \
					(os.path.splitext(f)[0] + '.' + output_format,)
			if not 1 == self.executor.call(args, cwd=download_dir):
				os.remove(os.path.join(download_dir, f))
			else:
				Bcolors.error('Failed to convert the file {}.'
							.format(os.path.basename(f).decode('utf-8')))
				Bcolors.warn('Check {} after the script is done.'
							.format(tempfile.gettempdir()))
		return True

	def _get_configs(self):
		parser = SafeConfigParser()
		return None if len(parser.read(Bluetube.CONFIG_FILES)) == 0 else parser

	def _check_config_file(self):
		ok = True
		if self.configs == None:
			Bcolors.error('Configuration file is not found.')
			ok = False

		if ok and not (self.configs.has_section('bluetooth')
			and self.configs.has_section('video')
			and self.configs.has_option('bluetooth', 'deviceID')
			and self.configs.has_option('video', 'output_format')):
			Bcolors.error('The configuration file has no needed options.')
			ok = False

		if not ok:
			with open(Bluetube.CONFIG_TEMPLATE, 'r') as f:
				Bcolors.error(u'You must create {} or {} with the content below manually:\n{}'
							.format(Bluetube.CONFIG_FILES[0],
									Bluetube.CONFIG_FILES[1],
									f.read()))
			return False

		if not self.configs.has_option('video', 'codecs_options'):
			Bcolors.error('ffmpeg codecs are not configured in {}'
						.format(Bluetube.CONFIG_FILE))

		return ok

	def _check_downloader(self):
		if self.executor.does_command_exist(Bluetube.DOWNLOADER):
			return True
		else:
			Bcolors.error(u'ERROR: The tool for downloading from youtube "{}" is not found in PATH'
						.format(Bluetube.DOWNLOADER))
			return False

	def _get_type(self, out_format):
		if out_format in ['a', 'audio']:
			return 'audio'
		elif out_format in ['v', 'video']:
			return 'video'
		else:
			Bcolors.error('ERROR: unexpected output type. Should be v (or video) or a (audio) separated by SPACE')
		return None

	def _get_feed_url(self, url):
		p1 = re.compile('^https://www\.youtube\.com/watch\?v=.+&list=(.+)$')
		p2 = re.compile('^https://www\.youtube\.com/playlist\?list=(.+)$')
		m = p1.match(url);
		if not m:
			m = p2.match(url)
		if m:
			return 'https://www.youtube.com/feeds/videos.xml?playlist_id={}'.format(m.group(1))
		else:
			p = re.compile('^https://www\.youtube\.com/channel/(.+)$')
			m = p.match(url);
			if m:
				return 'https://www.youtube.com/feeds/videos.xml?channel_id={}'.format(m.group(1))
			Bcolors.error(u'ERROR: misformatted URL of a youtube list provided.\n\
	Should be https://www.youtube.com/watch?v=XXX&list=XXX for a playlist,\n\
	or https://www.youtube.com/feeds/videos.xml?playlist_id=XXX for a channel.')
			return None

	def _ask(self, link, summary=None):
		'''ask if perform something'''
		d = [u'd', u'D', u'В', u'в', u'Y', u'y', u'Н', u'н', u'yes', u'YES'] # d for download
		r = [u'r', u'R', u'к', u'К', u'n', u'N', u'т', u'Т', u'no', u'NO'] # r for reject
		s = [u's', u'S', u'і', u'І']
		open_browser = [u'b', u'B', u'и', u'И']
		question = '{b}d{e}ownload | {b}r{e}eject | open in {b}b{e}rowser'.format(b=Bcolors.HEADER,
																				e=Bcolors.ENDC)
		if summary:
			question = question + ' | {b}s{e}ummary'.format(b=Bcolors.HEADER,
															e=Bcolors.ENDC)

		while True:
			i = raw_input('{}\n'.format(question))
			if i in d:
				return True
			elif i in r:
				return False
			elif i in s:
				print(u'Summary:\n{}'.format(summary))
			elif i in open_browser:
				print('Opening the link in the default browser...')
				webbrowser.open(link, new=2)
			else:
				Bcolors.error(u'{}{} to download, {} for reject, {} to get a summary (if any), {} to open in a browser.{}'
						.format(Bcolors.FAIL, d[0], r[0], s[0], open_browser[0], Bcolors.ENDC))

	def _get_playlists_with_urls(self, feeds, show_all):
		'''get URLs from the RSS that the user will selected for every playlist'''
		all_playlists = feeds.get_all_playlists()
		playlists = []
		for chs in all_playlists:
			print(chs['author'])
			for ch in chs['playlists']:
				processed_pl = self._process_playlist(chs['author'], ch, show_all)
				playlists.append(processed_pl)
		return playlists

	def _process_playlist(self, author, ch, show_all):
		urls = []
		is_need_update = False
		new_last_update = last_update = ch['last_update']
		print(u'{ind}{tit}'.format(ind=u' ' * Bluetube.INDENTATION, tit=ch['title']))
		f = feedparser.parse(ch['url'])
		for e in f.entries:
			pub = e['published_parsed']
			params = {'ind': 2 * Bluetube.INDENTATION * u' ',
					'tit': e['title'],
					'h': pub.tm_hour,
					'min': pub.tm_min,
					'd': pub.tm_mday,
					'mon': pub.tm_mon}

			e_update = time.mktime(e['published_parsed'])
			if last_update < e_update or show_all:
				if not is_need_update:
					is_need_update = True
				print(u'{ind}{tit} ({h}:{min:0>2} {d}.{mon:0>2})'.format(**params))

				if self._ask(e['link'], summary=e['summary']):
					urls.append(e['link'])
				if new_last_update < e_update:
					new_last_update = e_update

		return {'author': author,
				'playlist': ch,
				'urls': urls if is_need_update else None,
				'published_parsed': new_last_update}

	def _download(self, playlist, download_dir):
		options = ('--ignore-config',
					'--ignore-errors',
					'--mark-watched',)
		out_format = playlist['playlist']['out_format']
		if out_format == 'audio':
			spec_options = ('--extract-audio',
							'--audio-format=mp3',
							'--audio-quality=9',  # 9 means worse
							'--embed-thumbnail',
							)
		elif out_format == 'video':
			if self.configs.has_section('download'):
				video_format = self.configs.get('download', 'video_format')
			else:
				video_format = 'mp4[width<=640]+worstaudio'
			spec_options = ('--format', video_format,)
		else:
			assert 0, 'unexpected output format; should be either "v" or "a"'
		args = (Bluetube.DOWNLOADER,) + options + spec_options + tuple(playlist['urls'])
		return not self.executor.call(args, cwd=download_dir)

	def _send(self, sender, download_dir):
		'''Send all files in the given directory'''
		sent = []
		files = os.listdir(download_dir)
		for fl in files:
			if fl.endswith('.part') or fl.endswith('.ytdl'):
				# ignore but put them to send:
				#        partially downloaded files
				#        youtube-dl service files
				sent.append(os.path.join(fl))
		if sender.found and sender.connect():
				sent += sender.send(files)
				sender.disconnect()
		for f in sent:
			os.remove(f)

	def _fetch_download_dir(self):
		bluetube_dir = os.path.join(tempfile.gettempdir(), 'bluetube')
		if not os.path.isdir(bluetube_dir):
			os.mkdir(bluetube_dir)
		return bluetube_dir

	def _return_download_dir(self, bluetube_dir):
		if os.path.isdir(bluetube_dir):
			try:
				os.rmdir(bluetube_dir)
			except OSError:
				Bcolors.warn('The download directory {} is not empty. Cannot delete it.'
							.format(bluetube_dir))
				Bcolors.warn('\n  '.join(os.listdir(bluetube_dir)))

	def _get_bt_dir(self):
		return [Bluetube.CUR_DIR, os.path.expanduser(os.path.join('~', '.bluetube')), ]

# ============================================================================ #


def main():
	description='The script downloads youtube video as video or audio and sends to a bluetooth client device.'
	epilog = 'If no option specified the script shows feeds to choose, downloads and sends via bluetooth client.'
	parser = argparse.ArgumentParser(prog='bluetube', description=description)
	parser.epilog = epilog
	me_group = parser.add_mutually_exclusive_group()

	me_group.add_argument('--add', '-a',
						help='add a URL to youtube playlist', type=unicode)
	parser.add_argument('-t',
					dest='type',
					help='a type of a file you want to get (for --add)',
					choices=['a', 'v'],
					default='v')
	me_group.add_argument('--list', '-l',
						help='list all playlists', action='store_true')
	me_group.add_argument('--remove', '-r',
						nargs=2, 
						help='remove a playlist by names of the author and the playlist',
						type=lambda s: unicode(s, 'utf8'))

	me_group.add_argument('--send', '-s',
						help='send already downloaded files',
						action='store_true')

	parser.add_argument('--show_all',
					action='store_true',
					help='show all available feed items despite last update time')
	parser.add_argument('--verbose', '-v',
					action='store_true',
					help='print more information')
	parser.add_argument('--version', action='version',
					version='%(prog)s {}'.format(__version__))

	bluetube = Bluetube()
	args = parser.parse_args()
	if args.add:
		if not bluetube.add_playlist(args.add, args.type):
			sys.exit(-1)
	elif args.list:
		bluetube.list_playlists()
	elif args.remove:
		bluetube.remove_playlist(args.remove[0].strip(), args.remove[1].strip())
	elif args.send:
		bluetube.send()
	else:
		bluetube.run(args.verbose, args.show_all)
	print('Done')

if __name__ == '__main__':
	main()
