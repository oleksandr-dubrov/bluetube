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
import shelve
import subprocess
import sys
import re
import webbrowser
import time
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

	def __init__(self):
		self._verbose = False
		
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

	DATABASE_FILE = 'bluetube.dat'

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
		return shelve.open(Feeds.DATABASE_FILE, flag='r')
	
	def get_authors(self):
		if 'feeds' in self.db:
			return [a['author'] for a in self.db['feeds']]
		return []

	def get_channels(self, author):
		authors = self.get_authors()
		if authors:
			for au in self.db['feeds']:
				if au['author'] == author:
					return [ch['title'] for ch in au['channels']]
		return []

	def has_channel(self, author, channel):
		if channel in self.get_channels(author):
			return True
		return False

	def add_channel(self, author, title, url, out_format):
		feeds = self.get_all_channels()

		# create a channel 
		channel = {"title": title,
					"url": url,
					"last_update" : 0,
					"out_format": out_format}

		# insert the channel into the author
		if author not in [f['author'] for f in feeds]:
			feeds.append({'author': author, 'channels': []})
		for f in feeds:
			if f['author'] == author:
				f['channels'].append(channel)
				break

		self.write_to_db(feeds)

	def get_all_channels(self):
		return self.db.get('feeds', [])

	def remove_channel(self, author, title):
		feeds = self.get_all_channels()
		for idx in range(len(feeds)):
			if feeds[idx]['author'] == author:
				for jdx in range(len(feeds[idx]['channels'])):
					if feeds[idx]['channels'][jdx]['title'] == title:
						del feeds[idx]['channels'][jdx]
					if len(feeds[idx]['channels']) == 0:
						del feeds[idx]
					break
				break
		self.write_to_db(feeds)

	def write_to_db(self, feeds):
		if 'feeds' not in self.db:
			self.db['feeds'] = []
		self.db['feeds'] = feeds
		self.db.sync()

	def update_last_update(self, author, channel, published_parsed):
		feeds = self.get_all_channels()
		for a in feeds:
			if a['author'] == author:
				for ch in a['channels']:
					if ch['title'] == channel['title']:
						ch['last_update'] = published_parsed
		self.write_to_db(feeds)


class Bluetooth(Client):
	'''Sends files to the given device'''

	def __init__(self, device_id, bluetube_dir):
		self.found = self._find_device(device_id)
		if self.found:
			print("Checking connection to \"%s\" on %s" % (self.name, self.host))
			Client.__init__(self, self.host, self.port) # Client is old style class, so don't use super
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

	def _callback(self, resp):
		if resp:
			if self.in_progress:
				sys.stdout.write('.')
			else:
				sys.stdout.write('Sending to {}...'.format(self.name))
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
		self.connect()
		for fm in filenames:
			full_path = os.path.join(self.bluetube_dir, fm)
			self.file_data_stream = open(full_path, 'rb')
			resp = self.put(fm.decode('utf-8'), full_path, callback=self._callback)
			if resp:
				print(resp)
			else:
				print('\n{} sent.'.format(fm))
				sent.append(full_path)
			self.in_progress = False
			self.file_data_stream.close()
		self.disconnect()
		return sent


