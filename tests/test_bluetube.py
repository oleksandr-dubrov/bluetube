#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
sys.path.insert(0, os.path.abspath('..'))

import unittest
from bluetube import Bluetube
from bluetube import Feeds
from mock import patch


class TestBluetube(unittest.TestCase):
	'''The main tester class'''

	class InFeed(object):
		def __init__(self, author, title):
			self.title = title
			self.author = author
	
	
	class FakeFeed(object):
		def __init__(self, author, title):
			self.feed = TestBluetube.InFeed(title, author)
			

	def setUp(self):
		self.SUT = Bluetube()

	def tearDown(self):
		if os.path.isfile(Feeds.DATABASE_FILE) and os.path.exists(Feeds.DATABASE_FILE):
			os.remove(Feeds.DATABASE_FILE)
		if os.path.isfile(Bluetube.CONFIG_FILE) and os.path.exists(Bluetube.CONFIG_FILE):
			os.remove(Bluetube.CONFIG_FILE)

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

		print 'ADDING CHANNELS'
		ret = self.SUT.add_channel(url1, 'a')
		self.assertFalse(ret, 'add channel 1 failed')

		ret = self.SUT.add_channel(url1, 'a')
		self.assertFalse(ret, 'add channel 1 for the second time failed')

		ret = self.SUT.add_channel(url2, 'v')
		self.assertFalse(ret, 'add channel 2 failed')

		ret = self.SUT.add_channel(url3, 'v')
		self.assertFalse(ret, 'add channel 3 failed')

		print 'SHOW ALL CHANNELS'
		self.SUT.list_channels()
# 
		print 'REMOVE ONE CHANNAL THAT DOES EXIST'
		self.SUT.remove_channel(u'Вольнов Talks', u'Все видео канала')
		

		print 'REMOVE A NON-EXISTAING CHANNAL'
		self.SUT.remove_channel(u'author', u'name')

		print 'REMOVE ANOTHER CHANNAL THAT DOES EXIST'
		self.SUT.remove_channel(u'Евгений Вольнов', u'Настенька')

		print 'SHOW ALL CHANNELS AGAIN'
		self.SUT.list_channels()

	@patch('bluetube.subprocess.call')
	def test_run_precondition_fails(self, mocked_call):
		'''1st - no configs
		   2nd - no youtube-dl 
		   3rd - no blutooth-send'''
		
		self.assertTrue(self.SUT.run(), 'No configuration file, the case should fail')
		
		self._create_a_configuration_file()
		
		mocked_call.side_effect = [OSError(-1, 'no youtube-dl'),
								OSError(0, ''),
								OSError(-1, 'no bluetooth-send')]
		self.assertTrue(self.SUT.run(), 'No youtube-dl in the PATH, the case should fail')
		self.assertTrue(self.SUT.run(), 'No bluetooth-send in the PATH, the case should fail')
		print 'DONE'


	@patch('bluetube.subprocess.call')
	def test_run(self, mocked_call):
		mocked_call.side_effect = [OSError(0, ''),
									OSError(0, ''),
									OSError(-1, 'no bluetooth-send')]
		self._create_a_configuration_file()
		
		print 'ADDING CHANNELS'
		ret = self.SUT.add_channel('https://www.youtube.com/watch?v=VTC8gj01s6g&list=PL17KOAV8JBN_uE7v4qgQxLX7kno4G9HyQ', 'a')
		self.assertFalse(ret, 'add channel failed')
		
		ret = self.SUT.run()
	
	def _create_a_configuration_file(self):
		with open(Bluetube.CONFIG_FILE, 'w') as f:
			f.write(Bluetube.DEFAULT_CONFIGS)


if __name__ == "__main__":
	unittest.main()
