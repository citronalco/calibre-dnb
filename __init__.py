#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

__license__ = 'GPL v3'
__copyright__ = '2018, Bernhard Geier <geierb@geierb.de>'
__docformat__ = 'en'

from calibre.ebooks.metadata.sources.base import Source
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.book.base import Metadata
from calibre.library.comments import sanitize_comments_html
from calibre import as_unicode

import re
import datetime

try:
    from urllib import quote, quote_plus # Python2
except ImportError:
    from urllib.parse import quote, quote_plus # Python3

from lxml import etree
from lxml.etree import tostring

try:
    from Queue import Queue, Empty # Python2
except ImportError:
    from queue import Queue, Empty # Python3


class DNB_DE(Source):
    name = 'DNB_DE'
    description = _(
        'Downloads metadata from the DNB (Deutsche National Bibliothek).')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Citronalco'
    version = (3, 0, 0)
    minimum_calibre_version = (0, 8, 0)

    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset(['title', 'authors', 'publisher', 'pubdate', 'languages', 'tags', 'identifier:urn',
                                'identifier:idn', 'identifier:isbn', 'identifier:ddc', 'series', 'series_index', 'comments'])
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
        self.cfg_guess_series = cfg.plugin_prefs[cfg.STORE_NAME].get(
            cfg.KEY_GUESS_SERIES, False)
        self.cfg_append_edition_to_title = cfg.plugin_prefs[cfg.STORE_NAME].get(
            cfg.KEY_APPEND_EDITION_TO_TITLE, False)
        self.cfg_fetch_subjects = cfg.plugin_prefs[cfg.STORE_NAME].get(
            cfg.KEY_FETCH_SUBJECTS, 2)
        self.cfg_dnb_token = cfg.plugin_prefs[cfg.STORE_NAME].get(
            cfg.KEY_SRUTOKEN, None)

        if self.cfg_dnb_token == "enter-your-sru-token-here" or len(self.cfg_dnb_token) == 0:
            self.cfg_dnb_token = None

    def config_widget(self):
        self.cw = None
        from calibre_plugins.DNB_DE.config import ConfigWidget
        return ConfigWidget(self)

    def is_customizable(self):
        return True

    def identify(self, log, result_queue, abort, title=None, authors=[], identifiers={}, timeout=30):
        self.load_config()

        if authors is None:
            authors = []

        # get identifying tags from book
        idn = identifiers.get('dnb-idn', None)
        isbn = check_isbn(identifiers.get('isbn', None))

        # ignore unknown authors
        ignored_authors = ["V. A.", "V.A.", "Unknown", "Unbekannt"]
        for i in ignored_authors:
            authors = [x for x in authors if x != i]

        if (isbn is None) and (idn is None) and (title is None) and (authors is None):
            log.info(
                "This plugin requires at least either ISBN, IDN, Title or Author(s).")
            return None

        queries = []
        # DNB does not do an exact search when searching for a idn or isbn, so we have to filter the results
        exact_search = {}

        if idn is not None:
            exact_search['idn'] = idn
            # in case look for a IDN only search for the IDN and skip all the other stuff
            queries.append('num='+idn)

        else:
            authors_v = []
            title_v = []

            #authors = []
            #title = None
            #isbn = None
            #title = re.sub('^(Der|Die|Das|Ein|Eine) ', '', title)


            # create some variants of given authors
            if authors != []:
                # concat all author names ("Peter Meier Luise Stark")
                authors_v.append(' '.join(self.get_author_tokens(
                    authors, only_first_author=False)))
                authors_v.append(' '.join(self.get_author_tokens(
                    authors, only_first_author=True)))  # use only first author
                for a in authors:
                    authors_v.append(a)  # use all authors, one by one

                # remove duplicates
                unique_authors_v = []
                for i in authors_v:
                    if i not in unique_authors_v:
                        unique_authors_v.append(i)

            # create some variants of given title
            if title is not None:
                title_v.append(title)  # simply use given title
                title_v.append(' '.join(self.get_title_tokens(
                    title, strip_joiners=False, strip_subtitle=False)))  # remove some punctation characters
                # remove subtitle (everything after " : ")
                title_v.append(' '.join(self.get_title_tokens(
                    title, strip_joiners=False, strip_subtitle=True)))
                # remove some punctation characters and joiners ("and", "&", ...)
                title_v.append(' '.join(self.get_title_tokens(
                    title, strip_joiners=True, strip_subtitle=False)))
                # remove subtitle (everything after " : ") and joiners ("and", "&", ...)
                title_v.append(' '.join(self.get_title_tokens(
                    title, strip_joiners=True, strip_subtitle=True)))

                # TODO: remove subtitle after " - "

                ## TEST: remove text in braces at the end of title (if present)
                #match = re.search("^(.+?)[\s*]\(.+\)$", title)
                #if match is not None:
                #    title_v.append(' '.join(self.get_title_tokens(
                #        match.group(1), strip_joiners=True, strip_subtitle=True)))

                ## TEST: search for title parts before and after colon (if present)
                #match = re.search("^(.+)\s*[\-:]\s(.+)$", title)
                #if match is not None:
                #    title_v=[]
                #    title_v.append(' '.join(self.get_title_tokens(match.group(2),strip_joiners=True,strip_subtitle=True)))
                #    title_v.append(' '.join(self.get_title_tokens(match.group(1),strip_joiners=True,strip_subtitle=True)))

                # remove duplicates
                unique_title_v = []
                for i in title_v:
                    if i not in unique_title_v:
                        unique_title_v.append(i)

            # title and author
            if authors_v != [] and title_v != []:
                for a in authors_v:
                    for t in title_v:
                        if isbn is not None:
                            queries.append(
                                'tit="' + t + '" AND per="' + a + '" AND num="' + isbn + '"')
                        else:
                            queries.append(
                                'tit="' + t + '" AND per="' + a + '"')

                # try with first author as title and title (without subtitle) as author
                if isbn is not None:
                    queries.append('per="' + ' '.join(self.get_title_tokens(title, strip_joiners=True, strip_subtitle=True)) +
                                   '" AND tit="' + ' '.join(self.get_author_tokens(authors, only_first_author=True)) + '" AND num="'+isbn+'"')
                else:
                    queries.append('per="' + ' '.join(self.get_title_tokens(title, strip_joiners=True, strip_subtitle=True)
                                                      ) + '" AND tit="' + ' '.join(self.get_author_tokens(authors, only_first_author=True)) + '"')

                # try with author and title (without subtitle) in any index
                if isbn is not None:
                    queries.append('"' + ' '.join(self.get_title_tokens(title, strip_joiners=True, strip_subtitle=True)) +
                                   '" AND "' + ' '.join(self.get_author_tokens(authors, only_first_author=True)) + '" AND num="'+isbn+'"')
                else:
                    queries.append('"' + ' '.join(self.get_title_tokens(title, strip_joiners=True, strip_subtitle=True)
                                                  ) + '" AND "' + ' '.join(self.get_author_tokens(authors, only_first_author=True)) + '"')

            # author but no title
            elif authors_v != [] and title_v == []:
                for i in authors_v:
                    if isbn is not None:
                        queries.append(
                            'per="' + i + '" AND num="' + isbn + '"')
                    else:
                        queries.append('per="' + i + '"')

                # try with author as title
                if isbn is not None:
                    queries.append('tit="' + ' '.join(self.get_author_tokens(authors,
                                                                             only_first_author=True)) + '" AND num="' + isbn + '"')
                else:
                    queries.append(
                        'tit="' + ' '.join(self.get_author_tokens(authors, only_first_author=True)) + '"')

            # title but no author
            elif authors_v == [] and title_v != []:
                for i in title_v:
                    if isbn is not None:
                        queries.append(
                            'tit="' + i + '" AND num="' + isbn + '"')
                    else:
                        queries.append('tit="' + i + '"')

                # try with title as author
                if isbn is not None:
                    queries.append('per="' + ' '.join(self.get_title_tokens(
                        title, strip_joiners=True, strip_subtitle=True)) + '" AND num="' + isbn + '"')
                else:
                    queries.append('per="' + ' '.join(self.get_title_tokens(title, strip_joiners=True, strip_subtitle=True)) + '"')

            ## TEST: Search anything anywhere - except ISBN
            #p=[]
            #if title is not None:
            #    p.append('"' + ' '.join(self.get_title_tokens(title,strip_joiners=True,strip_subtitle=True)) + '"')
            #if authors != []:
            #    p.append('"' + ' '.join(self.get_author_tokens(authors,only_first_author=True)) + '"')
            #q=' AND '.join(p)
            #queries.append(q)

            # as last resort only use ISBN
            if isbn is not None:
                queries.append('num=' + isbn)

        # remove duplicate queries
        uniqueQueries = []
        for i in queries:
            if i not in uniqueQueries:
                uniqueQueries.append(i)

        # Process queries
        results = None

        for query in uniqueQueries:
            # SRU does not work with "+" or "?" characters in query, so we simply remove them
            query = re.sub('[\+\?]', '', query)

            query = query + \
                ' NOT (mat=film OR mat=music OR mat=microfiches OR cod=tt)'
            log.info(query)

            if self.cfg_dnb_token is None:
                results = self.getSearchResultsByScraping(log, query, timeout)
            else:
                results = self.getSearchResults(log, query, timeout)

            if results is None:
                continue

            log.info("Parsing records")

            ns = {'marc21': 'http://www.loc.gov/MARC21/slim'}

            for record in results:
                series = None
                series_index = None
                publisher = None
                pubdate = None
                languages = []
                title = None
                title_sort = None
                authors = []
                author_sort = None
                edition = None
                comments = None
                idn = None
                urn = None
                isbn = None
                ddc = []
                subjects_gnd = []
                subjects_non_gnd = []
                publisher_name = None
                publisher_location = None

                ##### Field 264 #####
                # Publisher Name and Location
                fields = record.xpath(
                    "./marc21:datafield[@tag='264']/marc21:subfield[@code='b' and string-length(text())>0]/../marc21:subfield[@code='a' and string-length(text())>0]/..", namespaces=ns)
                if len(fields) > 0:
                    publisher_name = fields[0].xpath(
                        "./marc21:subfield[@code='b' and string-length(text())>0]", namespaces=ns)[0].text.strip()
                    publisher_location = fields[0].xpath(
                        "./marc21:subfield[@code='a' and string-length(text())>0]", namespaces=ns)[0].text.strip()
                else:
                    fields = record.xpath(
                        "./marc21:datafield[@tag='264']/marc21:subfield[@code='b' and string-length(text())>0]/../..", namespaces=ns)
                    if len(fields) > 0:
                        publisher_name = fields[0].xpath(
                            "./marc21:subfield[@code='b' and string-length(text())>0]", namespaces=ns)[0].text.strip()
                    else:
                        fields = record.xpath(
                            "./marc21:datafield[@tag='264']/marc21:subfield[@code='a' and string-length(text())>0]/../..", namespaces=ns)
                        if len(fields) > 0:
                            publisher_location = fields[0].xpath(
                                "./marc21:subfield[@code='a' and string-length(text())>0]", namespaces=ns)[0].text.strip()

                # Publishing Date
                for i in record.xpath("./marc21:datafield[@tag='264']/marc21:subfield[@code='c' and string-length(text())>=4]", namespaces=ns):
                    match = re.search("(\d{4})", i.text.strip())
                    if match is not None:
                        year = match.group(1)
                        pubdate = datetime.datetime(int(year), 1, 1, 12, 30, 0)
                        break

                # Log
                if publisher_name is not None:
                    log.info("Extracted Publisher: %s" % publisher_name)
                if publisher_location is not None:
                    log.info("Extracted Publisher Location: %s" %
                             publisher_location)
                if pubdate is not None:
                    log.info("Extracted Publication Year: %s" % pubdate)

                ##### Field 245 ####
                # a = title, n = number of part, p = name of part - ok
                # Title/Series/Series_Index
                title_parts = []
                for i in record.xpath("./marc21:datafield[@tag='245']/marc21:subfield[@code='a' and string-length(text())>0]/..", namespaces=ns):
                    code_a = []
                    code_n = []
                    code_p = []

                    # a
                    for j in i.xpath("./marc21:subfield[@code='a']", namespaces=ns):
                        code_a.append(j.text.strip())

                    # n
                    for j in i.xpath("./marc21:subfield[@code='n']", namespaces=ns):
                        match = re.search("(\d+([,\.]\d+)?)", j.text.strip())
                        if match:
                            code_n.append(match.group(1))
                        else:
                            # looks like sometimes DNB does not know the series index and uses something like "[...]"
                            code_n.append("0")

                    # p
                    for j in i.xpath("./marc21:subfield[@code='p']", namespaces=ns):
                        code_p.append(j.text.strip())

                    # Title
                    title_parts = code_a

                    # Series?
                    if len(code_a) > 0 and len(code_n) > 0:
                        # a = "The Endless Book", n[0] = 2, p[0] = "Second Season", n[1] = 3, p[1] = "Summertime", n[2] = 4, p[2] = "The Return of Foobar"	Example: dnb-id 1008774839
                        # ->	Title: 	"The Endless Book 2 - Second Season 3 - Summertime 4 - The Return Of Foobar"
                        #	Series:	"The Endless Book 2 - Second Season 3 - Summertime"
                        #	Index:	4

                        # a = "The Endless Book", n[0] = 2, p[0] = "Second Season", n[1] = 3, p[1] = "Summertime", n[2] = 4"
                        # ->	Title: 	"The Endless Book 2 - Second Season 3 - Summertime 4"
                        #	Series:	"The Endless Book 2 - Second Season 3 - Summertime"
                        #	Index:	4

                        # a = "The Endless Book", n[0] = 2, p[0] = "Second Season", n[1] = 3, p[1] = "Summertime"
                        # ->	Title: 	"The Endless Book 2 - Second Season 3 - Summertime"	n=2, p=2
                        #	Series:	"The Endless Book 2 - Second Season"
                        #	Index:	3

                        # a = "The Endless Book", n[0] = 2, p[0] = "Second Season", n[1] = 3"	Example: 956375146
                        # ->	Title: 	"The Endless Book 2 - Second Season 3"	n=2, p =1
                        #	Series:	"The Endless Book 2 - Second Season"
                        #	Index:	3

                        # a = "The Endless Book", n[0] = 2, p[0] = "Second Season"
                        # ->	Title: 	"The Endless Book 2 - Second Season"	n=1,p=1
                        #	Series:	"The Endless Book"
                        #	Index:	2

                        # a = "The Endless Book", n[0] = 2"	n=1, p=0
                        # ->	Title: 	"The Endless Book 2"
                        #	Series:	"The Endless Book"
                        #	Index:	2

                        # build title ("Name-of-Series 123 - Name of this Book")
                        # for i in range(0,max(len(code_n),len(code_p))):
                        #    if i<len(code_n):
                        #	title_parts[0] += ' ' + code_n[i]
                        #    if i<len(code_p):
                        #	title_parts[0] += ' - ' + code_p[i]

                        # alt: build title ("Name of this Book")
                        if len(code_p) > 0:
                            title_parts = [code_p[-1]]

                        # build series name
                        series_parts = [code_a[0]]
                        for i in range(0, min(len(code_p), len(code_n))-1):
                            series_parts.append(code_p[i])

                        if len(series_parts) > 1:
                            for i in range(0, min(len(series_parts), len(code_n)-1)):
                                series_parts[i] += ' ' + code_n[i]

                        series = ' - '.join(series_parts)

                        # build series index
                        series_index = 0
                        if len(code_n) > 0:
                            series_index = code_n[-1]

                # subtitle 1: Field 245, b
                for i in record.xpath("./marc21:datafield[@tag='245']/marc21:subfield[@code='b' and string-length(text())>0]", namespaces=ns):
                    title_parts.append(i.text.strip())
                    break

                # subtitle 2
                # for i in record.xpath("./marc21:datafield[@tag='245']/marc21:subfield[@code='c' and string-length(text())>0]",namespaces=ns):
                #    title = title + " / " + i.text.strip()
                #    break

                title = " : ".join(title_parts)

                # Log
                if series_index is not None:
                    log.info("Extracted Series_Index from Field 245: %s" %
                             series_index)
                if series is not None:
                    log.info("Extracted Series from Field 245: %s" % series)
                    series = self.cleanUpSeries(log, series, publisher_name)
                if title is not None:
                    log.info("Extracted Title: %s" % title)
                    title = self.cleanUpTitle(log, title)

                # Title_Sort
                if len(title_parts) > 0:
                    title_sort_parts = list(title_parts)

                    try:	# Python2
                        title_sort_regex = re.match('^(.*?)('+unichr(152)+'.*'+unichr(156)+')?(.*?)$', title_parts[0])
                    except:	# Python3
                        title_sort_regex = re.match('^(.*?)('+chr(152)+'.*'+chr(156)+')?(.*?)$', title_parts[0])
                    sortword = title_sort_regex.group(2)
                    if sortword:
                        title_sort_parts[0] = ''.join(filter(None, [title_sort_regex.group(1).strip(), title_sort_regex.group(3).strip(), ", "+sortword]))
                    title_sort = " : ".join(title_sort_parts)

                # Log
                if title_sort is not None:
                    log.info("Extracted Title_Sort: %s" % title_sort)

                ##### Field 100 and Field 700 #####
                # Authors
                # primary authors
                for i in record.xpath("./marc21:datafield[@tag='100']/marc21:subfield[@code='4' and text()='aut']/../marc21:subfield[@code='a' and string-length(text())>0]", namespaces=ns):
                    name = re.sub(" \[.*\]$", "", i.text.strip())
                    authors.append(name)
                # secondary authors
                for i in record.xpath("./marc21:datafield[@tag='700']/marc21:subfield[@code='4' and text()='aut']/../marc21:subfield[@code='a' and string-length(text())>0]", namespaces=ns):
                    name = re.sub(" \[.*\]$", "", i.text.strip())
                    authors.append(name)
                if len(authors) == 0:  # if no "real" author was found take all persons involved
                    # secondary authors
                    for i in record.xpath("./marc21:datafield[@tag='700']/marc21:subfield[@code='a' and string-length(text())>0]", namespaces=ns):
                        name = re.sub(" \[.*\]$", "", i.text.strip())
                        authors.append(name)
                if len(authors) > 0:
                    author_sort = authors[0]

                # Log
                if len(authors) > 0:
                    log.info("Extracted Authors: %s" % " & ".join(authors))
                if author_sort is not None:
                    log.info("Extracted Author_Sort: %s" % " & ".join(authors))

                ##### Field 856 #####
                # Comments
                for i in record.xpath("./marc21:datafield[@tag='856']/marc21:subfield[@code='u' and string-length(text())>0]", namespaces=ns):
                    if i.text.startswith("http://deposit.dnb.de/"):
                        br = self.browser
                        log.info('Downloading Comments from: %s' % i.text)
                        try:
                            comments = br.open_novisit(
                                i.text, timeout=30).read()
                            comments = re.sub(
                                b'(\s|<br>|<p>|\n)*Angaben aus der Verlagsmeldung(\s|<br>|<p>|\n)*(<h3>.*?</h3>)*(\s|<br>|<p>|\n)*', b'', comments, flags=re.IGNORECASE)
                            comments = sanitize_comments_html(comments)
                            break
                        except:
                            log.info("Could not download Comments from %s" % i)

                # Log
                if comments is not None:
                    log.info('Comments: %s' % comments)

                # If no comments are found for this edition, look at other editions of this book (Fields 776)
                # TODO: Make this configurable (default: yes)
                if comments is None:
                    # get all other issues
                    for i in record.xpath("./marc21:datafield[@tag='776']/marc21:subfield[@code='w' and string-length(text())>0]", namespaces=ns):
                        other_idn = re.sub("^\(.*\)", "", i.text.strip())
                        subquery = 'num='+other_idn + \
                            ' NOT (mat=film OR mat=music OR mat=microfiches OR cod=tt)'
                        log.info(subquery)

                        if self.cfg_dnb_token is None:
                            subresults = self.getSearchResultsByScraping(
                                log, subquery, timeout)
                        else:
                            subresults = self.getSearchResults(
                                log, subquery, timeout)

                        if subresults is None:
                            continue

                        for subrecord in subresults:
                            for i in subrecord.xpath("./marc21:datafield[@tag='856']/marc21:subfield[@code='u' and string-length(text())>0]", namespaces=ns):
                                if i.text.startswith("http://deposit.dnb.de/"):
                                    br = self.browser
                                    log.info(
                                        'Downloading Comments from: %s' % i.text)
                                    try:
                                        comments = br.open_novisit(
                                            i.text, timeout=30).read()
                                        comments = re.sub(
                                            b'(\s|<br>|<p>|\n)*Angaben aus der Verlagsmeldung(\s|<br>|<p>|\n)*(<h3>.*?</h3>)?(\s|<br>|<p>|\n)*', b'', comments, flags=re.IGNORECASE)
                                        comments = sanitize_comments_html(
                                            comments)
                                        break
                                    except:
                                        log.info(
                                            "Could not download Comments from %s" % i)
                            if comments is not None:
                                log.info(
                                    'Comments from other issue: %s' % comments)
                                break

                ##### Field 16 #####
                # ID: IDN
                for i in record.xpath("./marc21:datafield[@tag='016']/marc21:subfield[@code='a' and string-length(text())>0]", namespaces=ns):
                    idn = i.text.strip()
                    break
                # Log
                if idn is not None:
                    log.info("Extracted ID IDN: %s" % idn)

                ##### Field 24 #####
                # ID: URN
                for i in record.xpath("./marc21:datafield[@tag='024']/marc21:subfield[@code='2' and text()='urn']/../marc21:subfield[@code='a' and string-length(text())>0]", namespaces=ns):
                    urn = i.text.strip()
                    match = re.search("^urn:(.+)$", urn)
                    if match:
                         urn = match.group(1)
                         break

                # Log
                if urn is not None:
                    log.info("Extracted ID URN: %s" % urn)

                ##### Field 20 #####
                # ID: ISBN
                for i in record.xpath("./marc21:datafield[@tag='020']/marc21:subfield[@code='a' and string-length(text())>0]", namespaces=ns):
                    isbn_regex = "(?:ISBN(?:-1[03])?:? )?(?=[-0-9 ]{17}|[-0-9X ]{13}|[0-9X]{10})(?:97[89][- ]?)?[0-9]{1,5}[- ]?(?:[0-9]+[- ]?){2}[0-9X]"
                    match = re.search(isbn_regex, i.text.strip())
                    isbn = match.group()
                    isbn = isbn.replace('-', '')
                    break

                # Log
                if isbn is not None:
                    log.info("Extracted ID ISBN: %s" % isbn)

                # When doing an exact search for a given ISBN skip books with wrong ISBNs
                if isbn is not None and "isbn" in exact_search:
                    if isbn != exact_search["isbn"]:
                        log.info(
                            "Extracted ISBN does not match book's ISBN, skipping record")
                        continue

                ##### Field 82 #####
                # ID: Sachgruppe (DDC)
                for i in record.xpath("./marc21:datafield[@tag='082']/marc21:subfield[@code='a' and string-length(text())>0]", namespaces=ns):
                    ddc.append(i.text.strip())

                # Log
                if len(ddc) > 0:
                    log.info("Extracted ID DDC: %s" % ",".join(ddc))

                ##### Field 490 #####
                # In theory this field is not used for "real" book series, use field 830 instead. But it is used.
                # Series and Series_Index
                if series is None or (series is not None and series_index == "0"):
                    for i in record.xpath("./marc21:datafield[@tag='490']/marc21:subfield[@code='v' and string-length(text())>0]/../marc21:subfield[@code='a' and string-length(text())>0]/..", namespaces=ns):
                        # "v" either "Nr. 220" or "This great Seriestitle : Nr. 220" - if available use this instead of attribute a
                        attr_v = i.xpath(
                            "./marc21:subfield[@code='v']", namespaces=ns)[0].text.strip()
                        parts = re.split(" : ", attr_v)
                        if len(parts) == 2:
                            if bool(re.search("\d", parts[0])) != bool(re.search("\d", parts[1])):
                                # figure out which part contains the index
                                if bool(re.search("\d", parts[0])):
                                    indexpart = parts[0]
                                    textpart = parts[1]
                                else:
                                    indexpart = parts[1]
                                    textpart = parts[0]

                                match = re.search("(\d+[,\.\d+]?)", indexpart)
                                if match is not None:
                                    series_index = match.group(1)
                                    series = textpart.strip()

                        else:
                            match = re.search("(\d+[,\.\d+]?)", attr_v)
                            if match is not None:
                                series_index = match.group(1)
                            else:
                                series_index = "0"

                        if series_index is not None:
                            series_index = series_index.replace(',', '.')

                        # Use Series Name from attribute "a" if not already found in attribute "v"
                        if series is None:
                            series = i.xpath(
                                "./marc21:subfield[@code='a']", namespaces=ns)[0].text.strip()

                        # Log
                        if series_index is not None:
                            log.info(
                                "Extracted Series Index from Field 490: %s" % series_index)
                        if series is not None:
                            log.info(
                                "Extracted Series from Field 490: %s" % series)
                            series = self.cleanUpSeries(
                                log, series, publisher_name)
                        if series is not None:
                            break

                ##### Field 246 #####
                # Series and Series_Index
                if series is None or (series is not None and series_index == "0"):
                    for i in record.xpath("./marc21:datafield[@tag='246']/marc21:subfield[@code='a' and string-length(text())>0]", namespaces=ns):
                        match = re.search(
                            "^(.+?) ; (\d+[,\.\d+]?)$", i.text.strip())
                        if match is not None:
                            series = match.group(1)
                            series_index = match.group(2)

                            # Log
                            if series_index is not None:
                                log.info(
                                    "Extracted Series Index from Field 246: %s" % series_index)
                            if series is not None:
                                log.info(
                                    "Extracted Series from Field 246: %s" % series)
                                series = self.cleanUpSeries(
                                    log, series, publisher_name)
                            if series is not None:
                                break

                ##### Field 800 #####
                # Series and Series_Index
                if series is None or (series is not None and series_index == "0"):
                    for i in record.xpath("./marc21:datafield[@tag='800']/marc21:subfield[@code='v' and string-length(text())>0]/../marc21:subfield[@code='t' and string-length(text())>0]/..", namespaces=ns):
                        # Series Index
                        series_index = i.xpath(
                            "./marc21:subfield[@code='v']", namespaces=ns)[0].text.strip()
                        match = re.search("(\d+[,\.\d+]?)", series_index)
                        if match is not None:
                            series_index = match.group(1)
                        else:
                            series_index = "0"
                        series_index = series_index.replace(',', '.')
                        # Series
                        series = i.xpath(
                            "./marc21:subfield[@code='t']", namespaces=ns)[0].text.strip()

                        # Log
                        if series_index is not None:
                            log.info(
                                "Extracted Series Index from Field 800: %s" % series_index)
                        if series is not None:
                            log.info(
                                "Extracted Series from Field 800: %s" % series)
                            series = self.cleanUpSeries(
                                log, series, publisher_name)
                        if series is not None:
                            break

                ##### Field 830 #####
                # Series and Series_Index
                if series is None or (series is not None and series_index == "0"):
                    for i in record.xpath("./marc21:datafield[@tag='830']/marc21:subfield[@code='v' and string-length(text())>0]/../marc21:subfield[@code='a' and string-length(text())>0]/..", namespaces=ns):
                        # Series Index
                        series_index = i.xpath(
                            "./marc21:subfield[@code='v']", namespaces=ns)[0].text.strip()
                        match = re.search("(\d+[,\.\d+]?)", series_index)
                        if match is not None:
                            series_index = match.group(1)
                        else:
                            series_index = "0"
                        series_index = series_index.replace(',', '.')
                        # Series
                        series = i.xpath(
                            "./marc21:subfield[@code='a']", namespaces=ns)[0].text.strip()

                        # Log
                        if series_index is not None:
                            log.info(
                                "Extracted Series Index from Field 830: %s" % series_index)
                        if series is not None:
                            log.info(
                                "Extracted Series from Field 830: %s" % series)
                            series = self.cleanUpSeries(
                                log, series, publisher_name)
                        if series is not None:
                            break

                ##### Field 689 #####
                # GND Subjects
                for i in record.xpath("./marc21:datafield[@tag='689']/marc21:subfield[@code='a' and string-length(text())>0]", namespaces=ns):
                    subjects_gnd.append(i.text.strip())
                for f in range(600, 656):
                    for i in record.xpath("./marc21:datafield[@tag='"+str(f)+"']/marc21:subfield[@code='2' and text()='gnd']/../marc21:subfield[@code='a' and string-length(text())>0]", namespaces=ns):
                        if i.text.startswith("("):
                            continue
                        subjects_gnd.append(i.text)

                # Log
                if len(subjects_gnd) > 0:
                    log.info("Extracted GND Subjects: %s" %
                             " ".join(subjects_gnd))

                ##### Fields 600-655 #####
                # TODO: Remove sorting characters
                # Non-GND subjects
                for f in range(600, 656):
                    for i in record.xpath("./marc21:datafield[@tag='"+str(f)+"']/marc21:subfield[@code='a' and string-length(text())>0]", namespaces=ns):
                        # ignore entries starting with "(":
                        if i.text.startswith("("):
                            continue
                        subjects_non_gnd.extend(re.split(',|;', i.text))
                # remove one-character subjects:
                for i in subjects_non_gnd:
                    if len(i) < 2:
                        subjects_non_gnd.remove(i)

                # Log
                if len(subjects_non_gnd) > 0:
                    log.info("Extracted non-GND Subjects: %s" %
                             " ".join(subjects_non_gnd))

                ##### Field 250 #####
                # Edition
                for i in record.xpath("./marc21:datafield[@tag='250']/marc21:subfield[@code='a' and string-length(text())>0]", namespaces=ns):
                    edition = i.text.strip()
                    break

                # Log
                if edition is not None:
                    log.info("Extracted Edition: %s" % edition)

                ##### Field 41 #####
                # Languages
                for i in record.xpath("./marc21:datafield[@tag='041']/marc21:subfield[@code='a' and string-length(text())>0]", namespaces=ns):
                    languages.append(i.text.strip())

                # Log
                if languages is not None:
                    log.info("Extracted Languages: %s" % ",".join(languages))

                ##### If configured: Try to separate Series, Series Index and Title from the fetched title #####
                # if self.cfg_guess_series is True:
                if (series is None or (series is not None and series_index == "0")) and self.cfg_guess_series is True:
                    guessed_series = None
                    guessed_series_index = None
                    guessed_title = None

                    log.info("Starting Series Guesser")

                    parts = re.split(
                        "[:]", self.removeSortingCharacters(title))

                    if len(parts) == 2:
                        log.info("Title has two parts")
                        # make sure only one part of the two parts contains digits
                        if bool(re.search("\d", parts[0])) != bool(re.search("\d", parts[1])):
                            log.info("only one title part contains digits")
                            # figure out which part contains the index
                            if bool(re.search("\d", parts[0])):
                                indexpart = parts[0]
                                textpart = parts[1]
                            else:
                                indexpart = parts[1]
                                textpart = parts[0]

                            # Look at the part without digits:
                            # remove odd characters from start and end of the text part
                            match = re.match(
                                "^[\s\-–:]*(.+?)[\s\-–:]*$", textpart)
                            if match:
                                textpart = match.group(1)

                            # Look at the part with digits:
                            # for Titleparts like: "Name of the series - Episode 2"
                            match = re.match(
                                "^\s*(\S\D*?[a-zA-Z]\D*?)\W[\(\/\.,\s\-–:]*(?:#|Nr\.|Episode|Bd\.|Sammelband|[B|b]and|Part|Teil|Folge)[,\-–:\s#\(]*(\d+\.?\d*)[\)\s\-–:]*$", indexpart)
                            if match:
                                guessed_series_index = match.group(2)
                                guessed_series = match.group(1)
                                if guessed_series is None:
                                    guessed_series = textpart
                                    guessed_title = textpart + " : Band " + guessed_series_index
                                else:
                                    guessed_title = textpart

                                #log.info("ALGO1: guessed_title: " + guessed_title)
                                #log.info("ALGO1: guessed_series: " + guessed_series)
                                #log.info("ALGO1: guessed_series_index: " + guessed_series_index)

                            else:
                                # for Titleparts like: "Episode 2 Name of the series"
                                match = re.match(
                                    "^\s*(?:#|Nr\.|Episode|Bd\.|Sammelband|[B|b]and|Part|Teil|Folge)[,\-–:\s#\(]*(\d+\.?\d*)[\)\s\-–:]*(\S\D*?[a-zA-Z]\D*?)[\/\.,\-–\s]*$", indexpart)
                                if match:
                                    guessed_series_index = match.group(1)
                                    guessed_series = match.group(2)

                                    if guessed_series is None:
                                        # sometimes books with multiple volumes are detected as series without name -> Add the volume to the title
                                        guessed_series = textpart
                                        guessed_title = textpart + " : Band " + guessed_series_index
                                    else:
                                        guessed_title = textpart

                                    #log.info("ALGO2: guessed_title: " + guessed_title)
                                    #log.info("ALGO2: guessed_series: " + guessed_series)
                                    #log.info("ALGO2: guessed_series_index: " + guessed_series_index)

                                else:
                                    # for titleparts like: "Band 2"
                                    match = re.match(
                                        "^[\s\(]*(?:#|Nr\.|Episode|Bd\.|Sammelband|[B|b]and|Part|Teil|Folge)[,\-–:\s#\(]*(\d+\.?\d*)[\)\s\-–:]*[\/\.,\-–\s]*$", indexpart)
                                    if match:
                                        guessed_series_index = match.group(1)
                                        # ...with textpart like NAME OF SERIES\s[\-\.;:]\sNAME OF TITLE
                                        # some false positives
                                        match = re.match(
                                            "^\s*(\w+.+?)\s?[\.;\-–:]+\s(\w+.+)\s*$", textpart)
                                        if match:
                                            guessed_series = match.group(1)
                                            guessed_title = match.group(2)

                                            log.info(
                                                "ALGO3: guessed_title: " + guessed_title)
                                            log.info(
                                                "ALGO3: guessed_series: " + guessed_series)
                                            log.info(
                                                "ALGO3: guessed_series_index: " + guessed_series_index)

                    elif len(parts) == 1:
                        log.info("Title has one part")
                        # for Titles like: "Name of the series - Title (Episode 2)"
                        match = re.match(
                            "^\s*(\S.+?) \- (\S.+?) [\(\/\.,\s\-–:](?:#|Nr\.|Episode|Bd\.|Sammelband|[B|b]and|Part|Teil|Folge)[,\-–:\s#\(]*(\d+\.?\d*)[\)\s\-–:]*$", parts[0])
                        if match:
                            guessed_series_index = match.group(3)
                            guessed_series = match.group(1)
                            guessed_title = match.group(2)

                            #log.info("ALGO4: guessed_title: " + guessed_title)
                            #log.info("ALGO4: guessed_series: " + guessed_series)
                            #log.info("ALGO4: guessed_series_index: " + guessed_series_index)

                        else:
                            # for Titles like: "Name of the series - Episode 2"
                            match = re.match(
                                "^\s*(\S.+?)[\(\/\.,\s\-–:]*(?:#|Nr\.|Episode|Bd\.|Sammelband|[B|b]and|Part|Teil|Folge)[,\-–:\s#\(]*(\d+\.?\d*)[\)\s\-–:]*$", parts[0])
                            if match:
                                guessed_series_index = match.group(2)
                                guessed_series = match.group(1)
                                guessed_title = guessed_series + " : Band " + guessed_series_index

                                #log.info("ALGO5: guessed_title: " + guessed_title)
                                #log.info("ALGO5: guessed_series: " + guessed_series)
                                #log.info("ALGO5: guessed_series_index: " + guessed_series_index)

                    # Log
                    if guessed_series is not None:
                        log.info("Guessed Series: %s" % guessed_series)
                        #guessed_series = self.cleanUpSeries(log, guessed_series, publisher_name)
                    if guessed_series_index is not None:
                        log.info("Guessed Series Index: %s" %
                                 guessed_series_index)
                    if guessed_title is not None:
                        log.info("Guessed Title: %s" % guessed_title)
                        guessed_title = self.cleanUpTitle(log, guessed_title)

                    if guessed_series is not None and guessed_series_index is not None and guessed_title is not None:
                        title = guessed_title
                        series = guessed_series
                        series_index = guessed_series_index

                ##### Filter exact searches #####
                # When doing an exact search for a given IDN skip books with wrong IDNs
                # TODO: Currently exact_search for ISBN is not implemented. Would require ISBN-10 and ISBN-13 conversions
                if idn is not None and "idn" in exact_search:
                    if idn != exact_search["idn"]:
                        log.info(
                            "Extracted IDN does not match book's IDN, skipping record")
                        continue

                ##### Put it all together #####
                if self.cfg_append_edition_to_title == True and edition is not None:
                    title = title + " : " + edition

                mi = Metadata(self.removeSortingCharacters(title), list(map(
                    lambda i: self.removeSortingCharacters(i), authors)))
                mi.title_sort = self.removeSortingCharacters(title_sort)
                mi.author_sort = self.removeSortingCharacters(author_sort)
                mi.languages = languages
                mi.pubdate = pubdate
                mi.publisher = " ; ".join(filter(
                    None, [publisher_location, self.removeSortingCharacters(publisher_name)]))
                if series_index is not None and float(series_index) < 3000:
                    mi.series = self.removeSortingCharacters(series)
                    mi.series_index = series_index
                mi.comments = comments
                mi.isbn = isbn  # also required for cover download
                mi.set_identifier('urn', urn)
                mi.set_identifier('dnb-idn', idn)
                mi.set_identifier('ddc', ",".join(ddc))

                # cfg_subjects:
                # 0: use only subjects_gnd
                if self.cfg_fetch_subjects == 0:
                    mi.tags = self.uniq(subjects_gnd)
                # 1: use only subjects_gnd if found, else subjects_non_gnd
                elif self.cfg_fetch_subjects == 1:
                    if len(subjects_gnd) > 0:
                        mi.tags = self.uniq(subjects_gnd)
                    else:
                        mi.tags = self.uniq(subjects_non_gnd)
                # 2: subjects_gnd and subjects_non_gnd
                elif self.cfg_fetch_subjects == 2:
                    mi.tags = self.uniq(subjects_gnd + subjects_non_gnd)
                # 3: use only subjects_non_gnd if found, else subjects_gnd
                elif self.cfg_fetch_subjects == 3:
                    if len(subjects_non_gnd) > 0:
                        mi.tags = self.uniq(subjects_non_gnd)
                    else:
                        mi.tags = self.uniq(subjects_gnd)
                # 4: use only subjects_non_gnd
                elif self.cfg_fetch_subjects == 4:
                    mi.tags = self.uniq(subjects_non_gnd)
                # 5: use no subjects at all
                elif self.cfg_fetch_subjects == 5:
                    mi.tags = []

                # put current result's metdata into result queue
                log.info("Final formatted result: \n%s" % mi)
                result_queue.put(mi)

    def removeSortingCharacters(self, text):
        if text is not None:
            # remove sorting word markers
            return ''.join([c for c in text if ord(c) != 152 and ord(c) != 156])
        else:
            return None

    def cleanUpTitle(self, log, title):
        if title is not None:
            match = re.search(
                '^(.+) [/:] [Aa]us dem .+? von(\s\w+)+$', self.removeSortingCharacters(title))
            if match:
                title = match.group(1)
                log.info("Cleaning up title: %s" % title)
        return title

    def cleanUpSeries(self, log, series, publisher_name):
        if series is not None:
            # series must at least contain a single character or digit
            match = re.search('[\w\d]', series)
            if not match:
                #log.info("Series must at least contain a single character or digit, ignoring")
                return None

            # remove sorting word markers
            series = ''.join(
                [c for c in series if ord(c) != 152 and ord(c) != 156])

            # do not accept publisher name as series
            if publisher_name is not None:
                if publisher_name == series:

                    log.info("Series is equal to publisher name, ignoring")
                    return None

                # Skip series info if it starts with the first word of the publisher's name (which must be at least 4 characters long)
                match = re.search(
                    '^(\w\w\w\w+)', self.removeSortingCharacters(publisher_name))
                if match:
                    pubcompany = match.group(1)
                    if re.search('^'+pubcompany, series, flags=re.IGNORECASE):
                        log.info("Series starts with publisher name, ignoring")
                        return None

            # do not accept some other unwanted series names
            # TODO: Has issues with Umlaus in regex (or series string?)
            for i in [
                '^\[Ariadne\]$', '^Ariadne$', '^atb$', '^BvT$', '^Bastei L', '^bb$', '^Beck Paperback', '^Beck\-.*berater', '^Beck\'sche Reihe', '^Bibliothek Suhrkamp$', '^BLT$',
                '^DLV-Taschenbuch$', '^Edition Suhrkamp$', '^Edition Lingen Stiftung$', '^Edition C', '^Edition Metzgenstein$', '^ETB$', '^dtv', '^Ein Goldmann',
                '^Oettinger-Taschenbuch$', '^Haymon-Taschenbuch$', '^Mira Taschenbuch$', '^Suhrkamp-Taschenbuch$', '^Bastei-L', '^Hey$', '^btb$', '^bt-Kinder', '^Ravensburger',
                '^Sammlung Luchterhand$', '^blanvalet$', '^KiWi$', '^Piper$', '^C.H. Beck', '^Rororo', '^Goldmann$', '^Moewig$', '^Fischer Klassik$', '^hey! shorties$', '^Ullstein',
                '^Unionsverlag', '^Ariadne-Krimi', '^C.-Bertelsmann', '^Phantastische Bibliothek$', '^Beck Paperback$', '^Beck\'sche Reihe$', '^Knaur', '^Volk-und-Welt',
                    '^Allgemeine', '^Horror-Bibliothek$']:
                if re.search(i, series, flags=re.IGNORECASE):
                    log.info("Series contains unwanted string %s, ignoring" % i)
                    return None
        return series

    def uniq(self, listWithDuplicates):
        uniqueList = []
        if len(listWithDuplicates) > 0:
            for i in listWithDuplicates:
                if i not in uniqueList:
                    uniqueList.append(i)
        return uniqueList

    def getSearchResults(self, log, query, timeout=30):
        log.info('Querying: %s' % query)

        queryUrl = self.QUERYURL % (
            self.cfg_dnb_token, quote(query.encode('utf-8')))
        log.info('Query URL: %s' % queryUrl)

        xmlData = None
        try:
            data = self.browser.open_novisit(queryUrl, timeout=timeout).read()
            #log.info('Got some data: %s' % data)

            xmlData = etree.XML(data)
            # log.info(etree.tostring(xmlData,pretty_print=True))

            numOfRecords = xmlData.xpath("./zs:numberOfRecords", namespaces={"zs": "http://www.loc.gov/zing/srw/"})[0].text.strip()
            log.info('Got records: %s' % numOfRecords)

            if int(numOfRecords) == 0:
                return None

            return xmlData.xpath("./zs:records/zs:record/zs:recordData/marc21:record", namespaces={'marc21': 'http://www.loc.gov/MARC21/slim', "zs": "http://www.loc.gov/zing/srw/"})
        except:
            try:
                diag = ": ".join([
                    xmlData.find('diagnostics/diag:diagnostic/diag:details', namespaces={
                              None: 'http://www.loc.gov/zing/srw/', 'diag': 'http://www.loc.gov/zing/srw/diagnostic/'}).text,
                    xmlData.find('diagnostics/diag:diagnostic/diag:message', namespaces={
                              None: 'http://www.loc.gov/zing/srw/', 'diag': 'http://www.loc.gov/zing/srw/diagnostic/'}).text
                ])
                log.error('ERROR: %s' % diag)
                return None
            except:
                log.error('ERROR: Got no valid response.')
                return None

    def getSearchResultsByScraping(self, log, query, timeout=30):
        log.info('Querying: %s' % query)

        m21records = []
        resultNum = 0
        while resultNum < 100:
            queryUrl = self.SCRAPEURL % (quote_plus(
                query.encode('utf-8')+str("&any").encode('utf-8')), str(resultNum))
            log.info('Query URL: %s' % queryUrl)
            try:
                webpage = self.browser.open_novisit(
                    queryUrl, timeout=timeout).read()
                htmlData = etree.HTML(webpage)

                marc21links = htmlData.xpath(
                    u".//a[text()='MARC21-XML-Repräsentation dieses Datensatzes']/@href")
                if len(marc21links) == 0:
                    break

                m21data = self.browser.open_novisit(
                    marc21links[0], timeout=timeout).read()
                m21records.append(etree.XML(m21data))
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
        url = self.COVERURL % isbn
        return url

    def download_cover(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30, get_best_cover=False):
        cached_url = self.get_cached_cover_url(identifiers)
        if cached_url is None:
            log.info('No cached cover found, running identify')
            rq = Queue()
            self.identify(log, rq, abort, title=title,
                          authors=authors, identifiers=identifiers)
            if abort.is_set():
                return
                results = []
                while True:
                    try:
                        results.append(rq.get_nowait())
                    except Empty:
                        break
                results.sort(key=self.identify_results_keygen(
                    title=title, authors=authors, identifiers=identifiers))
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
            result_queue.put((self, cdata))
        except:
            log.info("Could not download Cover")


if __name__ == '__main__':  # tests
    # To run these test use:
    # calibre-debug -e __init__.py
    from calibre.ebooks.metadata.sources.test import (
        test_identify_plugin, title_test, authors_test, series_test)

    test_identify_plugin(DNB_DE.name, [
        (
            {'identifiers': {'isbn': '9783404285266'}},
            [title_test('Sehnsucht des Herzens', exact=True),
             authors_test(['Lucas, Joanne St.'])]
        ),
    ])
