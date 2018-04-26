# DNB metadata plugin for Calibre

A Calibre metadata source plugin that uses the catalogue (https://portal.dnb.de) of the Deutsche Nationalbibliothek (DNB) to retrieve metadata.
It supports retrieval of DNB-IDN, ISBN, authors, title, edition, tags, pulication date, languages, publisher, comments, series, series index and cover.

For books without series information it can try to extract series and series index from the title.
GND and/or non-GND subjects can be used as tags.

### Requirements:

You need a personal SRU Access Token. The Token is free of charge.

#### How to get a SRU Access Token:

1. Create a free account at https://portal.dnb.de/myAccount/register.htm
1. Write an email to schnittstellen-service@dnb.de and ask them to enable SRU Access Token generation for your account.
1. Log in into your DNB account and create an Access Token.
1. Enter the Access Token into this plugin's settings page.


### Limitations and caveats

- The returned publication date contains only the year, not the precise date.
