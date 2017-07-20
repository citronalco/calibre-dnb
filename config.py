#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__   = 'GPL v3'
__copyright__ = '2017, Bernhard Geier <geierb@geierb.de>'
__docformat__ = 'restructuredtext en'

try:
    from PyQt5 import Qt as QtGui
except ImportError:
    from PyQt4 import QtGui
try:
    from PyQt5.Qt import QLabel, QGridLayout, Qt, QGroupBox, QCheckBox
except ImportError:
    from PyQt4.Qt import QLabel, QGridLayout, Qt, QGroupBox, QCheckBox

from calibre.gui2.metadata.config import ConfigWidget as DefaultConfigWidget
from calibre.utils.config import JSONConfig

STORE_NAME = 'Options'
KEY_SRUTOKEN = 'sruToken'

DEFAULT_STORE_VALUES = {
    KEY_SRUTOKEN: 'enter-your-sru-token-here'
}

# This is where all preferences for this plugin will be stored
plugin_prefs = JSONConfig('plugins/DNB_DE')
# Set defaults
plugin_prefs.defaults[STORE_NAME] = DEFAULT_STORE_VALUES

class ConfigWidget(DefaultConfigWidget):
    def __init__(self, plugin):
	DefaultConfigWidget.__init__(self, plugin)
	c = plugin_prefs[STORE_NAME]

	other_group_box = QGroupBox('Other options', self)
	self.l.addWidget(other_group_box, self.l.rowCount(), 0, 1, 2)
	other_group_box_layout = QGridLayout()
	other_group_box.setLayout(other_group_box_layout)

	sru_token_label = QLabel('SRU Token:', self)
	sru_token_label.setToolTip('To access the API of the DNB a personal SRU access token is required.\n'
                             'The token is for free.\n\n'
                             'To get a token, create an account at https://portal.dnb.de/myAccount/register.htm \n'
                             'After that write an email to schnittstellen-service@dnb.de and ask them to enable \n'
                             'SRU token generation for your account.')
	other_group_box_layout.addWidget(sru_token_label, 0, 0, 1, 1)

	self.sru_token_line = QtGui.QLineEdit(self)
	self.sru_token_line.setText(c.get(KEY_SRUTOKEN, DEFAULT_STORE_VALUES[KEY_SRUTOKEN]))
	other_group_box_layout.addWidget(self.sru_token_line, 0, 1, 1, 1)

    def commit(self):
	DefaultConfigWidget.commit(self)
	new_prefs = {}
	new_prefs[KEY_SRUTOKEN] = self.sru_token_line.text()
	plugin_prefs[STORE_NAME] = new_prefs
