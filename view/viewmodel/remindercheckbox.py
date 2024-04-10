from __future__ import annotations

from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTableWidgetItem


class ReminderCheckbox(QTableWidgetItem):
    CB_LIST: List[ReminderCheckbox] = []

    def __init__(self, container_name: str, to_sync: List[str], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.container_name: str = container_name
        self.to_sync: List[str] = to_sync
        self.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        self.load_check_state()
        ReminderCheckbox.CB_LIST.append(self)

    @staticmethod
    def reset_list():
        ReminderCheckbox.CB_LIST.clear()

    def load_check_state(self):
        self.setCheckState(Qt.CheckState.Checked
                           if self.container_name in self.to_sync
                           else Qt.CheckState.Unchecked)

    def check(self):
        self.setCheckState(Qt.CheckState.Checked)

    def uncheck(self):
        self.setCheckState(Qt.CheckState.Unchecked)

    def is_checked(self) -> bool:
        return self.checkState() == Qt.CheckState.Checked
