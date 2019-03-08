#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time
sys.path.insert(0, os.path.abspath('..'))

import unittest
from bluetube import Bluetube
from bluetoothclient import BluetoothClient
from feeds import Feeds
from mock import patch  # @UnresolvedImport


class TestBluetube(unittest.TestCase):
	'''The main tester class'''

	class InFeed(object):
		def __init__(self, author, title):
			self.title = title
			self.author = author
	
	
	class FakeFeed(object):
		def __init__(self, author, title, entries=[]):
			self.feed = TestBluetube.InFeed(title, author)
			self.entries = entries
			

	class FakeSocket(object):
		def shutdown(self):
			pass
		def close(self):
			pass
		def settimeout(self, ms):
			pass

	class FakeClient(object):
		def __init__(self):
			self.socket = TestBluetube.FakeSocket()

	@staticmethod
	def good_side_effect(*args, **kwargs):
		if '--version' in args[0]:
			print('--version')
		elif 'youtube-dl' in args[0][0]:
			assert os.path.exists(kwargs['cwd']) and os.path.isdir(kwargs['cwd']), \
				'{} directory is not found'.format(kwargs['cwd'])
			name = args[0][-1].split('=')[1]
			ext = None
			for x in args[0]:
				if '--audio-format' in x:
					ext = x.split()[-1]
					break
			assert ext, 'no --audio-format found in the command'
			with open(os.path.join(kwargs['cwd'], '{}.{}'.format(name, ext)), 'w') as f:
				f.write(str(args))
		elif 'blue' in args[0][0]:
			path = os.path.join(kwargs['cwd'], args[0][-1])
			assert os.path.exists(path) and os.path.isfile(path), \
				'{} not found'.format(path)
		return 0
		
	def setUp(self):
		self.SUT = Bluetube()

	def tearDown(self):
		db_file = Feeds(Bluetube.CUR_DIR).db_file
		if os.path.isfile(db_file) and os.path.exists(db_file):
			os.remove(db_file)
		if os.path.isfile(Bluetube.CONFIG_FILE) and os.path.exists(Bluetube.CONFIG_FILE):
			os.remove(Bluetube.CONFIG_FILE)
		download_dir = os.path.join(os.getcwd(), 'Downloads')
		if os.path.exists(download_dir):
			try:
				os.rmdir(download_dir)
			except OSError:
				print('The download directory {} is not empty. Some test doesn\'t remove downloaded files.'.format(download_dir))

	@patch('bluetube.feedparser.parse')
	def test_add_list_remove(self, mocked_feed):
		mocked_feed.side_effect = [TestBluetube.FakeFeed(u"Евгений Вольнов", u"Настенька"),
								TestBluetube.FakeFeed(u"Евгений Вольнов", u"Настенька"),
								TestBluetube.FakeFeed(u"Вольнов Talks", u"Все відео"),
								TestBluetube.FakeFeed(u"ВатаШоу", u"Чатрулетка")
		]

		url1 = 'https://www.youtube.com/watch?v=4bvAIa5hjFk&list=PLV4xApIh67zHZXf4DoSDtXqVvneSgh-1X'
		url2 = 'https://www.youtube.com/watch?v=GKJLAvTrRKA&list=PLlnMlUDFFfEs8eO4L3haB5V1qO2syoHQJ'
		url3 = 'https://www.youtube.com/watch?v=2y3gqxklW04&list=PLU8zrvU8pCeXhM_32znSFmCBFuswP5_Cv'

		print('ADDING CHANNELS')
		ret = self.SUT.add_playlist(url1, 'a')
		self.assertTrue(ret, 'add playlist 1 failed')

		ret = self.SUT.add_playlist(url1, 'a')
		self.assertTrue(ret, 'add playlist 1 for the second time failed')

		ret = self.SUT.add_playlist(url2, 'v')
		self.assertTrue(ret, 'add playlist 2 failed')

		ret = self.SUT.add_playlist(url3, 'v')
		self.assertTrue(ret, 'add playlist 3 failed')

		print('SHOW ALL CHANNELS')
		self.SUT.list_playlists()
