#!/usr/bin/env python
# -*- coding: utf-8 -*-

__version__ = '2.1'
__author__ = 'OD'
__license__ = 'GNU GPLv2'


#########################################################################
# This a script that loads RSS and sends selected feeds to my Nokia N73.#
#########################################################################


import argparse
import os
import shelve
import subprocess
import sys
import re
from ConfigParser import SafeConfigParser


try:
	import feedparser
except ImportError:
	print('''No feedparser in your environment. Run next command to install it:\n	pip install feedparser''')
	sys.exit(-1)


class CommandExecutor(object):
	'''This class run the commands in the shell'''
	
	def __init__(self):
		pass
		
	def call(self, args, cwd=None):
		if cwd == None:
			cwd = os.getcwd()
		call_env = os.environ
		return_code = 0
		try:
			print('RUN: {}'.format(args))
			return_code = subprocess.call(args, env=call_env, cwd=cwd)
		except OSError as e:
			return_code = e.errno
			print(e.strerror)
		return return_code

	def does_command_exist(self, name):
		'''call a command with the given name and expects that it has option --version'''
		return not self.call((name, '--version'));


class Feeds(object):
	'''Manages a RSS feeds in the shelve database'''

	DATABASE_FILE = 'bluetooth.dat'

	def __init__(self, mode):
		self.db = None
		if mode == 'r':
			self.db = Feeds._create_ro_connector()
		elif mode == 'rw':
			self.db = Feeds._create_rw_connector()
		else:
			print('the access mode should be either "rw" or "r"')

	def __del__(self):
		if self.db:
			try:
				self.db.close()
			except ValueError as e:
				print('Probably your changes were lost. Try again')
				raise e

	@staticmethod
	def _create_rw_connector():
		'''create db connector in read/write mode'''
		return shelve.open(Feeds.DATABASE_FILE, flag='c', writeback=False)

	@staticmethod
	def _create_ro_connector():
		'''create db connector in read-only mode'''
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
					"last_update" : None,
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


