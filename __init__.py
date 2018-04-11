#!/usr/bin/env python2
# -*- coding: utf-8 -*-

__license__ = 'GPL v3'
__copyright__ = '2017, Bernhard Geier <geierb@geierb.de>'
__docformat__ = 'en'

from calibre.ebooks.metadata.sources.base import Source
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.book.base import Metadata

import re, datetime
from urllib import quote
from lxml import etree

from Queue import Queue, Empty

class DNB_DE(Source):
    name = 'DNB_DE'
    description = _('Downloads metadata from the DNB (Deutsche National Bibliothek). Requires a personal SRU Access Token')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Citronalco'
    version = (1, 0, 2)
    minimum_calibre_version = (0, 8, 0)

    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset(['title', 'authors', 'publisher', 'pubdate', 'languages', 'tags', 'identifier:urn', 'identifier:idn','identifier:isbn'])
    can_get_multiple_covers = False
    supports_gzip_transfer_encoding = True
    cached_cover_url_is_reliable = True
    prefer_results_with_isbn = True

    QUERYURL = 'https://services.dnb.de/sru/dnb?version=1.1&accessToken=%s&maximumRecords=100&operation=searchRetrieve&query=%s'
    COVERURL = 'https://portal.dnb.de/opac/mvb/cover.htm?isbn=%s'

    def config_widget(self):
	self.cw = None
	from calibre_plugins.DNB_DE.config import ConfigWidget
	return ConfigWidget(self)

    def is_customizable(self):
	return True

    def identify(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30):
	idn = identifiers.get('dnb-idn', None)
	isbn = check_isbn(identifiers.get('isbn', None))

	# ignore unknown authors
	if authors is "V. A." or authors is "V.A." or authors is "Unknown" or authors is "Unbekannt":
	    authors = None

	if (isbn is None) and (idn is None) and (title is None) and (authors is None):
	    log.info("This plugin requires at least either ISBN, IDN, Title or Author(s).")
	    return None


	queries=[]
	if idn is not None:
	    queries.append('num='+idn)

	else:
	    authors_v=[]
	    title_v=[]

	    if authors is not None:
		authors_v.append(' '.join(authors))
		authors_v.append(' '.join(self.get_author_tokens(authors,only_first_author=False)))
		authors_v.append(' '.join(self.get_author_tokens(authors,only_first_author=True)))

	    if title is not None:
		title_v.append(title)
		title_v.append(' '.join(self.get_title_tokens(title,strip_joiners=False,strip_subtitle=False)))
		title_v.append(' '.join(self.get_title_tokens(title,strip_joiners=False,strip_subtitle=True)))


	    # title and author
	    if authors is not None and title is not None:
		for a in authors_v:
		    for t in title_v:
			if isbn is not None:
			    queries.append('tit="'+t+'" AND per="'+a+'" AND num="'+isbn+'"')
			else:
			    queries.append('tit="'+t+'" AND per="'+a+'"')

		# try with author and title swapped
		if isbn is not None:
		    queries.append('per="'+title+'" AND tit="'+authors[0]+'" AND num="'+isbn+'"')
		else:
		    queries.append('per="'+title+'" AND tit="'+authors[0]+'"')


	    # title but no author
	    elif authors is not None and title is None:
		for i in authors_v:
		    if isbn is not None:
			queries.append('per="'+i+'" AND num="'+isbn+'"')
		    else:
			queries.append('per="'+i+'"')

		# try with author and title swapped
		if isbn is not None:
		    queries.append('tit="'+authors[0]+'" AND num="'+isbn+'"')
		else:
		    queries.append('tit="'+authors[0]+'"')


	    # author but no title
	    elif authors is None and title is not None:
		for i in title_v:
		    if isbn is not None:
			queries.append('tit="'+i+'" AND num="'+isbn+'"')
		    else:
			queries.append('tit="'+i+'"')

		# try with author and title swapped
		if isbn is not None:
		    queries.append('per="'+title+'" AND num="'+isbn+'"')
		else:
		    queries.append('per="'+title+'"')


	    # as last resort only use isbn
	    if isbn is not None:
		queries.append('num='+isbn)


	    # Sort queries descending by length (assumption: longer query -> less but better results)
	    #queries.sort(key=len)
	    #queries.reverse()


	# remove duplicate queries
	uniqueQueries=[]
	for i in queries:
	    if i not in uniqueQueries:
		uniqueQueries.append(i)

	# Process queries
	results = None
	for query in uniqueQueries:
	    query = query + ' AND (mat=books OR mat=serials OR mat=online)'
	    log.info(query)

	    results = self.getSearchResults(log, query, timeout)

	    if results is None:
		continue
	
	    log.info("Parsing records")
	    for record in results:
		validRecord = True

		#log.info(etree.tostring(record,pretty_print=True)
		# Title
		title = record.xpath(".//dc:title",namespaces={"dc": "http://purl.org/dc/elements/1.1/"})[0].text
		title = title.replace('[Elektronische Ressource]','')
		# Remove Autors after "/" sign
		if title.rfind(' / ')>0:
		    title = title[:title.rfind('/')]
		# Remove orginal title in square brackets from the front
		title = re.sub(r'^\[.+\] ; ','',title).strip()
		log.info("Extracted Title: %s" % title)

		# Authors
		authors = []
		for a in record.xpath(".//dc:creator",namespaces={"dc": "http://purl.org/dc/elements/1.1/"}):
		    author = a.text

		    skipAuthor =		"[gefeierte Person]","[Begr.]","[Einbandgestalter]","[Übers.]","[Übersetzer]","[Gestalter]"
		    skipRecord = 		"[Erzähler]","[Erz.]","[Spr.]","[Sprecher]"
		    removeBracket = 		"[Verfasser]","[Mitverf.]","[Mitverfasser]","[Mitwirkender]","[Bearb.]","[Verfasser einer Einleitung]","[Verfasser eines Vorworts]","[Verfasser eines Nachworts]","[Verfasser eines Geleitworts]", \
						"[Illustrator]","[Ill.]","[Designer]","[Fotograf]",\
						"[Vorr.]","[Nachr.]","[Künstler]","[Fotograf]","[sonst. bet. Person]","[Red.]","[Produzent]","[Zusammenstellender]","[Komponist]","[Hrsg.]", "[Herausgeber]"
		
		    if (author.endswith(skipAuthor)):
			continue
		    elif (author.endswith(removeBracket)):
			author = re.sub(" \[.*\]$","",author)
		    elif (author.endswith(skipRecord)):
			validRecord = False

		    # remove trailing & heading spaces
		    author = author.strip()
		    log.info("Extracted Author: %s" % author)
		    authors.append(author)
		if validRecord is not True:
		    continue

		if title is None or authors is None:
		    return None

		mi = Metadata(title, authors)

		# Optional:
		try:
		    publisher = record.xpath(".//dc:publisher",namespaces={"dc": "http://purl.org/dc/elements/1.1/"})[0].text
		    log.info("Extracted Publisher: %s" % publisher)
		    mi.publisher = publisher
		except:
		    log.info("No Publisher found")

		try:
		    year = record.xpath(".//dc:date",namespaces={"dc": "http://purl.org/dc/elements/1.1/"})[0].text
		    log.info("Extracted Year: %s" % year)
		    mi.pubdate = datetime.datetime(int(year), 1, 1)
		except:
		    log.info("No Year found")

		try:
		    languages = []
		    for l in record.xpath(".//dc:language",namespaces={"dc": "http://purl.org/dc/elements/1.1/"}):
			languages.append(l.text)
			log.info("Extraced Language: %s" % l.text)
		    mi.languages = languages
		except:
		    log.info("No Language found")

		try:
		    urn = record.xpath(".//dc:identifier[@*='tel:URN']",namespaces={"dc": "http://purl.org/dc/elements/1.1/"})[0].text
		    log.info("Extraced URN: %s" % urn)
		    mi.set_identifier('urn',urn)
		except:
		    log.info("No URN found")

		try:
		    idn = record.xpath(".//dc:identifier[@*='dnb:IDN']",namespaces={"dc": "http://purl.org/dc/elements/1.1/"})[0].text
		    log.info("Extracted DNB IDN: %s" %idn)
		    mi.set_identifier('dnb-idn',idn)
		except:
		    log.info("No IDN found")

		try:
		    isbn = record.xpath(".//dc:identifier[@*='tel:ISBN']",namespaces={"dc": "http://purl.org/dc/elements/1.1/"})[0].text
		    isbnRegex = "(?:ISBN(?:-1[03])?:? )?(?=[-0-9 ]{17}|[-0-9X ]{13}|[0-9X]{10})(?:97[89][- ]?)?[0-9]{1,5}[- ]?(?:[0-9]+[- ]?){2}[0-9X]"
		    match = re.search(isbnRegex, isbn)
		    isbn = match.group()
		    isbn = isbn.replace('-','')
		    log.info("Extracted ISBN: %s" %isbn)
		    mi.set_identifier('dnb-idn',idn)	# required for info in metadata
		    mi.isbn = isbn	# required for cover download
		except:
		    log.info("No ISBN found")

		try:
		    subjects = []
		    for s in record.xpath(".//dc:subject",namespaces={"dc": "http://purl.org/dc/elements/1.1/"}):
			subjects.append(s.text)
			log.info("Extracted Subject: %s" % s.text)
		    mi.tags = subjects
		except:
		    log.info("No Subjects found")

		# put current result's metdata into result queue
		log.info("Final formatted result: %s" % mi)
		result_queue.put(mi)

    def getSearchResults(self, log, query, timeout=30):
	log.info('Querying: %s' % query)

	# get sru token from config
	import calibre_plugins.DNB_DE.config as cfg
	dnb_token = cfg.plugin_prefs[cfg.STORE_NAME][cfg.KEY_SRUTOKEN]

	queryUrl = self.QUERYURL % (dnb_token, quote(query.encode('utf-8')))
	log.info('Querying: %s' % queryUrl)
	
	root = None
	try:
	    data = self.browser.open_novisit(queryUrl, timeout=timeout).read()
	    log.info('Got some data: %s' % data)
	    root = etree.XML(data)
	    numOfRecords = root.find('{http://www.loc.gov/zing/srw/}numberOfRecords').text
	    log.info("Got records: %s " % numOfRecords)
	    if int(numOfRecords) == 0:
		return None
	except:
	    log.info("Got no response.")
	    return None
	return root.find('{http://www.loc.gov/zing/srw/}records')

    def get_cached_cover_url(self, identifiers):
	url = None
	isbn = check_isbn(identifiers.get('isbn', None))
	if isbn is None:
	    return None
	url = self.COVERURL%isbn
	return url

    def download_cover(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30, get_best_cover=False):
	cached_url = self.get_cached_cover_url(identifiers)
	if cached_url is None:
	    log.info('No cached cover found, running identify')
	    rq = Queue()
	    self.identify(log, rq, abort, title=title, authors=authors, identifiers=identifiers)
	    if abort.is_set():
		return
		results = []
		while True:
		    try:
			results.append(rq.get_nowait())
		    except Empty:
			break
		results.sort(key=self.identify_results_keygen(title=title, authors=authors, identifiers=identifiers))
		for mi in results:
		    cached_url = self.get_cached_cover_url(mi.identifiers)
		    if cached_url is not None:
			break
		
	if cached_url is None:
	    log.info('No cover found')
	    return None
	
	if abort.is_set():
	    return
	br = self.browser
	log('Downloading cover from:', cached_url)
	try:
	    cdata = br.open_novisit(cached_url, timeout=timeout).read()
	    result_queue.put((self,cdata))
	except:
	    log.info("Could not download Cover")

if __name__ == '__main__': # tests
    # To run these test use:
    # calibre-debug -e __init__.py
    from calibre.ebooks.metadata.sources.test import (
	test_identify_plugin, title_test, authors_test, series_test)

    test_identify_plugin(DNB_DE.name, [
	(
	    {'identifiers':{'isbn': '9783404285266'}},
	    [title_test('Sehnsucht des Herzens', exact=True),
	     authors_test(['Lucas, Joanne St.'])]
	),
    ])
