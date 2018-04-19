#!/usr/bin/env python2
# -*- coding: utf-8 -*-

__license__ = 'GPL v3'
__copyright__ = '2017, Bernhard Geier <geierb@geierb.de>'
__docformat__ = 'en'

from calibre.ebooks.metadata.sources.base import Source
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.book.base import Metadata
from calibre.library.comments import sanitize_comments_html

import re, datetime
from urllib import quote
from lxml import etree
from lxml.etree import tostring

from Queue import Queue, Empty

class DNB_DE(Source):
    name = 'DNB_DE'
    description = _('Downloads metadata from the DNB (Deutsche National Bibliothek). Requires a personal SRU Access Token')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Citronalco'
    version = (2, 0, 0)
    minimum_calibre_version = (0, 8, 0)

    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset(['title', 'authors', 'publisher', 'pubdate', 'languages', 'tags', 'identifier:urn', 'identifier:idn','identifier:isbn', 'identifier:ddc', 'series', 'series_index', 'comments'])
    has_html_comments = True
    can_get_multiple_covers = False
    supports_gzip_transfer_encoding = True
    cached_cover_url_is_reliable = True
    prefer_results_with_isbn = True

    QUERYURL = 'https://services.dnb.de/sru/dnb?version=1.1&accessToken=%s&maximumRecords=100&operation=searchRetrieve&recordSchema=MARC21-xml&query=%s'
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

	    ns = { 'marc21' : 'http://www.loc.gov/MARC21/slim' }
	    for record in results:
		#log.info(etree.tostring(record,pretty_print=True))

		# Title
		title = None
		for i in record.xpath(".//marc21:datafield[@tag='245']/marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):	# main title
		    title = i.text.strip()
		    break;
		for i in record.xpath(".//marc21:datafield[@tag='245']/marc21:subfield[@code='b' and string-length(text())>0]",namespaces=ns):	# subtitle 1
		    title = title + " : " + i.text.strip()
		    break
		for i in record.xpath(".//marc21:datafield[@tag='245']/marc21:subfield[@code='n' and string-length(text())>0]",namespaces=ns):	# subtitle 1
		    title = title + " : " + i.text.strip()
		    break
		#for i in record.xpath(".//marc21:datafield[@tag='245']/marc21:subfield[@code='c' and string-length(text())>0]",namespaces=ns):	# subtitle 2
		#    title = title + " / " + i.text.strip()
		#    break

		title_sort = None
		title_sort_regex = re.match('^(.*?)('+chr(152)+'.*'+chr(156)+')?(.*?)$',title)
		sortword = title_sort_regex.group(2)
		if sortword:
		    sortword = ''.join([c for c in sortword if ord(c)!=152 and ord(c)!=156])	# remove sorting word markers
		    title_sort = ''.join(filter(None,[title_sort_regex.group(1).strip(),title_sort_regex.group(3).strip(),", "+sortword]))
		    log.info("Extracted Title_Sort: %s" % title_sort)

		title=''.join([c for c in title if ord(c)!=152 and ord(c)!=156])	# remove sorting word markers
		log.info("Extracted Title: %s" % title)

		# Authors
		authors = []
		author_sort = None
		for i in record.xpath(".//marc21:datafield[@tag='100']/marc21:subfield[@code='4' and text()='aut']/../marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):	# primary authors
		    if author_sort is None:
			author_sort = i.text.strip();
		    authors.append(i.text.strip())
		for i in record.xpath(".//marc21:datafield[@tag='700']/marc21:subfield[@code='4' and text()='aut']/../marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):	# secondary authors
		    authors.append(i.text.strip())
		log.info("Extracted Authors: %s" % " & ".join(authors))

		mi = Metadata(title, authors)
		mi.title_sort = title_sort
		mi.author_sort = author_sort

		# Comments
		comments = None
		for i in record.xpath(".//marc21:datafield[@tag='856']/marc21:subfield[@code='u' and string-length(text())>0]",namespaces=ns):
		    if i.text.startswith("http://deposit.dnb.de/"):
			br = self.browser
			log.info('Downloading Comments from: %s' % i.text)
			try:
			    comments = br.open_novisit(i.text, timeout=30).read()
			    comments = sanitize_comments_html(comments)
			    log.info('Comments: %s' % comments)
			    mi.comments = comments
			    break
			except:
			    log.info("Could not download Comments from %s" % i)

		# Publisher Name and Location
		publisher = None
		for i in record.xpath(".//marc21:datafield[@tag='264']/marc21:subfield[@code='b' and string-length(text())>0]",namespaces=ns):
		    publisher = i.text.strip()
		    log.info("Extracted Publisher: %s" % publisher)
		    for i in record.xpath(".//marc21:datafield[@tag='264']/marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):
			publisher_location = i.text.strip()
			log.info("Extracted Publisher Location: %s" % publisher_location)
			publisher = publisher + " : " + publisher_location
			break
		    mi.publisher = publisher
		    break

		# Publishing Date
		pubdate = None
		for i in record.xpath(".//marc21:datafield[@tag='264']/marc21:subfield[@code='c' and string-length(text())>=4]",namespaces=ns):
		    match = re.search("(\d{4})", i.text.strip())
		    year = match.group()
		    log.info("Extracted Year: %s" % year)
		    mi.pubdate = datetime.datetime(int(year), 1, 2)
		    break

		# ID: IDN
		idn = None
		for i in record.xpath(".//marc21:datafield[@tag='016']/marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):
		    idn = i.text.strip()
		    log.info("Extracted ID IDN: %s" % idn)
		    mi.set_identifier('dnb-idn',idn)
		    break

		# ID: URN
		urn = None
		for i in record.xpath(".//marc21:datafield[@tag='024']/marc21:subfield[@code='2' and text()='urn']/../marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):
		    urn = i.text.strip()
		    log.info("Extracted ID URN: %s" % urn)
		    mi.set_identifier('urn',urn)
		    break

		# ID: ISBN
		isbn = None
		for i in record.xpath(".//marc21:datafield[@tag='020']/marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):
		    isbn = i.text.strip()
		    isbn_regex = "(?:ISBN(?:-1[03])?:? )?(?=[-0-9 ]{17}|[-0-9X ]{13}|[0-9X]{10})(?:97[89][- ]?)?[0-9]{1,5}[- ]?(?:[0-9]+[- ]?){2}[0-9X]"
		    match = re.search(isbn_regex, isbn)
		    isbn = match.group()
		    isbn = isbn.replace('-','')
		    log.info("Extracted ID ISBN: %s" % isbn)
		    mi.isbn = isbn # also required for cover download
		    break

		# ID: Sachgruppe (DDC)
		ddc = []
		for i in record.xpath(".//marc21:datafield[@tag='082']/marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):
		    ddc.append(i.text.strip())
		if ddc is not None:
		    log.info("Extracted ID DDC: %s" % ",".join(ddc))
		    mi.set_identifier('ddc', ",".join(ddc))

		# Series - 490 or 830?
		series = None
		series_index = None
		for i in record.xpath(".//marc21:datafield[@tag='830']/marc21:subfield[@code='v' and string-length(text())>0]/../marc21:subfield[@code='a' and string-length(text())>0]/..",namespaces=ns):
		    # Series
		    series = i.xpath(".//marc21:subfield[@code='a']",namespaces=ns)[0].text.strip()
		    series = ''.join([c for c in series if ord(c)!=152 and ord(c)!=156])	# remove sorting word markers
		    log.info("Extracted Series: %s" % series)
		    mi.series = series
		    # Series Index
		    series_index = i.xpath(".//marc21:subfield[@code='v']",namespaces=ns)[0].text.strip()
		    match = re.search("(\d+[,\.\d+]?)", series_index)
		    series_index = match.group()
		    series_index = series_index.replace(',','.')
		    log.info("Extracted Series Index: %s" % series_index)
		    mi.series_index = series_index
		    break

		# Subjects
		subjects = []
		for i in record.xpath(".//marc21:datafield[@tag='689']/marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):
		    subjects.append(i.text.strip())
		for i in record.xpath(".//marc21:datafield[@tag='653']/marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):
		    if i.text.startswith("("):
			continue
		    subjects.extend(i.text.split(','))
		if subjects is not None:
		    log.info("Extracted Subjects: %s" % " ".join(subjects))
		    mi.tags = subjects

		# Language
		languages = []
		for i in record.xpath(".//marc21:datafield[@tag='041']/marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):
		    languages.append(i.text.strip())
		if languages is not None:
		    log.info("Extracted Languages: %s" % ",".join(languages))
		    mi.languages = languages


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
	    #log.info('Got some data: %s' % data)
	    root = etree.XML(data)

	    numOfRecords = root.find('{http://www.loc.gov/zing/srw/}numberOfRecords').text
	    log.info("Got records: %s " % numOfRecords)
	    if int(numOfRecords) == 0:
		return None
	except:
	    log.info("Got no response.")
	    return None

	return root.xpath(".//marc21:record",namespaces={"marc21": "http://www.loc.gov/MARC21/slim"});

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
