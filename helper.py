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


def clean_series(log, series, publisher_name, unwanted_regex):
    """
    Clean up series
    """
    if series:
        # series must at least contain a single character
        match = re.search(r'\S', series)
        if not match:
            return None

        # remove sorting word markers
        series = remove_sorting_characters(series)

        # do not accept publisher name as series
        if publisher_name:
            if publisher_name.lower() == series.lower():
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
        # try...except, log errors!
        if unwanted_regex:
            for i in unwanted_regex:
                try:
                    if re.search(r'' + i, series, flags=re.IGNORECASE):
                        log.info("[Series Cleaning] Series %s contains unwanted string %s, ignoring" % (series, i))
                        return None
                except:
                    log.warn("[Series Cleaning] Regular expression %s caused an error, ignoring" % i)
                    pass
    return series


def uniq(list_with_duplicates):
    """
    Remove duplicates from a list
    """
    unique_list = []
    for i in list_with_duplicates:
        if i not in unique_list:
            unique_list.append(i)
    return unique_list


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


def guess_series_from_title(log, title):
    """
    Try to extract Series and Series Index from a book's title
    """
    guessed_series = None
    guessed_series_index = None
    guessed_title = None

    parts = re.split("[:]", remove_sorting_characters(title))

    if len(parts) == 2:
        # make sure only one part of the two parts contains digits
        if bool(re.search(r"\d", parts[0])) != bool(re.search(r"\d", parts[1])):

            # call the part with the digits "indexpart" as it contains the series_index, the one without digits "textpart"
            if bool(re.search(r"\d", parts[0])):
                indexpart = parts[0]
                textpart = parts[1]
            else:
                indexpart = parts[1]
                textpart = parts[0]

            # remove odd characters from start and end of the textpart
            match = re.match(
                r"^[\s\-–—:]*(.+?)[\s\-–—:]*$", textpart)
            if match:
                textpart = match.group(1)

            # if indexparts looks like "Name of the series - Episode 2": extract series and series_index
            match = re.match(
                r"^\s*(\S\D*?[a-zA-Z]\D*?)\W[\(\/\.,\s\-–—:]*(?:#|Reihe|Nr\.|Heft|Volume|Vol\.?|Episode|Bd\.|Sammelband|[B|b]and|Part|Kapitel|[Tt]eil|Folge)[,\-–—:\s#\(]*(\d+[\.,]?\d*)[\)\s\-–—:]*$", indexpart)
            if match:
                guessed_series_index = match.group(2)
                guessed_series = match.group(1)

                # sometimes books with multiple volumes are detected as series without series name -> Add the volume to the title if no series was found
                if not guessed_series:
                    guessed_series = textpart
                    guessed_title = textpart + " : Band " + guessed_series_index
                else:
                    guessed_title = textpart

                log.info("[Series Guesser] 2P1 matched: Title: %s, Series: %s[%s]" % (guessed_title, guessed_series, guessed_series_index))
                return guessed_title, guessed_series, guessed_series_index

            else:
                # if indexpart looks like "Episode 2 Name of the series": extract series and series_index
                match = re.match(
                    r"^\s*(?:#|Reihe|Nr\.|Heft|Volume|Vol\.?Episode|Bd\.|Sammelband|[B|b]and|Part|Kapitel|[Tt]eil|Folge)[,\-–—:\s#\(]*(\d+[\.,]?\d*)[\)\s\-–—:]*(\S\D*?[a-zA-Z]\D*?)[\/\.,\-–—\s]*$", indexpart)
                if match:
                    guessed_series_index = match.group(1)
                    guessed_series = match.group(2)

                    # sometimes books with multiple volumes are detected as series without series name -> Add the volume to the title if no series was found
                    if not guessed_series:
                        guessed_series = textpart
                        guessed_title = textpart + " : Band " + guessed_series_index
                    else:
                        guessed_title = textpart

                    log.info("[Series Guesser] 2P2 matched: Title: %s, Series: %s[%s]" % (guessed_title, guessed_series, guessed_series_index))
                    return guessed_title, guessed_series, guessed_series_index

                else:
                    # if indexpart looks like "Band 2": extract series_index
                    match = re.match(
                        r"^[\s\(]*(?:#|Reihe|Nr\.|Heft|Volume|Vol\.?Episode|Bd\.|Sammelband|[B|b]and|Part|Kapitel|[Tt]eil|Folge)[,\-–—:\s#\(]*(\d+[\.,]?\d*)[\)\s\-–—:]*[\/\.,\-–—\s]*$", indexpart)
                    if match:
                        guessed_series_index = match.group(1)

                        # if textpart looks like "Name of the Series - Book Title": extract series and title
                        match = re.match(
                            r"^\s*(\w+.+?)\s?[\.;\-–:]+\s(\w+.+)\s*$", textpart)
                        if match:
                            guessed_series = match.group(1)
                            guessed_title = match.group(2)

                            log.info("[Series Guesser] 2P3 matched: Title: %s, Series: %s[%s]" % (guessed_title, guessed_series, guessed_series_index))
                            return guessed_title, guessed_series, guessed_series_index

    elif len(parts) == 1:
        # if title looks like: "Name of the series - Title (Episode 2)"
        match = re.match(
            r"^\s*(\S.+?) \- (\S.+?) [\(\/\.,\s\-–:](?:#|Reihe|Nr\.|Heft|Volume|Vol\.?Episode|Bd\.|Sammelband|[B|b]and|Part|Kapitel|[Tt]eil|Folge)[,\-–—:\s#\(]*(\d+[\.,]?\d*)[\)\s\-–—:]*$", parts[0])
        if match:
            guessed_series_index = match.group(3)
            guessed_series = match.group(1)
            guessed_title = match.group(2)

            log.info("[Series Guesser] 1P1 matched: Title: %s, Series: %s[%s]" % (guessed_title, guessed_series, guessed_series_index))
            return guessed_title, guessed_series, guessed_series_index

        else:
            # if title looks like "Name of the series - Episode 2"
            match = re.match(
                r"^\s*(\S.+?)[\(\/\.,\s\-–—:]*(?:#|Reihe|Nr\.|Heft|Volume|Vol\.?Episode|Bd\.|Sammelband|[B|b]and|Part|Kapitel|[Tt]eil|Folge)[,\-–:\s#\(]*(\d+[\.,]?\d*)[\)\s\-–—:]*$", parts[0])
            if match:
                guessed_series_index = match.group(2)
                guessed_series = match.group(1)
                guessed_title = guessed_series + " : Band " + guessed_series_index

                log.info("[Series Guesser] 1P2 matched: Title: %s, Series: %s[%s]" % (guessed_title, guessed_series, guessed_series_index))
                return guessed_title, guessed_series, guessed_series_index

    return None
