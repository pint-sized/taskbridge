from __future__ import annotations

import json
import os.path
import re
from pathlib import Path
from threading import Thread
from typing import List

import keyring
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QApplication, QHeaderView, QTableWidgetItem, QFileDialog, QMessageBox

from taskbridge import helpers
from taskbridge.notes.controller import NoteController
from taskbridge.notes.model.notefolder import NoteFolder
from taskbridge.reminders.controller import ReminderController
from taskbridge.reminders.model.remindercontainer import ReminderContainer
from view.viewmodel import threadedtasks
from view.viewmodel.mainwindow import MainWindow
from view.viewmodel.notecheckbox import NoteCheckBox
from view.viewmodel.remindercheckbox import ReminderCheckbox


class TaskBridgeApp(QApplication):
    SETTINGS = {
        'sync_notes': '0',
        'remote_notes_folder': '',
        'associations': {
            'bi_directional': [],
            'local_to_remote': [],
            'remote_to_local': []
        },
        'sync_reminders': '0',
        'prune_reminders': '0',
        'caldav_server': '',
        'caldav_path': '',
        'caldav_url': '',
        'caldav_username': '',
        'caldav_type': '',
        'reminder_sync': []
    }

    PENDING_CHANGES: bool = False

    def __init__(self, argv: List[str]):
        super().__init__(argv)
        TaskBridgeApp.bootstrap_settings()
        QtCore.QDir.addSearchPath('assets', 'view/assets/')
        self.note_boxes: List = []
        self.reminder_boxes: List = []
        self.ui: MainWindow = MainWindow()

        TaskBridgeApp.load_settings()
        self.login_widgets = [
            self.ui.txt_reminder_username,
            self.ui.txt_reminder_address,
            self.ui.txt_reminder_path,
            self.ui.txt_reminder_password
        ]
        self.bootstrap_ui()
        self.ui.show()
        self.exec()

    # GENERAL DECLARATIONS ---------------------------------------------------------------------------------------------

    @staticmethod
    def save_settings(what: str | None = None, silent: bool = True):
        with open(helpers.settings_folder() / 'conf.json', 'w') as fp:
            json.dump(TaskBridgeApp.SETTINGS, fp)
        if not silent:
            TaskBridgeApp._show_message("Settings Saved", "Your {} sync settings have been saved.".format(what))
        TaskBridgeApp.PENDING_CHANGES = False

    @staticmethod
    def bootstrap_settings():
        conf_file = helpers.settings_folder() / 'conf.json'
        if not os.path.exists(conf_file):
            with open(helpers.settings_folder() / 'conf.json', 'w') as fp:
                json.dump(TaskBridgeApp.SETTINGS, fp)

    @staticmethod
    def load_settings():
        conf_file = helpers.settings_folder() / 'conf.json'
        if not os.path.exists(conf_file):
            return
        with open(helpers.settings_folder() / 'conf.json', 'r') as fp:
            TaskBridgeApp.SETTINGS = json.load(fp)

    @staticmethod
    def _show_message(title: str, message: str, message_type: str = 'info'):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical if message_type == 'error' else QMessageBox.Icon.Information)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def trigger_unsaved(self, view: str):
        TaskBridgeApp.PENDING_CHANGES = True
        if view == 'notes':
            self.ui.frm_notes.setEnabled(True)
        elif view == 'reminders':
            self.ui.frm_reminders.setEnabled(True)

    def bootstrap_ui(self):
        self.ui.tab_container.setCurrentIndex(0)
        self.ui.stackedWidget.setCurrentIndex(0)
        self.ui.tbl_notes.setRowCount(0)
        self.note_boxes.clear()
        self.reminder_boxes.clear()
        self.bootstrap_notes()
        self.bootstrap_reminders()
        self.ui.cb_notes_sync.clicked.connect(self.handle_notes_sync)
        self.ui.cb_reminders_sync.clicked.connect(self.handle_reminders_sync)
        self.ui.btn_notes_refresh.setIcon(QtGui.QIcon('assets:refresh.png'))
        self.ui.tab_container.currentChanged.connect(self.check_changes)

    def check_changes(self):
        if not TaskBridgeApp.PENDING_CHANGES:
            return

        ask = QMessageBox()
        ask.setIcon(QMessageBox.Icon.Warning)
        ask.setText("You have unsaved changes. What would you like to do?")
        ask.setWindowTitle("Unsaved Changes")
        ask.setStandardButtons(QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard)
        ask.activateWindow()
        action = ask.exec()

        if action == QMessageBox.StandardButton.Save:
            self.save_settings()
        elif action == QMessageBox.StandardButton.Discard:
            self.ui.frm_notes.setEnabled(False)
            self.ui.frm_reminders.setEnabled(False)
            self.load_settings()
            self.refresh_reminders()
            self.refresh_notes()
            TaskBridgeApp.PENDING_CHANGES = False

    # NOTE HANDLING ----------------------------------------------------------------------------------------------------
    @staticmethod
    def set_note_folder_association(folder_name: str, direction: str | None = None):
        assoc = TaskBridgeApp.SETTINGS['associations']
        for sync_direction in assoc.keys():
            if folder_name in assoc[sync_direction]:
                assoc[sync_direction].remove(folder_name)

        if direction is not None:
            assoc[direction].append(folder_name)

    def handle_notes_sync(self):
        if self.ui.cb_notes_sync.isChecked():
            TaskBridgeApp.SETTINGS['sync_notes'] = '1'
            if TaskBridgeApp.SETTINGS['remote_notes_folder'] == '':
                TaskBridgeApp._show_message("No Remote Folder", "Please select your remote notes folder.")
                self.handle_folder_browse()
            self.bootstrap_notes()
            self.ui.gb_notes.setEnabled(True)
        else:
            TaskBridgeApp.SETTINGS['sync_notes'] = '0'
            TaskBridgeApp.SETTINGS['remote_notes_folder'] = ''
            TaskBridgeApp.SETTINGS['associations']['bi_directional'].clear()
            TaskBridgeApp.SETTINGS['associations']['local_to_remote'].clear()
            TaskBridgeApp.SETTINGS['associations']['remote_to_local'].clear()
            TaskBridgeApp.save_settings()
            self.ui.tbl_notes.setRowCount(0)
            self.ui.gb_notes.setEnabled(False)
            self.ui.frm_notes.setEnabled(False)

    def bootstrap_notes(self):
        self.ui.tbl_notes.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ui.btn_notes_choose.clicked.connect(self.handle_folder_browse)
        self.ui.btn_notes_save.clicked.connect(lambda: TaskBridgeApp.save_settings("notes", False))
        self.ui.btn_notes_cancel.clicked.connect(self.handle_notes_cancel)
        self.ui.btn_notes_refresh.clicked.connect(self.load_note_folders)
        self.ui.tbl_notes.cellClicked.connect(self.handle_note_checkbox)

        self.refresh_notes()

    def refresh_notes(self):
        self.ui.tbl_notes.setRowCount(0)
        self.apply_notes_settings()
        self.ui.cb_notes_sync.setChecked(TaskBridgeApp.SETTINGS['sync_notes'] == '1')
        remote_path = TaskBridgeApp.SETTINGS['remote_notes_folder']
        if remote_path == '':
            self.ui.cb_notes_sync.setChecked(False)
            return
        self.ui.gb_notes.setEnabled(True)
        self.load_note_folders()

    def apply_notes_settings(self):
        if TaskBridgeApp.SETTINGS['sync_notes'] == '1':
            self.ui.txt_notes_folder.setText(str(TaskBridgeApp.SETTINGS['remote_notes_folder']))
            if TaskBridgeApp.SETTINGS['prune_reminders'] == '1':
                self.ui.cb_reminder_autoprune.setChecked(True)
            self.ui.cb_notes_sync.setChecked(True)
        else:
            self.ui.cb_notes_sync.setChecked(True)
            self.ui.gb_notes.setEnabled(False)
            self.ui.frm_notes.setEnabled(False)

    def load_note_folders(self):
        # Set fields
        NoteController.REMOTE_NOTE_FOLDER = Path(TaskBridgeApp.SETTINGS['remote_notes_folder'])
        NoteController.ASSOCIATIONS = TaskBridgeApp.SETTINGS['associations']

        note_thread = Thread(target=threadedtasks.pre_warm_notes, args=[self, self.display_notes_table])
        note_thread.start()

    def display_notes_table(self, folder_list: List[NoteFolder]):
        # Display folders in table
        self.ui.tbl_notes.setRowCount(0)
        NoteCheckBox.CB_LIST.clear()
        row = 0
        NoteCheckBox.reset_list()
        for folder in folder_list:
            if folder.local_folder is not None and folder.remote_folder is None:
                name = folder.local_folder.name
                location = 'Local'
            elif folder.local_folder is None and folder.remote_folder is not None:
                name = folder.remote_folder.name
                location = 'Remote'
            elif folder.local_folder is not None and folder.remote_folder is not None:
                name = folder.local_folder.name
                location = 'Local & Remote'
            else:
                # TODO show some sort of error
                return

            assoc = TaskBridgeApp.SETTINGS['associations']
            self.ui.tbl_notes.insertRow(row)
            self.ui.tbl_notes.setItem(row, 0, QTableWidgetItem(name))
            self.ui.tbl_notes.setItem(row, 1, QTableWidgetItem(location))
            self.ui.tbl_notes.setItem(row, 2, NoteCheckBox(check_type='local_to_remote', location=location,
                                                           folder_name=name, associations=assoc))
            self.ui.tbl_notes.setItem(row, 3, NoteCheckBox(check_type='remote_to_local', location=location,
                                                           folder_name=name, associations=assoc))
            self.ui.tbl_notes.setItem(row, 4, NoteCheckBox(check_type='bi_directional', location=location,
                                                           folder_name=name, associations=assoc))

    def handle_note_checkbox(self, row, col):
        self.ui.tbl_notes.setUpdatesEnabled(False)
        item = self.ui.tbl_notes.item(row, col)
        if not isinstance(item, NoteCheckBox):
            return

        check_group = {item.check_type: item}
        for key in [k for k in NoteCheckBox.CHECK_TYPES if k not in check_group.keys()]:
            check_group[key] = next((cb for cb in NoteCheckBox.CB_LIST if
                                     cb.location == item.location and
                                     cb.folder_name == item.folder_name and
                                     cb.check_type == key),
                                    None)

        if item.is_checked():
            if item.check_type == 'bi_directional':
                TaskBridgeApp.set_note_folder_association(item.folder_name, 'bi_directional')
                check_group['local_to_remote'].uncheck()
                check_group['remote_to_local'].uncheck()
            elif item.check_type == 'remote_to_local':
                if check_group['local_to_remote'].is_checked():
                    TaskBridgeApp.set_note_folder_association(item.folder_name, 'bi_directional')
                    item.uncheck()
                    check_group['local_to_remote'].uncheck()
                    check_group['bi_directional'].check()
                else:
                    TaskBridgeApp.set_note_folder_association(item.folder_name, 'remote_to_local')
                    check_group['bi_directional'].uncheck()
            elif item.check_type == 'local_to_remote':
                if check_group['remote_to_local'].is_checked():
                    TaskBridgeApp.set_note_folder_association(item.folder_name, 'bi_directional')
                    item.uncheck()
                    check_group['remote_to_local'].uncheck()
                    check_group['bi_directional'].check()
                else:
                    TaskBridgeApp.set_note_folder_association(item.folder_name, 'local_to_remote')
                    check_group['bi_directional'].uncheck()

        self.ui.tbl_notes.setUpdatesEnabled(True)
        self.trigger_unsaved('notes')

    def handle_folder_browse(self):
        remote_notes_folder = QFileDialog.getExistingDirectory(None, 'Select Remote Notes Folder')
        TaskBridgeApp.SETTINGS['remote_notes_folder'] = remote_notes_folder
        self.ui.txt_notes_folder.setText(remote_notes_folder)
        TaskBridgeApp.PENDING_CHANGES = True

    def handle_notes_cancel(self):
        # TODO show confirmation dialog
        TaskBridgeApp.load_settings()
        self.apply_notes_settings()
        self.load_note_folders()

    # REMINDER HANDLING ------------------------------------------------------------------------------------------------
    def bootstrap_reminders(self):
        self.ui.tbl_reminders.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ui.btn_reminder_save.clicked.connect(lambda: TaskBridgeApp.save_settings("reminders", False))
        self.ui.btn_reminder_cancel.clicked.connect(self.handle_reminders_cancel)
        self.ui.btn_reminder_login.clicked.connect(self.handle_login)
        self.ui.tbl_reminders.cellClicked.connect(self.handle_reminder_checkbox)
        for widget in self.login_widgets:
            widget.installEventFilter(self)
        self.ui.rb_server_caldav.clicked.connect(lambda: self.trigger_unsaved("reminders"))
        self.ui.rb_server_nextcloud.clicked.connect(lambda: self.trigger_unsaved("reminders"))
        self.ui.cb_reminder_autoprune.clicked.connect(lambda: self.trigger_unsaved("reminders"))
        self.refresh_reminders()

    def refresh_reminders(self):
        self.ui.tbl_reminders.setRowCount(0)
        self.ui.btn_reminder_login.setEnabled(self.validate_login_form()[0])
        self.apply_reminders_settings()
        self.ui.cb_reminders_sync.setChecked(TaskBridgeApp.SETTINGS['sync_reminders'] == '1')
        caldav_username = TaskBridgeApp.SETTINGS['caldav_username']
        if caldav_username == '':
            self.ui.cb_reminders_sync.setChecked(False)
            return
        else:
            self.load_reminder_lists()
            self.ui.gb_reminders.setEnabled(True)
            self.ui.frm_caldav_login.setEnabled(True)

    def load_reminder_lists(self):
        # Set fields
        ReminderController.CALDAV_USERNAME = TaskBridgeApp.SETTINGS['caldav_username']
        ReminderController.CALDAV_URL = TaskBridgeApp.SETTINGS['caldav_url']
        ReminderController.CALDAV_HEADERS = {}
        ReminderController.CALDAV_PASSWORD = keyring.get_password("TaskBridge", "CALDAV-PWD")
        ReminderController.TO_SYNC = TaskBridgeApp.SETTINGS['reminder_sync']

        # Pre-Warm Reminders
        reminder_thread = Thread(target=threadedtasks.pre_warm_reminders, args=[self, self.display_reminders_table])
        reminder_thread.start()

    def display_reminders_table(self, container_list: List[ReminderContainer]):
        # Display containers in table
        self.ui.tbl_reminders.setRowCount(0)
        row = 0
        for container in container_list:
            if container.local_list is not None and container.remote_calendar is None:
                name = container.local_list.name
                location = 'Local'
            elif container.local_list is None and container.remote_calendar is not None:
                name = container.remote_calendar.name
                location = 'Remote'
            elif container.local_list is not None and container.remote_calendar is not None:
                name = container.local_list.name
                location = 'Local & Remote'
            else:
                # TODO show some sort of error
                return

            cbox = ReminderCheckbox(name, TaskBridgeApp.SETTINGS['reminder_sync'])
            self.ui.tbl_reminders.insertRow(row)
            self.ui.tbl_reminders.setItem(row, 0, QTableWidgetItem(name))
            self.ui.tbl_reminders.setItem(row, 1, QTableWidgetItem(location))
            self.ui.tbl_reminders.setItem(row, 2, cbox)

    def apply_reminders_settings(self):
        if TaskBridgeApp.SETTINGS['sync_reminders'] == '1':
            self.ui.txt_reminder_username.setText(TaskBridgeApp.SETTINGS['caldav_username'])
            self.ui.txt_reminder_address.setText(TaskBridgeApp.SETTINGS['caldav_server'])
            self.ui.txt_reminder_path.setText(TaskBridgeApp.SETTINGS['caldav_path'])
            self.ui.txt_reminder_password.setText(keyring.get_password("TaskBridge", "CALDAV-PWD"))
            if TaskBridgeApp.SETTINGS['caldav_type'] == 'NextCloud' or TaskBridgeApp.SETTINGS['caldav_type'] == '':
                self.ui.rb_server_nextcloud.setChecked(True)
                self.ui.rb_server_caldav.setChecked(False)
            else:
                self.ui.rb_server_caldav.setChecked(True)
                self.ui.rb_server_nextcloud.setChecked(False)
            self.ui.cb_reminders_sync.setChecked(True)
        else:
            self.ui.cb_reminders_sync.setChecked(False)
            self.ui.frm_reminders.setEnabled(False)
            self.ui.frm_caldav_login.setEnabled(False)
            self.ui.gb_reminders.setEnabled(False)

    def validate_login_form(self) -> tuple[bool, str]:
        error = ""
        missing = []

        if not self.ui.txt_reminder_username.text():
            missing.append('username')
        if not self.ui.txt_reminder_address.text():
            missing.append('server address')
        if not self.ui.txt_reminder_path.text():
            missing.append('tasks path')
        if not self.ui.txt_reminder_password.text():
            missing.append('password')

        is_valid = len(missing) == 0
        if not is_valid:
            error = "The {0} {1} missing.\n".format(', '.join(missing), 'is' if len(missing) == 1 else 'are')

        full_path = ''
        if self.ui.txt_reminder_address.text():
            url_regex = re.compile(r'https?://(?:www\.)?[a-zA-Z0-9./]+')
            server_address = self.ui.txt_reminder_address.text().strip('/')
            task_path = self.ui.txt_reminder_path.text().strip('/')
            if not task_path.startswith('/'):
                task_path = '/' + task_path
            full_path = server_address + task_path
            if not url_regex.match(full_path):
                error += "Server address or task path are not in the right format.\n"
                is_valid = False

        return is_valid, full_path if is_valid else error

    def handle_reminders_cancel(self):
        pass

    def handle_reminders_sync(self):
        if self.ui.cb_reminders_sync.isChecked():
            TaskBridgeApp.SETTINGS['sync_reminders'] = '1'

            if TaskBridgeApp.SETTINGS['caldav_url'] == '':
                TaskBridgeApp._show_message("Login To CalDav", "Please configure your CalDav login.")
                self.ui.frm_caldav_login.setEnabled(True)
        else:
            TaskBridgeApp.SETTINGS['sync_reminders'] = '0'
            TaskBridgeApp.SETTINGS['caldav_url'] = ''
            TaskBridgeApp.SETTINGS['caldav_username'] = ''
            TaskBridgeApp.SETTINGS['reminder_sync'].clear()
            TaskBridgeApp.save_settings()
            self.ui.tbl_reminders.setRowCount(0)
            self.ui.gb_reminders.setEnabled(False)
            self.ui.frm_reminders.setEnabled(False)
            self.ui.frm_caldav_login.setEnabled(False)

    def handle_login(self):
        valid, msg = self.validate_login_form()
        if not valid:
            self._show_message("Invalid Login Credentials", msg, 'error')
            return

        TaskBridgeApp.SETTINGS['caldav_username'] = self.ui.txt_reminder_username.text()
        TaskBridgeApp.SETTINGS['caldav_server'] = self.ui.txt_reminder_address.text()
        TaskBridgeApp.SETTINGS['caldav_path'] = self.ui.txt_reminder_path.text()
        TaskBridgeApp.SETTINGS['caldav_url'] = msg
        TaskBridgeApp.SETTINGS['caldav_type'] = 'NextCloud' if self.ui.rb_server_nextcloud.isChecked() else 'CalDav'
        keyring.set_password("TaskBridge", "CALDAV-PWD", self.ui.txt_reminder_password.text())

        self.load_reminder_lists()
        self.ui.gb_reminders.setEnabled(True)
        self.trigger_unsaved('reminders')

    def handle_reminder_checkbox(self, row: int, col: int):
        cbox = self.ui.tbl_reminders.item(row, col)
        if not isinstance(cbox, ReminderCheckbox):
            return

        if cbox.is_checked():
            TaskBridgeApp.SETTINGS['reminder_sync'].append(cbox.container_name)
        else:
            TaskBridgeApp.SETTINGS['reminder_sync'].remove(cbox.container_name)

        TaskBridgeApp.PENDING_CHANGES = True

    def eventFilter(self, widget, event):
        # Focusing out of any login form widget validates the form (to enable/disable login button)
        if event.type() == QEvent.Type.FocusOut and widget in self.login_widgets:
            self.ui.btn_reminder_login.setEnabled(self.validate_login_form()[0])

        # Tabbing out of username with a NextCloud server automatically populates the reminder path
        if widget == self.ui.txt_reminder_username and self.ui.txt_reminder_username.text() and self.ui.rb_server_nextcloud.isChecked():
            self.ui.txt_reminder_path.setText('/remote.php/dav/calendars/{}'.format(self.ui.txt_reminder_username.text()))

        # Tabbing out of the password field triggers the login button being enabled
        if event.type() == QEvent.Type.KeyRelease and widget == self.ui.txt_reminder_password:
            self.ui.btn_reminder_login.setEnabled(self.validate_login_form()[0])

        # Making changes to the reminder login form triggers unsaved changes
        if event.type() == QEvent.Type.KeyRelease and widget in self.login_widgets:
            TaskBridgeApp.PENDING_CHANGES = True

        return False

    # Thread Handling---------------------------------------------------------------------------------------------------
    def update_status(self, status: str = "Currently idle."):
        self.ui.lbl_sync_status.setText(status)