# 
		print('REMOVE ONE CHANNAL THAT DOES EXIST')
		self.SUT.remove_playlist(u'Вольнов Talks', u'Все видео канала')

		print('REMOVE A NON-EXISTAING CHANNAL')
		self.SUT.remove_playlist(u'author', u'name')

		print('REMOVE ANOTHER CHANNAL THAT DOES EXIST')
		self.SUT.remove_playlist(u'Евгений Вольнов', u'Настенька')

		print('SHOW ALL CHANNELS AGAIN')
		self.SUT.list_playlists()

	@patch('bluetube.raw_input')
	@patch('bluetube.Bluetube._get_playlists_with_urls')
	@patch('bluetoothclient.bluetooth.find_service')
	def test_run_precondition_fails(self, mocked_find_service,
										mocked_get_urls,
										mocked_raw_input):  # @UnusedVariable
		'''1st - no configurations
		   2nd - no remote bluetoothclient device'''

		self.assertFalse(self.SUT.run(), 'No configuration file, the case should fail')

		self._create_a_configuration_file()
		mocked_find_service.return_value = []
		mocked_get_urls.return_value = [{'urls': []}, ]

		self.assertTrue(self.SUT.run(), 'no remote bluetoothclient device, the case succeed')

	@patch('bluetoothclient.Client')
	@patch('os.path.expanduser')
	@patch('PyOBEX.client.Client.disconnect')
	@patch('PyOBEX.client.Client.connect')
	@patch('PyOBEX.client.Client.put')
	@patch('bluetoothclient.bluetooth.lookup_name')
	@patch('bluetoothclient.bluetooth.find_service')
	@patch('bluetube.raw_input')
	@patch('bluetube.feedparser.parse')
	@patch('bluetube.subprocess.call')
	def test_run(self,  # @DontTrace
				mocked_call,
				mocked_feed_parse,
				mocked_raw_input,
				mocked_find_service,
				mocked_lookup_name,
				mocked_client_put,
				mocked_client_connect,  # @UnusedVariable
				mocked_client_disconnect,  # @UnusedVariable
				mocked_expanduser,
				mocked_client):  # @UnusedVariable

		mocked_call.side_effect = TestBluetube.good_side_effect

		entries = [{'title': u'Маркевич — як помирали Металіст та Дніпро',
					'link' : 'https://www.youtube.com/watch?v=1',
					'published_parsed': time.localtime(),
					'summary': u'summary 1'},
					{'title': u'Сабо - як відривалися радянські футболісти та про Динамо за лаштунками',
					'link': 'https://www.youtube.com/watch?v=2',
					'published_parsed': time.localtime(),
					'summary': u'summary 2'}
				]
		mocked_feed_parse.side_effect = [TestBluetube.FakeFeed(u"Вацко Live", u"Вацко Light"),
										TestBluetube.FakeFeed(u"Вацко Live", u"Вацко Light", entries)]
		mocked_raw_input.side_effect = ['y', 'n']
		mocked_find_service.return_value = [{'name': 'OBEX Object Push', 'host': 'host', 'port': 1}]
		mocked_lookup_name.return_value = 'Symbian S60'
		mocked_client_put.return_value = False
		mocked_expanduser.return_value = os.getcwd()
		BluetoothClient.socket = TestBluetube.FakeSocket()

		self._create_a_configuration_file()

		print('ADDING CHANNELS')
		# use real URL in order to pass the validation
		ret = self.SUT.add_playlist('https://www.youtube.com/watch?v=VTC8gj01s6g&list=PL17KOAV8JBN_uE7v4qgQxLX7kno4G9HyQ', 'a')
		self.assertTrue(ret, 'add playlist failed')
		
		ret = self.SUT.run()
		self.assertTrue(ret, 'run failed')
	
	def _create_a_configuration_file(self):
		with open(Bluetube.CONFIG_FILE, 'w') as f:
			f.write(Bluetube.DEFAULT_CONFIGS)


if __name__ == "__main__":
	unittest.main()
