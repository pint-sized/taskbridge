from __future__ import annotations

from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTableWidgetItem


class NoteCheckBox(QTableWidgetItem):
    CHECK_TYPES = ['local_to_remote', 'remote_to_local', 'bi_directional']
    CB_LIST: List[NoteCheckBox] = []

    def __init__(self, check_type: str, location: str, folder_name: str, associations: dict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        self.check_type: str = check_type
        self.location: str = location
        self.folder_name: str = folder_name
        self.associations: dict = associations
        self.load_check_state()
        NoteCheckBox.CB_LIST.append(self)

    @staticmethod
    def reset_list():
        NoteCheckBox.CB_LIST.clear()

    def load_check_state(self):
        self.setCheckState(Qt.CheckState.Checked
                           if self.folder_name in self.associations[self.check_type]
                           else Qt.CheckState.Unchecked)

    def check(self):
        self.setCheckState(Qt.CheckState.Checked)

    def uncheck(self):
        self.setCheckState(Qt.CheckState.Unchecked)

    def is_checked(self) -> bool:
        return self.checkState() == Qt.CheckState.Checked
