#!/usr/bin/env python
# -*- coding: utf-8 -*-


__version__ = '1.0'
__author__ = 'OD'
__license__ = '''This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
'''


#########################################################################
# This a script that loads RSS and sends selected feeds to my Nokia N73.#
#########################################################################


import argparse
import os
import re
import shelve
import socket
import subprocess
import sys
import tempfile
import time
import webbrowser
from ConfigParser import SafeConfigParser

try:
	import bluetooth  # @UnresolvedImport
	from PyOBEX.client import Client  # @UnresolvedImport
	from PyOBEX import headers
	from PyOBEX import requests
	from PyOBEX import responses
	import feedparser
except ImportError:
	print('''Dependencies is not satisfied.
	Run pip install -r dependencies.txt''')
	sys.exit(-1)


CUR_DIR = os.path.dirname(os.path.realpath(__file__))


class Bcolors:
	BOLD = '\033[1m'
	HEADER = '\033[95m'
	OKBLUE = '\033[94m'
	OKGREEN = '\033[92m'
	WARNING = '\033[93m'
	FAIL = '\033[91m'
	ENDC = '\033[0m'

	def disable(self):
		Bcolors.BOLD = ''
		Bcolors.HEADER = ''
		Bcolors.OKBLUE = ''
		Bcolors.OKGREEN = ''
		Bcolors.WARNING = ''
		Bcolors.FAIL = ''
		Bcolors.ENDC = ''

	@staticmethod
	def warn(txt):
		print(u'{}{}{}'.format(Bcolors.WARNING, txt, Bcolors.ENDC))

	@staticmethod
	def error(txt):
		print(u'{}{}{}'.format(Bcolors.FAIL, txt, Bcolors.ENDC))

	@staticmethod
	def intense(txt):
		print(u'{}{}{}'.format(Bcolors.BOLD, txt, Bcolors.ENDC))


class CommandExecutor(object):
	'''This class run the commands in the shell'''

	def __init__(self, verbose):
		self._verbose = verbose
		
	def call(self, args, cwd=None, suppress_output=False):
		if cwd == None:
			cwd = os.getcwd()
		call_env = os.environ
		return_code = 0
		stdout = None
		try:
			if self._verbose:
				print('RUN: {}'.format(args))
			if suppress_output:
				stdout = open(os.devnull, 'wb')
			return_code = subprocess.call(args, env=call_env, stdout=stdout, cwd=cwd)
		except OSError as e:
			return_code = e.errno
			print(e.strerror)
		return return_code

	def does_command_exist(self, name):
		'''call a command with the given name and expects that it has option --version'''
		return not self.call((name, '--version'), suppress_output=True);


class Feeds(object):
	'''Manages a RSS feeds in the shelve database'''

	DATABASE_FILE = os.path.join(CUR_DIR, 'bluetube.dat')

	def __init__(self, mode='rw'):
		self.db = None
		if mode == 'r':
			self.db = Feeds._create_ro_connector()
		elif mode == 'rw':
			self.db = Feeds._create_rw_connector()
		else:
			assert 0, 'the access mode should be either "rw" or "r"'

	def __del__(self):
		if self.db:
			try:
				self.db.close()
			except ValueError as e:
				Bcolors.error('Probably your changes were lost. Try again')
				raise e

	@staticmethod
	def _create_rw_connector():
		'''create DB connector in read/write mode'''
		return shelve.open(Feeds.DATABASE_FILE, flag='c', writeback=False)

	@staticmethod
	def _create_ro_connector():
		'''create DB connector in read-only mode'''
		if not os.path.isfile(Feeds.DATABASE_FILE):
			Feeds._create_empty_db()
		return shelve.open(Feeds.DATABASE_FILE, flag='r')

	@staticmethod
	def _create_empty_db():
		db = Feeds._create_rw_connector()
		db['feeds'] = []
		db.sync()

	def get_authors(self):
		if 'feeds' in self.db:
			return [a['author'] for a in self.db['feeds']]
		return []

	def get_playlists(self, author):
		authors = self.get_authors()
		if authors:
			for au in self.db['feeds']:
				if au['author'] == author:
					return [ch['title'] for ch in au['playlists']]
		return []

	def has_playlist(self, author, playlist):
		if playlist in self.get_playlists(author):
			return True
		return False

	def add_playlist(self, author, title, url, out_format):
		feeds = self.get_all_playlists()

		# create a playlist 
		playlist = {"title": title,
					"url": url,
					"last_update" : 0,
					"out_format": out_format}

		# insert the playlist into the author
		if author not in [f['author'] for f in feeds]:
			feeds.append({'author': author, 'playlists': []})
		for f in feeds:
			if f['author'] == author:
				f['playlists'].append(playlist)
				break

		self.write_to_db(feeds)

	def get_all_playlists(self):
		return self.db.get('feeds', [])

	def remove_playlist(self, author, title):
		feeds = self.get_all_playlists()
		for idx in range(len(feeds)):
			if feeds[idx]['author'] == author:
				for jdx in range(len(feeds[idx]['playlists'])):
					if feeds[idx]['playlists'][jdx]['title'] == title:
						del feeds[idx]['playlists'][jdx]
					if len(feeds[idx]['playlists']) == 0:
						del feeds[idx]
					break
				break
		self.write_to_db(feeds)

	def write_to_db(self, feeds):
		if 'feeds' not in self.db:
			self.db['feeds'] = []
		self.db['feeds'] = feeds
		self.db.sync()

	def update_last_update(self, author, playlist, published_parsed):
		feeds = self.get_all_playlists()
		for a in feeds:
			if a['author'] == author:
				for ch in a['playlists']:
					if ch['title'] == playlist['title']:
						ch['last_update'] = published_parsed
		self.write_to_db(feeds)


