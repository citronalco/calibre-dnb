# Calibre Metadata Source Plugin for Deutsche Nationalbibliothek (DNB)

A Calibre metadata source plugin that uses the catalogue (https://portal.dnb.de) of the Deutsche Nationalbibliothek (DNB) to retrieve metadata. DNB is the German central archival library. German publishers are required to send them a copy of every book for archival, so it's the largest metadata source for literature published in Germany.

This plugin supports retrieval of DNB-IDN, ISBN, authors, title, edition, tags, publication date, languages, publisher, comments, series, series index and cover.

For books without series information it can try to extract series and series index from the title.
GND and/or non-GND subjects can be used as tags.

This plugin works with Python 2 and Python 3.

### Requirements:

None.

For better performance it is recommended to use a personal SRU Access Token. The Token is free of charge, you can get it from the DNB.
With this token this plugin will use DNB's SRU API, without token it will do web scraping. The downloaded metadata is the same in each case.

### Installation:

1. Start Calibre
1. Go to "Preferences" -> "Plugins" and click on the "Get new plugins" button.
1. Search for "Deutsche Nationalbibliothek" and click the "Install" button.
1. Restart Calibre

You can also downloaded the plugin as ZIP file from here: https://github.com/citronalco/calibre-dnb/releases/

### How to get a SRU Access Token (optional):

1. Create a free account at https://portal.dnb.de/myAccount/register.htm
1. Write an email to schnittstellen-service@dnb.de and ask them to enable SRU Access Token generation for your login name and that you want to access the title data catalogue ("Titeldaten-Katalog") in MARC21-xml format.
1. Wait for their confirmation email.
1. Log in into your DNB account and create an Access Token.
1. Enter the Access Token into this plugin's settings page.

The Token is free of charge.

### Limitations and caveats

- The returned publication date contains only the year, not the precise date.
