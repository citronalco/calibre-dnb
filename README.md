# Calibre Metadata Source Plugin for Deutsche Nationalbibliothek (DNB)

A Calibre metadata source plugin that uses the catalogue (https://portal.dnb.de) of the Deutsche Nationalbibliothek (DNB) to retrieve metadata. DNB is the German central archival library. German publishers are required to send them a copy of every book for archival, so it's the largest metadata source for literature published in Germany.

This plugin supports retrieval of DNB-IDN, ISBN, authors, title, edition, tags, publication date, languages, publisher, comments, series, series index and cover.

For books without series information it can try to extract series and series index from the title.
GND and/or non-GND subjects can be used as tags.

This plugin works with Python 2 and Python 3.

### Installation:

1. Start Calibre
1. Go to "Preferences" -> "Plugins" and click on the "Get new plugins" button.
1. Search for "Deutsche Nationalbibliothek" and click the "Install" button.
1. Restart Calibre

You can also downloaded the plugin as ZIP file from here: https://git.bingo-ev.de/geierb/calibre-dnb/-/releases

### Limitations:

- Publication date: DNB only has the publication year, not the precise date.
