# DNB metadata plugin for Calibre

A Calibre metadata source plugin that uses the catalogue (https://portal.dnb.de) of the Deutsche Nationalbibliothek (DNB) to retrieve metadata.
If supports retrieval of DNB-IDN, ISBN, authors, title, tags, pulication date, languages, publisher and cover.


### Requirements:

You need a personal SRU Access Token. The Token is free of charge.

#### To get a SRU Token fo the following:

- Create a free account at https://portal.dnb.de/myAccount/register.htm
- Write an email to schnittstellen-service@dnb.de and ask them to enable SRU Access Token generation for your account.
- Log in into your DNB account and create an Access Token.
- Enter the Access Token into this plugin's settings page.


### Limitations and caveats

- The returned publication date contains only the year, not the precise date
- `Series` and `Series Index` are not supported