class Bluetube(object):
	''' The main class of the script. '''

	CONFIG_FILE = 'bluetube.cfg'
	DEFAULT_CONFIGS = u'''[bluetube]
; Configurations for bluetube
downloader=youtube-dl
sender=blueman-sendto
deviceID=YOUR_RECEIVER_DEVICE_ID
'''

	def __init__(self):
		pass

	def add_channel(self, url, out_format):
		''' add a new channels to RSS feeds '''
		out_format = self._get_type(out_format)
		feed_url = self._get_feed_url(url)
		feeds = Feeds('rw')
		if out_format and feed_url:
			f = feedparser.parse(feed_url)
			title = f.feed.title
			author = f.feed.author
			if feeds.has_channel(author, title):
				print(u'The channel {} by {} has already existed'.format(title, author))
			else:
				feeds.add_channel(author, title, feed_url, out_format)
				print(u'{} by {} added successfully.'.format(title, author))
			return 0
		return -1

	def list_channels(self):
		''' list all channels in RSS feeds '''
		feeds = Feeds('r')
		all_channels = feeds.get_all_channels()
		for a in all_channels:
			print(a['author'])
			for c in a['channels']:
				o = u'{}{}'.format(u' ' * len(a['author']), c['title'])
				if c['last_update']:
					o = u'{} ({})'.format(o, c['last_update'])
				print(o)

	def remove_channel(self, author, title):
		''' remove a channel be given title '''
		feeds = Feeds('rw')
		if feeds.has_channel(author, title):
			feeds.remove_channel(author, title)
		else:
			print(u'{} by {} not found'.format(title, author))
		
	def run(self):
		''' The main method. It does everything.'''
		self.configs = self._get_configs()
		self.executor = CommandExecutor()
		
		if self._check_config_file():
			downloader = self.configs.get('bluetube', 'downloader')
			sender = self.configs.get('bluetube', 'sender')
			if self._check_downloader(downloader) and self._check_sender(sender):
				channels = self._get_channels_with_urls()
				download_dir = self._fetch_download_dir()
				for ch in channels:
					if self._download(downloader, ch, download_dir):
						self._send(sender, download_dir)
					else:
						print('Failed to downloed this channel: \n\t{}'.format(ch.channel.title))
				self._return_download_dir(download_dir)
				return 0
		return -1

	def _get_configs(self):
		parser = SafeConfigParser()
		return None if len(parser.read(Bluetube.CONFIG_FILE)) == 0 else parser

	def _check_config_file(self):
		if self.configs == None:
			print(u'''No configuration file was found.\n
You must create {} with the content below manually:\n{}\n'''.format(Bluetube.CONFIG_FILE, Bluetube.DEFAULT_CONFIGS))
			return False
		return True

	def _check_downloader(self, downloader):
		if self.executor.does_command_exist(downloader):
			return True
		else:
			print(u'ERROR: The tool for downloading from youtube "{}" is not found in PATH'.format(downloader))
			return False

	def _check_sender(self, sender):
		if self.executor.does_command_exist(sender):
			return True
		else:
			print(u'ERROR: The tool for sending files via bluetooth "{}" is not found in PATH'.format(sender))
			return False

	def _get_type(self, out_format):
		if out_format in ['a', 'audio']:
			return 'audio'
		elif out_format in ['v', 'video']:
			return 'video'
		else:
			print('ERROR: unexpected output type. Should be v (or video) or a (audio) separated by SPACE')
		return None

	def _get_feed_url(self, url):
		p = re.compile('^https://www\.youtube\.com/watch\?v=.+&list=(.+)$')
		m = p.match(url);
		if m:
			return 'https://www.youtube.com/feeds/videos.xml?playlist_id={}'.format(m.group(1))
		else:
			print(u'ERROR: misformatted URL of a youtube list provided./n Should be https://www.youtube.com/watch?v=XXX&list=XXX')
			return None

	def _yes_or_no(self, question):
		'''ask if perform something'''
		yes = [u'd', u'D', u'В', u'в', u'Y', u'y', u'Н', u'н', u'yes', u'YES'] # d for download
		no = [u'r', u'R', u'к', u'К', u'n', u'N', u'т', u'Т', u'no', u'NO'] # r for reject
		while True:
			i = raw_input('{}\n'.format(question))
			if i in yes:
				return True
			elif i in no:
				return False
			else:
				print(u'Type {} for "yes" or {} for "no".'.format(yes, no))

	def _get_channels_with_urls(self):
		'''get URLs from the RSS that the user will selected for every channel'''
		feeds = Feeds('r')
		all_channels = feeds.get_all_channels()
		channels = []
		for chs in all_channels:
			print(chs['author'])
			ind1 = u' ' * len(chs['author'])
			urls = []
			for ch in chs['channels']:
				print(u'{ind}{tit}'.format(ind=ind1, tit=ch['title']))
				ind2 = len(ch['title']) / 2 * u' '
				f = feedparser.parse(ch['url'])
				for e in f.entries:
					print(u'{ind}{tit}'.format(ind=ind1+ind2,
												tit=e['title']))
					if self._yes_or_no('(d)ownload or (r)eject'):
						urls.append(e['link'])
				channels.append({'channel': ch, 'urls': urls})
		return channels
	
	def _download(self, downloader, channel, download_dir):
		if downloader == 'youtube-dl':
			options = ('--ignore-config',
					'--mark-watched',
					'--dateafter {}'.format(channel['channel']['last_update']
											if channel['channel']['last_update']
											else '19700101'), # the beginning of the epoch
					)
			out_format = channel['channel']['out_format']
			if out_format == 'audio':
				spec_options = ('--extract-audio',
								'--audio-format mp3',
								'--audio-quality 9' # 9 means worse
								)
			elif out_format == 'video':
				spec_options = ('--format 3gp',)
			else:
				assert 0, 'unexpected output format; should be either "v" or "a"'

			args = (downloader,) + options + spec_options + tuple(channel['urls'])
			self.executor.call(args, cwd=download_dir)
			return True
		else:
			print('ERROR: No downloader.')
			return False

	def _send(self, sender, bluetube_dir):
		'''Send all files in the given directory one by one.
		If a file filed to be sent try to send it again.'''
		files = os.listdir(bluetube_dir)
		options = [sender, '--device={}'.format(self.configs.get('bluetube', 'deviceID'))]
		# sent each file separately to re-send only the file that failed
		for f in files:
			attempts = 3
			options.append(f)
			status = -1
			while attempts and status:
				status = self.executor.call(options, cwd=bluetube_dir)
				if status:
					print('WARNING: failed to send file.')
					attempts -= 1
			if attempts > 0:
				os.remove(os.path.join(bluetube_dir, f))
				return 0
			return -1

	def _fetch_download_dir(self):
		home = os.path.expanduser('~')
		download_dir = os.path.join(home, 'Downloads')
		if not os.path.isdir(download_dir):
			print('no directory for downloads, it will be created now')
			os.mkdir(download_dir)
		bluetube_dir = os.path.join(download_dir, 'bluetube')
		if not os.path.isdir(bluetube_dir):
			os.mkdir(bluetube_dir)
		return bluetube_dir

	def _return_download_dir(self, bluetube_dir):
		if os.path.isdir(bluetube_dir):
			try:
				os.rmdir(bluetube_dir)
			except OSError:
				print('The directory {} is not empty. Cannot delete it.')


# ============================================================================ #	


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='The script downloads youtube video as video or audio and sends to a bluetooth device.')
	me_group = parser.add_mutually_exclusive_group()

	me_group.add_argument('--add', '-a', help='add a URL to youtube channel', type=unicode)
	parser.add_argument('-t', dest='type', help='a type of a file you want to get (for --add)', choices=['a', 'v'], default='v')
	me_group.add_argument('--list', '-l', help='list all channels', action='store_true')
	me_group.add_argument('--remove', '-r', nargs=2, help='remove a channel by names of the author and the channel', type=unicode)

	parser.add_argument('--version', action='version', version='%(prog)s 1.0')

	bluetube = Bluetube()
	args = parser.parse_args()
	if args.add:
		if bluetube.add_rss(args.add, args.type):
			sys.exit(-1)
	elif args.list:
		bluetube.list_channels()
	elif args.remove:
		bluetube.remove_channel(args.remover[0], args.remove[1])
	else:
		bluetube.run()