class Bluetooth(Client):
	'''Sends files to the given device'''

	SOCKETTIMEOUT = 120.0

	def __init__(self, device_id, bluetube_dir):
		self.found = self._find_device(device_id)
		if self.found:
			print("Checking connection to \"%s\" on %s" % (self.name, self.host))
			# Client is old style class, so don't use super
			Client.__init__(self, self.host, self.port)
			self.bluetube_dir = bluetube_dir
			self.in_progress = False
		else:
			Bcolors.error('Device {} is not found.'.format(device_id))

	def _find_device(self, device_id):
		service_matches = bluetooth.find_service(address = device_id)
		if len(service_matches) == 0:
			Bcolors.error("Couldn't find the service.")
			return False

		for s in service_matches:
			if s['name'] == 'OBEX Object Push':
				first_match = s
				break

		self.name = bluetooth.lookup_name(device_id)
		self.host = first_match["host"]
		self.port = first_match["port"]
		return True

	def _callback(self, resp, filename):
		if resp:
			if self.in_progress:
				sys.stdout.write('.')
			else:
				filename = filename.decode('utf-8')
				if len(filename) > 45:
					filename = filename[:42] + '...'
				sys.stdout.write(u'Sending "{}" to {}...'.format(filename,
																 self.name))
				self.in_progress = True
			sys.stdout.flush()

	def _put(self, name, file_data, header_list = ()):  # @UnusedVariable
		'''Modify the method from the base class
		to allow getting data from the file stream.'''

		header_list = [
			headers.Name(name),
			headers.Length(os.path.getsize(file_data))
			]

		max_length = self.remote_info.max_packet_length
		request = requests.Put()

		response = self._send_headers(request, header_list, max_length)
		yield response

		if not isinstance(response, responses.Continue):
			return

		optimum_size = max_length - 3 - 3

		i = 0
		size = os.path.getsize(file_data)
		while i < size:

			data = self.file_data_stream.read(optimum_size)
			i += len(data)
			if i < size:
				request = requests.Put()
				request.add_header(headers.Body(data, False), max_length)
				self.socket.sendall(request.encode())

				response = self.response_handler.decode(self.socket)
				yield response

				if not isinstance(response, responses.Continue):
					return
			else:
				request = requests.Put_Final()
				request.add_header(headers.End_Of_Body(data, False), max_length)
				self.socket.sendall(request.encode())

				response = self.response_handler.decode(self.socket)
				yield response

				if not isinstance(response, responses.Success):
					return

	def send(self, filenames):
		'''Sends files to the bluetooth device.
		Returns file names that has been sent.'''
		assert self.found, 'Device is not found. Create a new Bluetooth.'
		sent = []
		for fm in filenames:
			full_path = os.path.join(self.bluetube_dir, fm)
			if full_path.endswith('.part') or full_path.endswith('.ytdl'):
				# ignore but put them to send:
				#		partially downloaded files
				#		youtube-dl service files
				sent.append(full_path)
				continue
			self.file_data_stream = open(full_path, 'rb')
			try:
				resp = self.put(fm.decode('utf-8'),
								full_path,
								callback=lambda resp : self._callback(resp, fm))
				if resp:
					pass  # print(resp)
				else:
					print(u'\n{} sent.'.format(fm.decode('utf-8')))
					sent.append(full_path)
			except socket.error as e:
				Bcolors.error(str(e))
				Bcolors.error(u'{} didn\'t send'.format(fm.decode('utf-8')))
				print('Trying to reconnect...')
				self.socket.shutdown(socket.SHUT_RDWR)
				self.socket.close()
				del self.socket
				time.sleep(10.0)
				if not self.connect():
					break
				else:
					self.send([fm, ])
			except KeyboardInterrupt:
				Bcolors.error(u'Sending of {} stopped because of KeyboardInterrupt'
								.format(fm.decode('utf-8')))
			finally:
				self.in_progress = False
				self.file_data_stream.close()
		return sent

	def connect(self):
		status = False
		try:
			Client.connect(self)
			self.socket.settimeout(Bluetooth.SOCKETTIMEOUT)
			status = True
		except socket.error as e:
			Bcolors.error(str(e))
			Bcolors.warn('Some files will not be sent.')
		return status

	def disconnect(self):
		try:
			Client.disconnect(self)
			#  print(resp)
		except socket.errno as e:
			Bcolors.error(str(e))
			Bcolors.warn('Wait a minute.')
			time.sleep(60.0)


