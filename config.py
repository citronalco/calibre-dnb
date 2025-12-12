#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import (unicode_literals, division,
                        absolute_import, print_function)
from calibre.utils.config import JSONConfig
from calibre.gui2.metadata.config import ConfigWidget as DefaultConfigWidget

__license__ = 'agpl-3.0'
__copyright__ = '2017, Bernhard Geier <geierb@geierb.de>'
__docformat__ = 'restructuredtext en'


from PyQt5.Qt import QLabel, QGridLayout, QGroupBox, QCheckBox, QButtonGroup, QRadioButton, QPlainTextEdit

STORE_NAME = 'Options'

KEY_GUESS_SERIES = 'guessSeries'
KEY_APPEND_EDITION_TO_TITLE = 'appendEditionToTitle'
KEY_FETCH_SUBJECTS = 'subjects'
KEY_SKIP_SERIES_STARTING_WITH_PUBLISHERS_NAME = 'skipSeriesStartingWithPublishersName'
KEY_UNWANTED_SERIES_NAMES = 'unwantedSeriesNames'

DEFAULT_STORE_VALUES = {
    KEY_GUESS_SERIES: True,
    KEY_APPEND_EDITION_TO_TITLE: False,
    # 0:only gnd   1:prefer gnd 2:both   3:prefer non-gnd   4:only non-gnd   5:none
    KEY_FETCH_SUBJECTS: 2,
    KEY_SKIP_SERIES_STARTING_WITH_PUBLISHERS_NAME: True,
    # unwanted series names
    KEY_UNWANTED_SERIES_NAMES: [r'^Roman$', r'^Science-fiction$', r'^\[Ariadne\]$', r'^Ariadne$', r'^atb$', r'^BvT$',
                                r'^Bastei L', r'^bb$', r'^Beck Paperback', r'^Beck\-.*berater', r'^Beck\'sche Reihe',
                                r'^Bibliothek Suhrkamp$', r'^BLT$', r'^DLV-Taschenbuch$', r'^Edition Suhrkamp$',
                                r'^Edition Lingen Stiftung$', r'^Edition C', r'^Edition Metzgenstein$', r'^ETB$', r'^dtv',
                                r'^Ein Goldmann', r'^Oettinger-Taschenbuch$', r'^Haymon-Taschenbuch$', r'^Mira Taschenbuch$',
                                r'^Suhrkamp-Taschenbuch$', r'^Bastei-L', r'^Hey$', r'^btb$', r'^bt-Kinder', r'^Ravensburger',
                                r'^Sammlung Luchterhand$', r'^blanvalet$', r'^KiWi$', r'^Piper$', r'^C.H. Beck', r'^Rororo',
                                r'^Goldmann$', r'^Moewig$', r'^Fischer Klassik$', r'^hey! shorties$', r'^Ullstein',
                                r'^Unionsverlag', r'^Ariadne-Krimi', r'^C.-Bertelsmann', r'^Phantastische Bibliothek$',
                                r'^Beck Paperback$', r'^Beck\'sche Reihe$', r'^Knaur', r'^Volk-und-Welt', r'^Allgemeine',
                                r'^Premium', r'^Horror-Bibliothek$'],
}

# This is where all preferences for this plugin will be stored
plugin_prefs = JSONConfig('plugins/DNB_DE')
# Set defaults
plugin_prefs.defaults[STORE_NAME] = DEFAULT_STORE_VALUES


