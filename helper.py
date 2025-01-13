import re

def remove_sorting_characters(text):
    """
    Remove sorting word markers
    """
    if text:
        return ''.join([c for c in text if ord(c) != 152 and ord(c) != 156])
    return None


def clean_title(log, title):
    """
    Clean up title
    """
    if title:
        # remove name of translator from title
        match = re.search(
            r'^(.+) [/:] [Aa]us dem .+? von(\s\w+)+$', remove_sorting_characters(title))
        if match:
            title = match.group(1)
            log.info("[Title Cleaning] Removed translator, title is now: %s" % title)
    return title


def clean_series(log, series, publisher_name):
    """
    Clean up series
    """
    if series:
        # series must at least contain a single character or digit
        match = re.search(r'[\w\d]', series)
        if not match:
            return None

        # remove sorting word markers
        series = remove_sorting_characters(series)

        # do not accept publisher name as series
        if publisher_name:
            if publisher_name == series:
                log.info("[Series Cleaning] Series %s is equal to publisher, ignoring" % series)
                return None

            # Skip series info if it starts with the first word of the publisher's name (which must be at least 4 characters long)
            match = re.search(
                r'^(\w\w\w\w+)', remove_sorting_characters(publisher_name))
            if match:
                pubcompany = match.group(1)
                if re.search(r'^\W*' + pubcompany, series, flags=re.IGNORECASE):
                    log.info("[Series Cleaning] Series %s starts with publisher, ignoring" % series)
                    return None

        # do not accept some other unwanted series names
        # TODO: Has issues with Umlaus in regex (or series string?)
        # TODO: Make user configurable
        for i in [
            r'^Roman$', r'^Science-fiction$',
            r'^\[Ariadne\]$', r'^Ariadne$', r'^atb$', r'^BvT$', r'^Bastei L', r'^bb$', r'^Beck Paperback', r'^Beck\-.*berater', r'^Beck\'sche Reihe', r'^Bibliothek Suhrkamp$', r'^BLT$',
            r'^DLV-Taschenbuch$', r'^Edition Suhrkamp$', r'^Edition Lingen Stiftung$', r'^Edition C', r'^Edition Metzgenstein$', r'^ETB$', r'^dtv', r'^Ein Goldmann',
            r'^Oettinger-Taschenbuch$', r'^Haymon-Taschenbuch$', r'^Mira Taschenbuch$', r'^Suhrkamp-Taschenbuch$', r'^Bastei-L', r'^Hey$', r'^btb$', r'^bt-Kinder', r'^Ravensburger',
            r'^Sammlung Luchterhand$', r'^blanvalet$', r'^KiWi$', r'^Piper$', r'^C.H. Beck', r'^Rororo$', r'^Goldmann$', r'^Moewig$', r'^Fischer Klassik$', r'^hey! shorties$', r'^Ullstein',
            r'^Unionsverlag', r'^Ariadne-Krimi', r'^C.-Bertelsmann', r'^Phantastische Bibliothek$', r'^Beck Paperback$', r'^Beck\'sche Reihe$', r'^Knaur', r'^Volk-und-Welt',
            r'^Allgemeine', r'^Premium', r'^Horror-Bibliothek$']:
            if re.search(i, series, flags=re.IGNORECASE):
                log.info("[Series Cleaning] Series %s contains unwanted string %s, ignoring" % (series, i))
                return None
    return series


def uniq(listWithDuplicates):
    """
    Remove duplicates from a list
    """
    uniqueList = []
    if len(listWithDuplicates) > 0:
        for i in listWithDuplicates:
            if i not in uniqueList:
                uniqueList.append(i)
    return uniqueList



def iso639_2b_as_iso639_3(lang):
    """
    Convert ISO 639-2/B to ISO 639-3
    """
    #  Most codes in ISO 639-2/B are the same as in ISO 639-3. This are the exceptions:
    mapping = {
        'alb': 'sqi',
        'arm': 'hye',
        'baq': 'eus',
        'bur': 'mya',
        'chi': 'zho',
        'cze': 'ces',
        'dut': 'nld',
        'fre': 'fra',
        'geo': 'kat',
        'ger': 'deu',
        'gre': 'ell',
        'ice': 'isl',
        'mac': 'mkd',
        'may': 'msa',
        'mao': 'mri',
        'per': 'fas',
        'rum': 'ron',
        'slo': 'slk',
        'tib': 'bod',
        'wel': 'cym',
    }
    try:
        return mapping[lang.lower()]
    except KeyError:
        return lang


def strip_german_joiners(wordlist):
    """
    Remove German joiners from list of words
    By default, Calibre's function "get_title_tokens(...,strip_joiners=True,...)" only removes "a", "and", "the", "&"
    """
    tokens = []
    for word in wordlist:
        if word.lower() not in ( 'ein', 'eine', 'einer', 'der', 'die', 'das', 'und', 'oder'):
            tokens.append(word)
    return tokens