class Bluetube(object):
	''' The main class of the script. '''

	CONFIG_FILE = os.path.join(CUR_DIR, 'bluetube.cfg')
	DEFAULT_CONFIGS = u'''; Configurations for bluetube.
[bluetube]
downloader=youtube-dl
; enter your device ID in the line below
deviceID=YOUR_RECEIVER_DEVICE_ID
'''
	INDENTATION = 10

	def add_playlist(self, url, out_format):
		''' add a new playlists to RSS feeds '''
		out_format = self._get_type(out_format)
		feed_url = self._get_feed_url(url)
		if out_format and feed_url:
			f = feedparser.parse(feed_url)
			title = f.feed.title
			author = f.feed.author
			feeds = Feeds()
			if feeds.has_playlist(author, title):
				Bcolors.error(u'The playlist {} by {} has already been existed'.format(title, author))
			else:
				feeds.add_playlist(author, title, feed_url, out_format)
				Bcolors.intense(u'{} by {} added successfully.'.format(title, author))
			return 0
		return -1

	def list_playlists(self):
		''' list all playlists in RSS feeds '''
		feeds = Feeds('r')
		all_playlists = feeds.get_all_playlists()
		if len(all_playlists):
			for a in all_playlists:
				print(a['author'])
				for c in a['playlists']:
					o = u'{}{}'.format(u' ' * Bluetube.INDENTATION, c['title'])
					o = u'{} ({})'.format(o, time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(c['last_update'])))
					print(o)
		else:
			Bcolors.warn('The list of playlist is empty. Use --add to add a playlist.')

	def remove_playlist(self, author, title):
		''' remove a playlist be given title '''
		feeds = Feeds()
		if feeds.has_playlist(author, title):
			feeds.remove_playlist(author, title)
		else:
			Bcolors.error(u'{} by {} not found'.format(title, author))

	def run(self, verbose=False, show_all=False):
		''' The main method. It does everything.'''
		self.configs = self._get_configs()
		self.executor = CommandExecutor(verbose)

		if self._check_config_file():
			downloader = self.configs.get('bluetube', 'downloader')
			if self._check_downloader(downloader):
				return self._run(downloader, verbose, show_all)
		return -1

	def _run(self, downloader, verbose, show_all):
		feeds = Feeds()
		download_dir = self._fetch_download_dir()
		playlists = self._get_playlists_with_urls(feeds, show_all)
		sender = Bluetooth(self.configs.get('bluetube', 'deviceID'), download_dir)
		if len(playlists):
			return self._download_and_send_playlist(feeds,
													downloader,
													sender,
													playlists,
													download_dir,
													verbose)
		else:
			Bcolors.warn('No playlists in the list. Use --add to add a playlist.')
			return -1

	def _download_and_send_playlist(self, feeds, downloader, sender,
									playlists, download_dir, verbose):
		if not sender.found:
			Bcolors.warn('Your bluetooth device is not accessible.')
			Bcolors.warn('The script will download files to /tmp directory.')
			raw_input('Press Enter to continue, Ctrl+c to interrupt.')
		for ch in playlists:
			if len(ch['urls']):
				if self._download(downloader, ch, download_dir):
					feeds.update_last_update(ch['author'],
											ch['playlist'],
											ch['published_parsed'])
				else:
					Bcolors.error(u'Failed to download this playlist: \n\t{}'.format(ch['playlist']['title']))
				if sender.found:
					self._send(sender, download_dir)
			elif verbose:
				Bcolors.warn(u'Nothing to download from {}.'.format(ch['playlist']['title']))
		self._return_download_dir(download_dir)
		return 0

	def _get_configs(self):
		parser = SafeConfigParser()
		return None if len(parser.read(Bluetube.CONFIG_FILE)) == 0 else parser

	def _check_config_file(self):
		if self.configs == None:
			Bcolors.warn(u'''Configuration file is not found.\n
You must create {} with the content below manually in the script directory:\n{}\n'''.format(Bluetube.CONFIG_FILE, Bluetube.DEFAULT_CONFIGS))
			return False
		return True

	def _check_downloader(self, downloader):
		if self.executor.does_command_exist(downloader):
			return True
		else:
			Bcolors.error(u'ERROR: The tool for downloading from youtube "{}" is not found in PATH'.format(downloader))
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
		question = '{b}d{e}ownload | {b}r{e}eject | open in {b}b{e}rowser'.format(b=Bcolors.HEADER, e=Bcolors.ENDC)
		if summary:
			question = question + ' | {b}s{e}ummary'.format(b=Bcolors.HEADER, e=Bcolors.ENDC)

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
				print(u'{ind}{tit} ({h}:{min:0>2} {d}.{mon:0>2})'.format(**params))

				if self._ask(e['link'], summary=e['summary']):
					urls.append(e['link'])
				if new_last_update < e_update:
					new_last_update = e_update

		return {'author': author,
				'playlist': ch,
				'urls': urls,
				'published_parsed': new_last_update}

	def _download(self, downloader, playlist, download_dir):
		if downloader == 'youtube-dl':
			options = ('--ignore-config',
						'--ignore-errors',
						'--mark-watched',)
			out_format = playlist['playlist']['out_format']
			if out_format == 'audio':
				spec_options = ('--extract-audio',
								'--audio-format=mp3',
								'--audio-quality=9' # 9 means worse
								)
			elif out_format == 'video':
				spec_options = ('--format=3gp',)
			else:
				assert 0, 'unexpected output format; should be either "v" or "a"'
			args = (downloader,) + options + spec_options + tuple(playlist['urls'])
			return not self.executor.call(args, cwd=download_dir)
		else:
			Bcolors.error('ERROR: No downloader.')
			return False

	def _send(self, sender, download_dir):
		'''Send all files in the given directory'''
		if sender.found:
			files = os.listdir(download_dir)
			if sender.connect():
				sent = sender.send(files)
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
				Bcolors.warn('The download directory {} is not empty. Cannot delete it.'.format(bluetube_dir))


