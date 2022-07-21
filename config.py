#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import (unicode_literals, division,
                        absolute_import, print_function)
from calibre.utils.config import JSONConfig
from calibre.gui2.metadata.config import ConfigWidget as DefaultConfigWidget

__license__ = 'GPL v3'
__copyright__ = '2017, Bernhard Geier <geierb@geierb.de>'
__docformat__ = 'restructuredtext en'


from PyQt5.Qt import QLabel, QGridLayout, QGroupBox, QCheckBox, QButtonGroup, QRadioButton

STORE_NAME = 'Options'

KEY_GUESS_SERIES = 'guessSeries'
KEY_APPEND_EDITION_TO_TITLE = 'appendEditionToTitle'
KEY_FETCH_SUBJECTS = 'subjects'

DEFAULT_STORE_VALUES = {
    KEY_GUESS_SERIES: True,
    KEY_APPEND_EDITION_TO_TITLE: False,
    # 0:only gnd   1:prefer gnd 2:both   3:prefer non-gnd   4:only non-gnd   5:none
    KEY_FETCH_SUBJECTS: 2,
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

        # Guess Series
        guess_series_label = QLabel(
            'Guess Series and Series Index from Title:', self)
        guess_series_label.setToolTip('DNB only rarely provides data about a book\'s series.\n'
                                      'This plugin can try to extract series and series_index from the book title.\n')
        other_group_box_layout.addWidget(guess_series_label, 0, 0, 1, 1)

        self.guess_series_checkbox = QCheckBox(self)
        self.guess_series_checkbox.setChecked(
            c.get(KEY_GUESS_SERIES, DEFAULT_STORE_VALUES[KEY_GUESS_SERIES]))
        other_group_box_layout.addWidget(
            self.guess_series_checkbox, 0, 1, 1, 1)

        # Append Edition to Title
        append_edition_to_title_label = QLabel(
            'Append Edition to Title:', self)
        append_edition_to_title_label.setToolTip('For some books DNB has information about the edition.\n'
                                                 'This plugin can fetch this information and append it to the book\'s title,\n'
                                                 'e.g. "Mord am Tegernsee : Ein Bayern-Krimi : 2. Aufl.".\n'
                                                 'Of course this only works reliable if you search for a book with a known unique identifier such as dnb-idn or ISBN.')
        other_group_box_layout.addWidget(
            append_edition_to_title_label, 1, 0, 1, 1)

        self.append_edition_to_title_checkbox = QCheckBox(self)
        self.append_edition_to_title_checkbox.setChecked(c.get(
            KEY_APPEND_EDITION_TO_TITLE, DEFAULT_STORE_VALUES[KEY_APPEND_EDITION_TO_TITLE]))
        other_group_box_layout.addWidget(
            self.append_edition_to_title_checkbox, 1, 1, 1, 1)

        # Fetch Subjects
        fetch_subjects_label = QLabel('Fetch Subjects:', self)
        fetch_subjects_label.setToolTip('DNB provides several types of subjects:\n'
                                        ' - Standardized subjects according to the GND\n'
                                        ' - Subjects delivered by the publisher\n'
                                        'You can choose which ones to fetch.')
        other_group_box_layout.addWidget(fetch_subjects_label, 2, 0, 1, 1)

        self.fetch_subjects_radios_group = QButtonGroup(other_group_box)
        titles = ['only GND subjects', 'GND subjects if available, otherwise non-GND subjects', 'GND and non-GND subjects',
                  'non-GND subjects if available, otherwise GND subjects', 'only non-GND subjects', 'none']
        self.fetch_subjects_radios = [
            QRadioButton(title) for title in titles]
        for i, radio in enumerate(self.fetch_subjects_radios):
            if i == c.get(KEY_FETCH_SUBJECTS, DEFAULT_STORE_VALUES[KEY_FETCH_SUBJECTS]):
                radio.setChecked(True)
            self.fetch_subjects_radios_group.addButton(radio, i)
            other_group_box_layout.addWidget(radio, 2 + i, 1, 1, 1)

    def commit(self):
        DefaultConfigWidget.commit(self)
        new_prefs = {}
        new_prefs[KEY_GUESS_SERIES] = self.guess_series_checkbox.isChecked()
        new_prefs[KEY_APPEND_EDITION_TO_TITLE] = self.append_edition_to_title_checkbox.isChecked()
        new_prefs[KEY_FETCH_SUBJECTS] = self.fetch_subjects_radios_group.checkedId()

        plugin_prefs[STORE_NAME] = new_prefs
