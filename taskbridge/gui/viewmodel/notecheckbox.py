"""
Contains the ``NoteCheckbox`` class.
"""

from __future__ import annotations

from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTableWidgetItem


class NoteCheckBox(QTableWidgetItem):
    """
    A checkbox in the notes table. Implements logic as follows:

    - If 'local_to_remote' or 'remote_to_local' are checked alone, 'bidirectional' is unchecked.
    - If 'local_to_remote' or 'remote_to_local' are both checked, they are unchecked and 'bidirectional' is checked.
    - If 'bidirectional' is checked, all other checkboxes are unchecked.

    """

    #: Types of checkboxes in the notes table
    CHECK_TYPES = ['local_to_remote', 'remote_to_local', 'bi_directional']
    #: List of checkboxes in the notes table
    CB_LIST: List[NoteCheckBox] = []

    def __init__(self, check_type: str, location: str, folder_name: str, associations: dict, *args, **kwargs):
        """
        Initialises the note checkbox.

        :param check_type: the type of checkbox from :py:att``CHECK_TYPES`` above.
        :param location: whether this checkbox represents a 'local' or 'remote' folder.
        :param folder_name: the name of the folder this checkbox represents.
        :param associations: a dictionary of folder associations as chosen by the user.
        """
        super().__init__(*args, **kwargs)
        self.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        self.check_type: str = check_type
        self.location: str = location
        self.folder_name: str = folder_name
        self.associations: dict = associations
        self.load_check_state()
        NoteCheckBox.CB_LIST.append(self)

    @staticmethod
    def reset_list() -> None:
        """
        Remove all stored checkboxes.
        """
        NoteCheckBox.CB_LIST.clear()

    def load_check_state(self) -> None:
        """
        Used to determine whether this checkbox should be checked or unchecked when settings are loaded from file.
        """
        self.setCheckState(Qt.CheckState.Checked
                           if self.folder_name in self.associations[self.check_type]
                           else Qt.CheckState.Unchecked)

    def check(self) -> None:
        """
        Set this checkbox to checked.
        """
        self.setCheckState(Qt.CheckState.Checked)

    def uncheck(self) -> None:
        """
        Set this checkbox to unchecked.
        """
        self.setCheckState(Qt.CheckState.Unchecked)

    def is_checked(self) -> bool:
        """
        Returns the check state of this checkbox.

        :return: True if this checkbox is checked.
        """
        return self.checkState() == Qt.CheckState.Checked
