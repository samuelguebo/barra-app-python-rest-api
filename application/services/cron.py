from datetime import datetime
import time
from application.models.degree import Degree
from application.models.tag import Tag
from application.models.offer import DeegreeSchema, Offer, TagsSchema
from application.ai.classifier import Classifier
from application.dao.offer_dao import OfferDao
import re
from bs4 import BeautifulSoup
import requests
from config import Config, db

class Cron:
	"""
	Base class for automated operations, a.k.a cron jobs.
	Cron tasks will inherit this class 
	"""
	
	ID = 'default'
	CACHE_DELAY = 12 # twelve hours by default
	DETAILS_SELECTOR = '.detailsOffre > div:not(.content-area)'
	OFFERS_SELECTOR = 'ul#myList .box.row'
	TITLES_SELECTOR = '.text-col h4 a'
	DESC_SELECTOR = '.text-col .entry-title a'		

	def __init__(self):
		self = self


	def extractWithRegex(self, text, regexPattern, unique=False):
		"""
		Use a Regex expression to extract certain portions of texts
		
		:param text: Body of text to comb through
		:param regexPattern: Regular expression used for extraction
		"""
		
		matches = []
		matches = [match.replace(' ', '') for match in re.findall(regexPattern, text)]

		# Grab only first item
		if len(matches) == 1 or (len(matches) > 0 and unique):
			return matches[0];
		
		return matches


	def extractContent(self, url, selector):
		"""
		Scan through url to get page content 
		"""

		html_doc = requests.get(url).text
		soup = BeautifulSoup(html_doc, 'html.parser')
		content = ""

		for x in soup.select(selector):
			content += x.get_text()

		return content.replace("\n\n", " ")
    

	def extractDegrees(self, text):
		"""
		Extract the education level requirements
		"""
		
		degrees = self.extractWithRegex(text.upper(), Config.DEGREE_REGEX)
		if isinstance(degrees, list):
			degrees = [Degree(x) for x in set(degrees)]
		else:
			degrees = [Degree(degrees)]
		
		return degrees


	def extractType(self, text):
		"""
		Extract the type of job offer
		"""
		
		result = self.extractWithRegex(text.upper(), Config.TYPE_REGEX, True)
		if len(result) < 1:
			return Config.DEFAULT_TYPE
		
		return result


	def scrape_home_page(self, url):
		"""
		Comb through url to extract content
		"""

		html_doc = requests.get(url).text
		soup = BeautifulSoup(html_doc, 'html.parser')
		nodes = soup.select(self.OFFERS_SELECTOR)
		
		for node in nodes:

			# Data mapping
			url = "".join([x['href'] for x in node.select(self.TITLES_SELECTOR)])
			title = "".join([x.get_text() for x in node.select(self.TITLES_SELECTOR)])
			desc = "".join([x.get_text() for x in node.select(self.DESC_SELECTOR)])
			dates = self.extract_dates(node.get_text())

			pubDate = None
			expDate = None

			if len(dates) > 1:
				pubDate = dates[0]
				expDate = dates[1]

			# Check whether we have a valid url
			if len(url) > 10: 
				
				# Extract additional details: degree, type of offers, etc.
				print('{} {} {}'.format(url, title, desc, pubDate, expDate))
				offer = Offer(url, title, desc, pubDate, expDate)
				offer.content = self.extractContent(url, self.DETAILS_SELECTOR)
				offer.degrees = self.extractDegrees(offer.content)
				offer.set_type(self.extractType(offer.content))
				offer.tags = [Tag(x) for x in Classifier().predict_category(offer)]
				
				# Save to database
				dao = OfferDao(db)
				dao.create(offer)


	def extract_dates(self, text):
		"""
		Extract dates from the content
		of a job offer.
		"""
		datesRegx = "[0-9]{2}[\/\s]?[0-9]{2}[\/\s]?[0-9]{4}"
		return re.findall(datesRegx, text)