class Bluetube(object):
	''' The main class of the script. '''

	CONFIG_FILE = 'bluetube.cfg'
	DEFAULT_CONFIGS = u'''; Configurations for bluetube.
[bluetube]
downloader=youtube-dl
; enter your device ID in the line below
deviceID=YOUR_RECEIVER_DEVICE_ID
'''

	def __init__(self):
		pass

	def add_channel(self, url, out_format):
		''' add a new channels to RSS feeds '''
		out_format = self._get_type(out_format)
		feed_url = self._get_feed_url(url)
		if out_format and feed_url:
			f = feedparser.parse(feed_url)
			title = f.feed.title
			author = f.feed.author
			feeds = Feeds()
			if feeds.has_channel(author, title):
				Bcolors.error(u'The channel {} by {} has already been existed'.format(title, author))
			else:
				feeds.add_channel(author, title, feed_url, out_format)
				Bcolors.intense(u'{} by {} added successfully.'.format(title, author))
			return 0
		return -1

	def list_channels(self):
		''' list all channels in RSS feeds '''
		feeds = Feeds('r')
		all_channels = feeds.get_all_channels()
		if len(all_channels):
			for a in all_channels:
				print(a['author'])
				for c in a['channels']:
					o = u'{}{}'.format(u' ' * len(a['author']), c['title'])
					o = u'{} ({})'.format(o, time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(c['last_update'])))
					print(o)
		else:
			Bcolors.warn('The list of channel is empty. Use --add to add a channel.')

	def remove_channel(self, author, title):
		''' remove a channel be given title '''
		feeds = Feeds()
		if feeds.has_channel(author, title):
			feeds.remove_channel(author, title)
		else:
			Bcolors.error(u'{} by {} not found'.format(title, author))
		
	def run(self):
		''' The main method. It does everything.'''
		self.configs = self._get_configs()
		self.executor = CommandExecutor()
		
		if self._check_config_file():
			downloader = self.configs.get('bluetube', 'downloader')
			if self._check_downloader(downloader):
				self._run(downloader)
				return 0
		return -1

	def _run(self, downloader):
		feeds = Feeds()
		download_dir = self._fetch_download_dir()
		channels = self._get_channels_with_urls(feeds)
		if len(channels):
			sender = Bluetooth(self.configs.get('bluetube', 'deviceID'), download_dir)
			for ch in channels:
				if self._download(downloader, ch, download_dir):
					feeds.update_last_update(ch['author'], ch['channel'], ch['published_parsed'])
					self._send(sender, download_dir)
				else:
					Bcolors.error(u'Failed to download this channel: \n\t{}'.format(ch['channel']['title']))
			self._return_download_dir(download_dir)
		else:
			Bcolors.warn('No channels in the list. Use --add to add a channel.')

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
		p = re.compile('^https://www\.youtube\.com/watch\?v=.+&list=(.+)$')
		m = p.match(url);
		if m:
			return 'https://www.youtube.com/feeds/videos.xml?playlist_id={}'.format(m.group(1))
		else:
			Bcolors.error(u'ERROR: misformatted URL of a youtube list provided./n Should be https://www.youtube.com/watch?v=XXX&list=XXX')
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
				print('Summary:\n{}'.format(summary))
			elif i in open_browser:
				print('Opening the link in the default browser...')
				webbrowser.open(link, new=2)
			else:
				Bcolors.error(u'{}{} to download, {} for reject, {} to get a summary (if any), {} to open in a browser.{}'
						.format(Bcolors.FAIL, d[0], r[0], s[0], open_browser[0], Bcolors.ENDC))

	def _get_channels_with_urls(self, feeds):
		'''get URLs from the RSS that the user will selected for every channel'''
		all_channels = feeds.get_all_channels()
		channels = []
		for chs in all_channels:
			print(chs['author'])
			ind1 = u' ' * len(chs['author'])
			for ch in chs['channels']:
				channels.append(self._process_channel(chs['author'], ch, ind1))

		return channels

	def _process_channel(self, author, ch, ind):
		urls = []
		new_last_update = last_update = ch['last_update']
		print(u'{ind}{tit}'.format(ind=ind, tit=ch['title']))
		ind2 = len(ch['title']) / 2 * u' '
		f = feedparser.parse(ch['url'])
		for e in f.entries:
			pub = e['published_parsed']
			params = {'ind': ind+ind2,
					'tit': e['title'],
					'h': pub.tm_hour,
					'min': pub.tm_min,
					'd': pub.tm_mday,
					'mon': pub.tm_mon}

			e_update = time.mktime(e['published_parsed'])
			if last_update < e_update:
				print(u'{ind}{tit} ({h}:{min:0>2} {d}.{mon:0>2})'.format(**params))

				if self._ask(e['link'], summary=e['summary']):
					urls.append(e['link'])
					if new_last_update < e_update:
						new_last_update = e_update

		return {'author': author,
				'channel': ch,
				'urls': urls,
				'published_parsed': new_last_update}

	def _download(self, downloader, channel, download_dir):
		if downloader == 'youtube-dl':
			options = ('--ignore-config',
					'--mark-watched',)
			out_format = channel['channel']['out_format']
			if out_format == 'audio':
				spec_options = ('--extract-audio',
								'--audio-format=mp3',
								'--audio-quality=9' # 9 means worse
								)
			elif out_format == 'video':
				spec_options = ('--format=3gp',)
			else:
				assert 0, 'unexpected output format; should be either "v" or "a"'

			args = (downloader,) + options + spec_options + tuple(channel['urls'])
			return not self.executor.call(args, cwd=download_dir)
		else:
			Bcolors.error('ERROR: No downloader.')
			return False

	def _send(self, sender, download_dir):
		'''Send all files in the given directory'''
		if sender.found:
			files = os.listdir(download_dir)
			sent = sender.send(files)
			for f in sent:
				os.remove(f)

	def _fetch_download_dir(self):
		home = os.path.expanduser('~')
		download_dir = os.path.join(home, 'Downloads')
		if not os.path.isdir(download_dir):
			Bcolors.warn('no directory for downloads, it will be created now')
			os.mkdir(download_dir)
		bluetube_dir = os.path.join(download_dir, 'bluetube.tmp')
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

	me_group.add_argument('--add', '-a', help='add a URL to youtube channel', type=unicode)
	parser.add_argument('-t', dest='type', help='a type of a file you want to get (for --add)', choices=['a', 'v'], default='v')
	me_group.add_argument('--list', '-l', help='list all channels', action='store_true')
	me_group.add_argument('--remove', '-r', nargs=2, help='remove a channel by names of the author and the channel', type=lambda s: unicode(s, 'utf8'))

	parser.add_argument('--version', action='version', version='%(prog)s 1.0')

	bluetube = Bluetube()
	args = parser.parse_args()
	if args.add:
		if not bluetube.add_channel(args.add, args.type):
			sys.exit(-1)
	elif args.list:
		bluetube.list_channels()
	elif args.remove:
		bluetube.remove_channel(args.remove[0].strip(), args.remove[1].strip())
	else:
		bluetube.run()
	print('Done')
