"""
Contains the ``ReminderCheckbox`` class.
"""

from __future__ import annotations

from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTableWidgetItem


class ReminderCheckbox(QTableWidgetItem):
    """
    A checkbox in the reminders table.
    """
    CB_LIST: List[ReminderCheckbox] = []

    def __init__(self, container_name: str, to_sync: List[str], *args, **kwargs):
        """
        Initialises the reminder checkbox.

        :param container_name: the name of the container this checkbox represents.
        :param to_sync: a list of which reminder containers should be synchronised.
        """
        super().__init__(*args, **kwargs)
        self.container_name: str = container_name
        self.to_sync: List[str] = to_sync
        self.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        self.load_check_state()
        ReminderCheckbox.CB_LIST.append(self)

    @staticmethod
    def reset_list():
        """
        Remove all stored checkboxes.
        """
        ReminderCheckbox.CB_LIST.clear()

    def load_check_state(self):
        """
        Used to determine whether this checkbox should be checked or unchecked when settings are loaded from file.
        """
        self.setCheckState(Qt.CheckState.Checked
                           if self.container_name in self.to_sync
                           else Qt.CheckState.Unchecked)

    def check(self):
        """
        Set this checkbox to checked.
        """
        self.setCheckState(Qt.CheckState.Checked)

    def uncheck(self):
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
