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
from urllib import quote, quote_plus
from lxml import etree
from lxml.etree import tostring

from Queue import Queue, Empty

class DNB_DE(Source):
    name = 'DNB_DE'
    description = _('Downloads metadata from the DNB (Deutsche National Bibliothek). Requires a personal SRU Access Token')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Citronalco'
    version = (2, 0, 2)
    minimum_calibre_version = (0, 8, 0)

    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset(['title', 'authors', 'publisher', 'pubdate', 'languages', 'tags', 'identifier:urn', 'identifier:idn','identifier:isbn', 'identifier:ddc', 'series', 'series_index', 'comments'])
    has_html_comments = True
    can_get_multiple_covers = False
    supports_gzip_transfer_encoding = True
    cached_cover_url_is_reliable = True
    prefer_results_with_isbn = True

    QUERYURL = 'https://services.dnb.de/sru/dnb?version=1.1&accessToken=%s&maximumRecords=100&operation=searchRetrieve&recordSchema=MARC21-xml&query=%s'
    SCRAPEURL = 'https://portal.dnb.de/opac.htm?method=showFullRecord&currentResultId=%s&currentPosition=%s'
    COVERURL = 'https://portal.dnb.de/opac/mvb/cover.htm?isbn=%s'

    def load_config(self):
	# Config settings
	import calibre_plugins.DNB_DE.config as cfg
	self.cfg_guess_series = cfg.plugin_prefs[cfg.STORE_NAME].get(cfg.KEY_GUESS_SERIES,False)
	self.cfg_append_edition_to_title = cfg.plugin_prefs[cfg.STORE_NAME].get(cfg.KEY_APPEND_EDITION_TO_TITLE,False)
	self.cfg_fetch_subjects = cfg.plugin_prefs[cfg.STORE_NAME].get(cfg.KEY_FETCH_SUBJECTS,2)
	self.cfg_dnb_token = cfg.plugin_prefs[cfg.STORE_NAME].get(cfg.KEY_SRUTOKEN,None)

	if self.cfg_dnb_token == "enter-your-sru-token-here" or len(self.cfg_dnb_token)==0:
	    self.cfg_dnb_token = None

    def config_widget(self):
	self.cw = None
	from calibre_plugins.DNB_DE.config import ConfigWidget
	return ConfigWidget(self)

    def is_customizable(self):
	return True

    def identify(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30):
	self.load_config()

	# get identifying tags from book
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
	    query = query + ' NOT (mat=film OR mat=music OR mat=microfiches)'
	    log.info(query)

	    if self.cfg_dnb_token is None:
		results = self.getSearchResultsByScraping(log, query, timeout)
	    else:
		results = self.getSearchResults(log, query, timeout)

	    if results is None:
		continue

	    log.info("Parsing records")

	    ns = { 'marc21' : 'http://www.loc.gov/MARC21/slim' }
	    for record in results:
		series = None
		series_index = None
		publisher = None
		pubdate = None
		languages = []
		title = None
		title_sort = None
		edition = None
		comments = None
		idn = None
		urn = None
		isbn = None
		ddc = []
		subjects_gnd = []
		subjects_non_gnd = []


		# Title: Field 245
		title_parts = []
		# if a,n,p exist: series = a, series_index = n, title = p
		for i in record.xpath(".//marc21:datafield[@tag='245']/marc21:subfield[@code='a' and string-length(text())>0]/../marc21:subfield[@code='n' and string-length(text())>0]/../marc21:subfield[@code='p' and string-length(text())>0]/..",namespaces=ns):
		    series_index = i.xpath(".//marc21:subfield[@code='n']",namespaces=ns)[0].text.strip()
		    match = re.search("(\d+[,\.\d+]?)", series_index)
		    if match:
			series_index = match.group(1)
			series_index = series_index.replace(',','.')
			series = i.xpath(".//marc21:subfield[@code='a']",namespaces=ns)[0].text.strip()
			title_parts.append(i.xpath(".//marc21:subfield[@code='p']",namespaces=ns)[0].text.strip())
			log.info("Extracted Series: %s" % series)
			log.info("Extracted Series Index: %s" % series_index)
			break
		# otherwise: title = a
		if title is None:
		    for i in record.xpath(".//marc21:datafield[@tag='245']/marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):
			title_parts.append(i.text.strip())
			break

		# subtitle 1
		for i in record.xpath(".//marc21:datafield[@tag='245']/marc21:subfield[@code='b' and string-length(text())>0]",namespaces=ns):
		    title_parts.append(i.text.strip())
		    break
		
		# subtitle 2
		#for i in record.xpath(".//marc21:datafield[@tag='245']/marc21:subfield[@code='c' and string-length(text())>0]",namespaces=ns):
		#    title = title + " / " + i.text.strip()
		#    break
		
		title = " : ".join(title_parts)
		log.info("Extracted Title: %s" % title)


		# Title_Sort
		title_sort_parts = list(title_parts)
		title_sort_regex = re.match('^(.*?)('+chr(152)+'.*'+chr(156)+')?(.*?)$',title_parts[0])
		sortword = title_sort_regex.group(2)
		if sortword:
		    title_sort_parts[0] = ''.join(filter(None,[title_sort_regex.group(1).strip(),title_sort_regex.group(3).strip(),", "+sortword]))
		title_sort = " : ".join(title_sort_parts)
		log.info("Extracted Title_Sort: %s" % title_sort)


		# Authors
		authors = []
		author_sort = None
		for i in record.xpath(".//marc21:datafield[@tag='100']/marc21:subfield[@code='4' and text()='aut']/../marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):	# primary authors
		    name = re.sub(" \[.*\]$","",i.text.strip());
		    authors.append(name)
		for i in record.xpath(".//marc21:datafield[@tag='700']/marc21:subfield[@code='4' and text()='aut']/../marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):	# secondary authors
		    name = re.sub(" \[.*\]$","",i.text.strip());
		    authors.append(name)
		if len(authors)==0:	# if no "real" autor was found take all persons involved
		    for i in record.xpath(".//marc21:datafield[@tag='700']/marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):	# secondary authors
			name = re.sub(" \[.*\]$","",i.text.strip());
			authors.append(name)
		if len(authors)>0:
		    author_sort = authors[0]
		log.info("Extracted Authors: %s" % " & ".join(authors))


		# Comments
		for i in record.xpath(".//marc21:datafield[@tag='856']/marc21:subfield[@code='u' and string-length(text())>0]",namespaces=ns):
		    if i.text.startswith("http://deposit.dnb.de/"):
			br = self.browser
			log.info('Downloading Comments from: %s' % i.text)
			try:
			    comments = br.open_novisit(i.text, timeout=30).read()
			    comments = sanitize_comments_html(comments)
			    log.info('Comments: %s' % comments)
			    break
			except:
			    log.info("Could not download Comments from %s" % i)


		# Publisher Name and Location
		publisher_name = None
		publisher_location = None
		fields = record.xpath(".//marc21:datafield[@tag='264']/marc21:subfield[@code='b' and string-length(text())>0]/../marc21:subfield[@code='a' and string-length(text())>0]/..",namespaces=ns)
		if len(fields)>0:
		    publisher_name = fields[0].xpath(".//marc21:subfield[@code='b' and string-length(text())>0]",namespaces=ns)[0].text.strip();
		    publisher_location = fields[0].xpath(".//marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns)[0].text.strip();
		else:
		    fields = record.xpath(".//marc21:datafield[@tag='264']/marc21:subfield[@code='b' and string-length(text())>0]/../..",namespaces=ns)
		    if len(fields)>0:
			publisher_name = fields[0].xpath(".//marc21:subfield[@code='b' and string-length(text())>0]",namespaces=ns)[0].text.strip();
		    else:
			fields = record.xpath(".//marc21:datafield[@tag='264']/marc21:subfield[@code='a' and string-length(text())>0]/../..",namespaces=ns)
			if len(fields)>0:
			    publisher_location = fields[0].xpath(".//marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns)[0].text.strip();

		log.info("Extracted Publisher: %s" % publisher_name)
		log.info("Extracted Publisher Location: %s" % publisher_location)
		publisher = " : ".join(filter(None,[publisher_location, publisher_name]))


		# Publishing Date
		for i in record.xpath(".//marc21:datafield[@tag='264']/marc21:subfield[@code='c' and string-length(text())>=4]",namespaces=ns):
		    match = re.search("(\d{4})", i.text.strip())
		    year = match.group(1)
		    pubdate = datetime.datetime(int(year), 1, 2)
		    break
		log.info("Extracted Publication Year: %s" % year)


		# ID: IDN
		for i in record.xpath(".//marc21:datafield[@tag='016']/marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):
		    idn = i.text.strip()
		    break
		log.info("Extracted ID IDN: %s" % idn)


		# ID: URN
		for i in record.xpath(".//marc21:datafield[@tag='024']/marc21:subfield[@code='2' and text()='urn']/../marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):
		    urn = i.text.strip()
		    break
		log.info("Extracted ID URN: %s" % urn)


		# ID: ISBN
		for i in record.xpath(".//marc21:datafield[@tag='020']/marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):
		    isbn_regex = "(?:ISBN(?:-1[03])?:? )?(?=[-0-9 ]{17}|[-0-9X ]{13}|[0-9X]{10})(?:97[89][- ]?)?[0-9]{1,5}[- ]?(?:[0-9]+[- ]?){2}[0-9X]"
		    match = re.search(isbn_regex, i.text.strip())
		    isbn = match.group()
		    isbn = isbn.replace('-','')
		    break
		log.info("Extracted ID ISBN: %s" % isbn)


		# ID: Sachgruppe (DDC)
		for i in record.xpath(".//marc21:datafield[@tag='082']/marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):
		    ddc.append(i.text.strip())
		log.info("Extracted ID DDC: %s" % ",".join(ddc))


		# Series and Series_Index
		if series is None and series_index is None:
		    for i in record.xpath(".//marc21:datafield[@tag='830']/marc21:subfield[@code='v' and string-length(text())>0]/../marc21:subfield[@code='a' and string-length(text())>0]/..",namespaces=ns):
			# Series
			series = i.xpath(".//marc21:subfield[@code='a']",namespaces=ns)[0].text.strip()
			log.info("Extracted Series: %s" % series)
			# Series Index
			series_index = i.xpath(".//marc21:subfield[@code='v']",namespaces=ns)[0].text.strip()
			match = re.search("(\d+[,\.\d+]?)", series_index)
			series_index = match.group(1)
			series_index = series_index.replace(',','.')
			log.info("Extracted Series Index: %s" % series_index)
			break


		# Try to extract Series, Series Index and Title from the fetched title.
		# Caution: Also modifies the title!
		if series is None and series_index is None and title is not None and self.cfg_guess_series is True:
		    parts = re.split("[:]",self.removeSortingCharacters(title))
		    if len(parts)==2:
			if bool(re.search("\d",parts[0])) != bool(re.search("\d",parts[1])):
			    # figure out which part contains the index
			    if bool(re.search("\d",parts[0])):
				indexpart = parts[0]
				textpart = parts[1]
			    else:
				indexpart = parts[1]
				textpart = parts[0]

			    match = re.match("^[\s\-–:]*(.+?)[\s\-–:]*$",textpart)	# remove odd characters from start and end of the text part
			    if match:
				textpart = match.group(1)

			    # from Titles like: "Name of the series - Episode 2"
			    match = re.match("^\s*(\S.*?)??[\/\.,\s\-–:]*(?:Nr\.|Episode|Bd\.|Sammelband|[B|b]and|Part|Teil|Folge)?[,\-–:\s#\(]*(\d+\.?\d*)[\)\s\-–:]*$",indexpart)
			    if match:
				series_index = match.group(2)
				series = match.group(1)
				if series is None:
				    series = textpart
				    title = textpart + " : Band " + series_index
				else:
				    title = textpart
			    else:
				# from Titles like: "Episode 2 Name of the series"
				match = re.match("^\s*(?:Nr\.|Episode|Bd\.|Sammelband|[B|b]and|Part|Teil|Folge)[,\-–:\s#\(]*(\d+\.?\d*)[\)\s\-–:]*(\S.*?)??[\/\.,\-–\s]*$",indexpart)
				if match:
				    series_index = match.group(1)
				    series = match.group(2)
				    if series is None:
					series = textpart
					title = textpart + " : Band " + series_index
				    else:
					title = textpart
		    elif len(parts)==1:
			# from Titles like: "Name of the series - Episode 2"
			match = re.match("^\s*(\S.+?)??[\/\.,\s\-–:]*(?:Nr\.|Episode|Bd\.|Sammelband|[B|b]and|Part|Teil|Folge)?[,\-–:\s#\(]*(\d+\.?\d*)[\)\s\-–:]*$",parts[0])
			if match:
			    series_index = match.group(2)
			    series = match.group(1)
			    title = series + " : Band " + series_index

		    if series is not None and series_index is not None:
			log.info("Guessed Series: %s" % series)
			log.info("Guessed Series Index: %s" % series_index)


		# GND Subjects from 689
		for i in record.xpath(".//marc21:datafield[@tag='689']/marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):
		    subjects_gnd.append(i.text.strip())
		# GND Subjects from 600-655
		for f in range(600,656):
		    for i in record.xpath(".//marc21:datafield[@tag='"+str(f)+"']/marc21:subfield[@code='2' and text()='gnd']/../marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):
			if i.text.startswith("("):
			    continue
			subjects_gnd.append(i.text)
		log.info("Extracted GND Subjects: %s" % " ".join(subjects_gnd))


		# Non-GND subjects from 600-655
		for f in range(600,656):
		    for i in record.xpath(".//marc21:datafield[@tag='"+str(f)+"']/marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):
			# ignore entries starting with "(":
			if i.text.startswith("("):
			    continue
			subjects_non_gnd.extend(re.split(',|;',i.text))
		# remove one-character subjects:
		for i in subjects_non_gnd:
		    if len(i)<2:
			subjects_non_gnd.remove(i)
		log.info("Extracted non-GND Subjects: %s" % " ".join(subjects_non_gnd))


		# Edition
		for i in record.xpath(".//marc21:datafield[@tag='250']/marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):
		    edition = i.text.strip()
		    break
		log.info("Extracted Edition: %s" % edition)


		# Languages
		for i in record.xpath(".//marc21:datafield[@tag='041']/marc21:subfield[@code='a' and string-length(text())>0]",namespaces=ns):
		    languages.append(i.text.strip())
		if languages is not None:
		    log.info("Extracted Languages: %s" % ",".join(languages))


		# Put it all together
		if self.cfg_append_edition_to_title == True and edition is not None:
		    title = title + " : " + edition

		mi = Metadata(self.removeSortingCharacters(title), map(lambda i: self.removeSortingCharacters(i), authors))
		mi.title_sort = self.removeSortingCharacters(title_sort)
		mi.author_sort = self.removeSortingCharacters(author_sort)
		mi.languages = languages
		mi.pubdate = pubdate
		mi.series = self.removeSortingCharacters(series)
		mi.series_index = series_index
		mi.comments = comments
		mi.isbn = isbn # also required for cover download
		mi.set_identifier('urn',urn)
		mi.set_identifier('dnb-idn',idn)
		mi.set_identifier('ddc', ",".join(ddc))

		if self.cfg_fetch_subjects == 0:
		    mi.tags = self.uniq(subjects_gnd)
		elif self.cfg_fetch_subjects == 1:
		    if len(subjects_gnd)>0:
			mi.tags = self.uniq(subjects_gnd)
		    else:
			mi.tags = self.uniq(subjects_non_gnd)
		elif self.cfg_fetch_subjects == 2:
		    mi.tags = self.uniq(subjects_gnd + subjects_non_gnd)
		elif self.cfg_fetch_subjects == 3:
		    if len(subjects_non_gnd)>0:
			mi.tags = self.uniq(subjects_non_gnd)
		    else:
			mi.tags = self.uniq(subjects_gnd)
		elif self.cfg_fetch_subjects == 4:
		    mi.tags = self.uniq(subjects_non_gnd)
		elif self.cfg_fetch_subjects == 5:
		    mi.tags = []

		# put current result's metdata into result queue
		log.info("Final formatted result: %s" % mi)
		result_queue.put(mi)

    def removeSortingCharacters(self, text):
	if text is not None:
	    return ''.join([c for c in text if ord(c)!=152 and ord(c)!=156])	# remove sorting word markers
	else:
	    return None

    def uniq(self, listWithDuplicates):
	uniqueList = []
	if len(listWithDuplicates)>0:
	    for i in listWithDuplicates:
		if i not in uniqueList:
		    uniqueList.append(i)
	return uniqueList

    def getSearchResults(self, log, query, timeout=30):
	log.info('Querying: %s' % query)

	queryUrl = self.QUERYURL % (self.cfg_dnb_token, quote(query.encode('utf-8')))
	log.info('Query URL: %s' % queryUrl)
	
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

    def getSearchResultsByScraping(self, log, query, timeout=30):
	log.info('Querying: %s' % query)

	m21records = []
	resultNum = 0
	while True:
	    if resultNum > 99:
		break
	    queryUrl = self.SCRAPEURL % (quote_plus(query+"&any"), str(resultNum))
	    log.info('Query URL: %s' % queryUrl)
	    try:
		webpage = self.browser.open_novisit(queryUrl, timeout=timeout).read()
		webroot = etree.HTML(webpage)
		if len(webroot.xpath(".//p[text()='Datensatz kann nicht angezeigt werden.']"))>0:
		    break

		marc21link = webroot.xpath(u".//a[text()='MARC21-XML-Repräsentation dieses Datensatzes']/@href")[0]
		log.info("Found link to MARC21-XML: %s " % marc21link)

		m21data = self.browser.open_novisit(marc21link, timeout=timeout).read()
		m21records.append(etree.XML(m21data));
		resultNum += 1
	    except:
		log.info("Got no response.")
		resultNum += 1

	log.info("Got records: %s " % len(m21records))

	return m21records

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