class ConfigWidget(DefaultConfigWidget):
    def __init__(self, plugin):
        """
        Show configuration widget
        """
        DefaultConfigWidget.__init__(self, plugin)
        c = plugin_prefs[STORE_NAME]

        other_group_box = QGroupBox('Other options', self)
        self.l.addWidget(other_group_box, self.l.rowCount(), 0, 1, 2)
        other_group_box_layout = QGridLayout()
        other_group_box.setLayout(other_group_box_layout)

        # Guess Series?
        row = 0
        guess_series_label = QLabel(
            'Guess Series and Series Index from Title:', self)
        guess_series_label.setToolTip('DNB only rarely provides data about a book\'s series.\n'
                                      'This plugin can try to extract series and series_index from the book title.\n')
        other_group_box_layout.addWidget(guess_series_label, row, 0, 1, 1)

        self.guess_series_checkbox = QCheckBox(self)
        self.guess_series_checkbox.setChecked(
            c.get(KEY_GUESS_SERIES, DEFAULT_STORE_VALUES[KEY_GUESS_SERIES]))
        other_group_box_layout.addWidget(
            self.guess_series_checkbox, row, 1, 1, 1)

        # Append Edition to Title?
        row += 1
        append_edition_to_title_label = QLabel(
            'Append Edition to Title:', self)
        append_edition_to_title_label.setToolTip('For some books DNB has information about the edition.\n'
                                                 'This plugin can fetch this information and append it to the book\'s title,\n'
                                                 'e.g. "Mord am Tegernsee : Ein Bayern-Krimi : 2. Aufl.".\n'
                                                 'Of course this only works reliable if you search for a book with a known unique identifier such as dnb-idn or ISBN.')
        other_group_box_layout.addWidget(
            append_edition_to_title_label, row, 0, 1, 1)

        self.append_edition_to_title_checkbox = QCheckBox(self)
        self.append_edition_to_title_checkbox.setChecked(c.get(
            KEY_APPEND_EDITION_TO_TITLE, DEFAULT_STORE_VALUES[KEY_APPEND_EDITION_TO_TITLE]))
        other_group_box_layout.addWidget(
            self.append_edition_to_title_checkbox, row, 1, 1, 1)

        # Fetch which type of Subjects?
        row += 1
        fetch_subjects_label = QLabel('Fetch Subjects:', self)
        fetch_subjects_label.setToolTip('DNB provides several types of subjects:\n'
                                        ' - Standardized subjects according to the GND\n'
                                        ' - Subjects delivered by the publisher\n'
                                        'You can choose which ones to fetch.')
        other_group_box_layout.addWidget(fetch_subjects_label, row, 0, 1, 1)

        self.fetch_subjects_radios_group = QButtonGroup(other_group_box)
        titles = ['only GND subjects', 'GND subjects if available, otherwise non-GND subjects', 'GND and non-GND subjects',
                  'non-GND subjects if available, otherwise GND subjects', 'only non-GND subjects', 'none']
        self.fetch_subjects_radios = [
            QRadioButton(title) for title in titles]
        for i, radio in enumerate(self.fetch_subjects_radios):
            if i == c.get(KEY_FETCH_SUBJECTS, DEFAULT_STORE_VALUES[KEY_FETCH_SUBJECTS]):
                radio.setChecked(True)
            self.fetch_subjects_radios_group.addButton(radio, i)
            other_group_box_layout.addWidget(radio, row, 1, 1, 1)
            row += 1

        # Skip series starting with publisher's name?
        row += 1
        skipSeriesStartingWithPublishersName_label = QLabel(
            'Skip series starting with publisher\'s name:', self)
        skipSeriesStartingWithPublishersName_label.setToolTip(_('Skip series info if it starts with the first word of the publisher\'s '
                                                 'name (which must be at least 4 characters long).'))
        other_group_box_layout.addWidget(skipSeriesStartingWithPublishersName_label, row, 0, 1, 1)

        self.skipSeriesStartingWithPublishersName_checkbox = QCheckBox(self)
        self.skipSeriesStartingWithPublishersName_checkbox.setChecked(
            c.get(KEY_SKIP_SERIES_STARTING_WITH_PUBLISHERS_NAME, DEFAULT_STORE_VALUES[KEY_SKIP_SERIES_STARTING_WITH_PUBLISHERS_NAME]))
        other_group_box_layout.addWidget(
            self.skipSeriesStartingWithPublishersName_checkbox, row, 1, 1, 1)

        # Patterns for unwanted series names
        row += 1
        unwantedSeriesNames_label = QLabel(
            'Skip series that match RegEx pattern:', self)
        unwantedSeriesNames_label.setToolTip('RegEx pattern to detect unwanted series names. '
                                          'One pattern per line. Processing is done from top to bottom, and stopped at first match.')
        other_group_box_layout.addWidget(unwantedSeriesNames_label, row, 0, 1, 1)

        self.unwantedSeriesNames_textarea = QPlainTextEdit(self)
        self.unwantedSeriesNames_textarea.setPlainText(
            '\n'.join(c.get(KEY_UNWANTED_SERIES_NAMES, DEFAULT_STORE_VALUES[KEY_UNWANTED_SERIES_NAMES])))
        other_group_box_layout.addWidget(
            self.unwantedSeriesNames_textarea, row, 1, 1, 1)


    def commit(self):
        """
        Save settings
        """
        DefaultConfigWidget.commit(self)
        new_prefs = {}
        new_prefs[KEY_GUESS_SERIES] = self.guess_series_checkbox.isChecked()
        new_prefs[KEY_APPEND_EDITION_TO_TITLE] = self.append_edition_to_title_checkbox.isChecked()
        new_prefs[KEY_FETCH_SUBJECTS] = self.fetch_subjects_radios_group.checkedId()
        new_prefs[KEY_SKIP_SERIES_STARTING_WITH_PUBLISHERS_NAME] = self.skipSeriesStartingWithPublishersName_checkbox.isChecked()
        new_prefs[KEY_UNWANTED_SERIES_NAMES] = self.unwantedSeriesNames_textarea.toPlainText().split("\n")

        plugin_prefs[STORE_NAME] = new_prefs
