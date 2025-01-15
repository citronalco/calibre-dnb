from calibre import prints

def series_test(series_name, series_index):
    """ Test series_name and series_index """
    series_name = series_name.lower()

    def test(mi):
        ms = mi.series.lower()
        mi = mi.series_index
        if ms == series_name and int(mi) == int(series_index):
            return True
        prints('Series test failed. Expected: \'%s #%s\' found \'%s #%s\''%(series_name, series_index, ms, mi))
        return False

    return test


def languages_test(languages):
    """ Test languages """
    languages = {x.lower() for x in languages}

    def test(mi):
        l = {x.lower() for x in mi.languages}
        if l == languages:
            return True
        prints('Languages test failed. Expected: \'%s\' found \'%s\''%(languages, l))
        return False

    return test