# ============================================================================ #


if __name__ == '__main__':

	parser = argparse.ArgumentParser(description='The script downloads youtube video as video or audio and sends to a bluetooth device.')
	parser.epilog = 'If no option specified the script shows feeds to choose, downloads and sends via bluetooth.'
	me_group = parser.add_mutually_exclusive_group()

	me_group.add_argument('--add', '-a', help='add a URL to youtube playlist', type=unicode)
	parser.add_argument('-t', dest='type', help='a type of a file you want to get (for --add)', choices=['a', 'v'], default='v')
	me_group.add_argument('--list', '-l', help='list all playlists', action='store_true')
	me_group.add_argument('--remove', '-r', nargs=2, help='remove a playlist by names of the author and the playlist', type=lambda s: unicode(s, 'utf8'))

	parser.add_argument('--show_all', '-s', action='store_true', help='show all available feed items despite last update time')
	parser.add_argument('--verbose', '-v', action='store_true', help='print more information')
	parser.add_argument('--version', action='version', version='%(prog)s 1.0')

	bluetube = Bluetube()
	args = parser.parse_args()
	if args.add:
		if not bluetube.add_playlist(args.add, args.type):
			sys.exit(-1)
	elif args.list:
		bluetube.list_playlists()
	elif args.remove:
		bluetube.remove_playlist(args.remove[0].strip(), args.remove[1].strip())
	else:
		bluetube.run(args.verbose, args.show_all)
	print('Done')
