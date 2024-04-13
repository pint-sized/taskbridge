from __future__ import annotations

import datetime
import json
import os.path
import re
import sys
from pathlib import Path
from typing import List

import darkdetect
import keyring
import schedule
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import QHeaderView, QTableWidgetItem, QFileDialog, QMessageBox, QMainWindow

from taskbridge import helpers
from taskbridge.notes.controller import NoteController
from taskbridge.notes.model.notefolder import NoteFolder
from taskbridge.reminders.controller import ReminderController
from taskbridge.reminders.model.remindercontainer import ReminderContainer
from view.viewmodel import threadedtasks
from view.viewmodel.mainwindow import MainWindow
from view.viewmodel.notecheckbox import NoteCheckBox
from view.viewmodel.remindercheckbox import ReminderCheckbox


class TaskBridgeApp(QMainWindow):
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
        'reminder_sync': [],
        'log_level': 'debug',
        'autosync': '0',
        'autosync_interval': 0,
        'autosync_unit': 'Minutes'
    }

    PENDING_CHANGES: bool = False

    def __init__(self):
        super().__init__()
        self.reminder_pw_worker = threadedtasks.ReminderPreWarm(self.display_reminders_table)
        self.note_pw_worker = threadedtasks.NotePreWarm(self.display_notes_table)
        self.autosync_worker = None
        self.sync_worker = None
        self.tray_icon = None
        TaskBridgeApp.bootstrap_settings()
        QtCore.QDir.addSearchPath('assets', 'view/assets/')
        self.note_boxes: List = []
        self.reminder_boxes: List = []
        self.ui: MainWindow = MainWindow()

        TaskBridgeApp.load_settings()
        self.logging_worker = threadedtasks.LoggingThread(TaskBridgeApp.SETTINGS['log_level'], log_stdout=True)
        self.logging_worker.log_signal.connect(self.display_log)

        self.login_widgets = [
            self.ui.txt_reminder_username,
            self.ui.txt_reminder_address,
            self.ui.txt_reminder_path,
            self.ui.txt_reminder_password
        ]
        self.bootstrap_ui()
        self.ui.show()

    # GENERAL DECLARATIONS ---------------------------------------------------------------------------------------------

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

    @staticmethod
    def _ask_question(title: str, message: str) -> int:
        ask = QMessageBox()
        ask.setIcon(QMessageBox.Icon.Warning)
        ask.setText(message)
        ask.setWindowTitle(title)
        ask.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        ask.activateWindow()
        action = ask.exec()
        return action

    def save_settings(self, what: str | None = None, silent: bool = True):
        if (what == 'reminders' and not self.ui.cb_reminder_autoprune.isChecked) and not silent:
            title = "Enable Completed Reminder Pruning?"
            message = "You have not selected to automatically prune completed reminders. This can significantly slow the sync process. Do you want to enable automatic completed reminders pruning?"
            action = TaskBridgeApp._ask_question(title, message)
            if action == QMessageBox.StandardButton.Yes:
                self.ui.cb_reminder_autoprune.setChecked(True)
                TaskBridgeApp.SETTINGS['prune_reminders'] = '1'

        with open(helpers.settings_folder() / 'conf.json', 'w') as fp:
            json.dump(TaskBridgeApp.SETTINGS, fp)
        if not silent:
            TaskBridgeApp._show_message("Settings Saved", "Your {} sync settings have been saved.".format(what))
        TaskBridgeApp.PENDING_CHANGES = False

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
        self.bootstrap_sync()
        self.ui.cb_notes_sync.clicked.connect(self.handle_notes_sync)
        self.ui.cb_reminders_sync.clicked.connect(self.handle_reminders_sync)
        self.ui.setWindowIcon(QtGui.QIcon('assets:TaskBridge.png'))
        self.ui.btn_notes_refresh.setIcon(QtGui.QIcon('assets:refresh.png'))
        self.ui.btn_clear_logs.setIcon(QtGui.QIcon('assets:trash.png'))
        self.ui.lbl_sync_graphic.setPixmap(QtGui.QPixmap('assets:TaskBridge.png'))
        self.ui.lbl_sync_graphic.setScaledContents(True)
        self.ui.btn_clear_logs.clicked.connect(self.clear_logs)
        self.ui.tab_container.currentChanged.connect(self.check_changes)
        self.ui.btn_sync_view.clicked.connect(self.switch_sync_view)
        self.ui.cmb_sync_log_level.setCurrentText(TaskBridgeApp.SETTINGS['log_level'].title())
        self.ui.cmb_sync_log_level.currentIndexChanged.connect(self.set_logging_level)
        self.ui.btn_sync.clicked.connect(self.do_sync)

    def clear_logs(self):
        self.ui.txt_log_display.clear()

    def set_logging_level(self):
        log_level = self.ui.cmb_sync_log_level.currentText().lower()
        TaskBridgeApp.SETTINGS['log_level'] = log_level
        if self.logging_worker:
            self.logging_worker.set_logging_level(log_level)
        self.save_settings()

    def switch_sync_view(self):
        if self.ui.stackedWidget.currentIndex() == 0:
            self.ui.stackedWidget.setCurrentIndex(1)
            self.ui.btn_sync_view.setArrowType(Qt.ArrowType.LeftArrow)
        else:
            self.ui.stackedWidget.setCurrentIndex(0)
            self.ui.btn_sync_view.setArrowType(Qt.ArrowType.RightArrow)

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

        # Changing the autosync frequency revalidates the form
        if event.type() == QEvent.Type.FocusOut and widget == self.ui.spn_sync_frequency:
            self.validate_autosync_form()

        return False

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
            self.save_settings()
            self.ui.tbl_notes.setRowCount(0)
            self.ui.gb_notes.setEnabled(False)
            self.ui.frm_notes.setEnabled(False)

    def bootstrap_notes(self):
        self.ui.tbl_notes.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ui.btn_notes_choose.clicked.connect(self.handle_folder_browse)
        self.ui.btn_notes_save.clicked.connect(lambda: self.save_settings("notes", False))
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

        self.ui.btn_sync.setEnabled(False)
        self.note_pw_worker.message_signal.connect(self.display_log)
        self.note_pw_worker.start()

    def display_notes_table(self, folder_list: List[NoteFolder]):
        self.ui.btn_sync.setEnabled(True)
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
        self.ui.btn_reminder_save.clicked.connect(lambda: self.save_settings("reminders", False))
        self.ui.btn_reminder_cancel.clicked.connect(self.handle_reminders_cancel)
        self.ui.btn_reminder_login.clicked.connect(self.handle_login)
        self.ui.tbl_reminders.cellClicked.connect(self.handle_reminder_checkbox)
        for widget in self.login_widgets:
            widget.installEventFilter(self)
        self.ui.rb_server_caldav.clicked.connect(lambda: self.trigger_unsaved("reminders"))
        self.ui.rb_server_nextcloud.clicked.connect(lambda: self.trigger_unsaved("reminders"))
        self.ui.cb_reminder_autoprune.clicked.connect(self.handle_prune_checkbox)
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
        self.ui.btn_sync.setEnabled(False)
        self.reminder_pw_worker.message_signal.connect(self.display_log)
        self.reminder_pw_worker.start()

    def display_reminders_table(self, container_list: List[ReminderContainer]):
        self.ui.btn_sync.setEnabled(True)
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
            if TaskBridgeApp.SETTINGS['prune_reminders'] == '1':
                self.ui.cb_reminder_autoprune.setChecked(True)
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
            self.save_settings()
            self.ui.tbl_reminders.setRowCount(0)
            self.ui.gb_reminders.setEnabled(False)
            self.ui.frm_reminders.setEnabled(False)
            self.ui.frm_caldav_login.setEnabled(False)

    def handle_login(self):
        valid, msg = self.validate_login_form()
        if not valid:
            TaskBridgeApp._show_message("Invalid Login Credentials", msg, 'error')
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

    def handle_prune_checkbox(self):
        TaskBridgeApp.SETTINGS['prune_reminders'] = '1' if self.ui.cb_reminder_autoprune.isChecked() else '0'
        self.trigger_unsaved('reminders')

    # Sync Handling-----------------------------------------------------------------------------------------------------
    def bootstrap_sync(self):
        self.ui.cb_sync_scheduled.clicked.connect(self.handle_sync_toggle)
        self.ui.cmb_sync_frequency.currentIndexChanged.connect(self.validate_autosync_form)
        self.apply_autosync_settings()
        self.ui.spn_sync_frequency.installEventFilter(self)
        self.ui.btn_sync_set_schedule.clicked.connect(self.set_autosync)

    def do_sync(self):
        sync_reminders = TaskBridgeApp.SETTINGS['sync_reminders'] == '1'
        sync_notes = TaskBridgeApp.SETTINGS['sync_notes'] == '1'
        prune_reminders = TaskBridgeApp.SETTINGS['prune_reminders'] == '1'
        if not sync_reminders and not sync_notes:
            TaskBridgeApp._show_message("Nothing to sync", "Both reminder and note sync is disabled, nothing to do!")
            return

        self.ui.btn_sync.setEnabled(False)
        icon_path = "view/assets/bridge_animated_white.gif" if darkdetect.isDark() else "view/assets/bridge_animated_black.png"
        self.tray_icon.set_animated_icon(icon_path)
        self.sync_worker = threadedtasks.Sync(sync_reminders, sync_notes, self.sync_complete, prune_reminders)
        self.sync_worker.message_signal.connect(self.display_log)
        self.sync_worker.progress_signal.connect(self.update_progress)
        self.sync_worker.start()

    def validate_autosync_form(self):
        if self.ui.cmb_sync_frequency.currentText() == 'Minutes':
            self.ui.spn_sync_frequency.setMinimum(10)
            self.ui.spn_sync_frequency.setMaximum(59)
            current_interval = self.ui.spn_sync_frequency.value()
            self.ui.spn_sync_frequency.setValue(current_interval if current_interval >= 10 else 10)
        elif self.ui.cmb_sync_frequency.currentText() == 'Hours':
            self.ui.spn_sync_frequency.setMinimum(1)
            self.ui.spn_sync_frequency.setMaximum(12)
            current_interval = self.ui.spn_sync_frequency.value()
            self.ui.spn_sync_frequency.setValue(current_interval if current_interval <= 12 else 12)

    def set_autosync(self):
        interval = self.ui.spn_sync_frequency.value()
        unit = self.ui.cmb_sync_frequency.currentText()
        TaskBridgeApp.SETTINGS['autosync'] = '1'
        TaskBridgeApp.SETTINGS['autosync_interval'] = interval
        TaskBridgeApp.SETTINGS['autosync_unit'] = unit
        self.save_settings()
        self.start_autosync(interval, unit)

    def start_autosync(self, interval: int, unit: str):
        seconds = 0
        delta = 0
        if unit == 'Minutes':
            seconds = interval * 60
            delta = datetime.timedelta(minutes=interval)
        if unit == 'Hours':
            seconds = interval * 60 * 60
            delta = datetime.timedelta(hours=interval)

        if self.autosync_worker:
            self.autosync_worker.set()
        schedule.clear()

        schedule.every(seconds).seconds.do(self.do_sync)
        self.autosync_worker = threadedtasks.run_continuously()
        next_sync = datetime.datetime.now() + delta
        self.ui.lbl_sync_status.setText('Next Sync at {}.'.format(next_sync.strftime('%H:%M:%S')))

    def apply_autosync_settings(self):
        if TaskBridgeApp.SETTINGS['autosync'] == '1':
            interval = TaskBridgeApp.SETTINGS['autosync_interval']
            unit = TaskBridgeApp.SETTINGS['autosync_unit']
            self.start_autosync(interval, unit)
            self.ui.spn_sync_frequency.setValue(interval)
            self.ui.cmb_sync_frequency.setCurrentText(unit)
            self.ui.cb_sync_scheduled.setChecked(True)
            self.ui.gb_autosync.setEnabled(True)

    def handle_sync_toggle(self):
        if self.ui.cb_sync_scheduled.isChecked():
            self.ui.gb_autosync.setEnabled(True)
        else:
            self.ui.gb_autosync.setEnabled(False)
            if self.autosync_worker:
                self.autosync_worker.set()
            schedule.clear()
            self.ui.spn_sync_frequency.setValue(0)
            self.ui.cmb_sync_frequency.setCurrentText("Minutes")
            TaskBridgeApp.SETTINGS['autosync'] = '0'
            self.save_settings()

    # Tray Handling-----------------------------------------------------------------------------------------------------
    def quit_gracefully(self):
        if self.reminder_pw_worker:
            self.reminder_pw_worker.quit()
        if self.note_pw_worker:
            self.note_pw_worker.quit()
        if self.autosync_worker:
            self.autosync_worker.set()
        if self.logging_worker:
            self.logging_worker.quit()
        if self.sync_worker:
            self.sync_worker.quit()
        schedule.clear()
        sys.exit(0)

    # Thread Handling---------------------------------------------------------------------------------------------------
    def update_status(self, status: str = "Currently idle."):
        self.ui.lbl_sync_status.setText(status)

    def display_log(self, message: str):
        self.ui.txt_log_display.append(message)
        self.ui.txt_log_display.verticalScrollBar().setValue(self.ui.txt_log_display.verticalScrollBar().maximum())

    def update_progress(self, progress: int):
        self.ui.progressBar.setValue(progress)

    def sync_complete(self):
        icon_path = "view/assets/bridge_white.png" if darkdetect.isDark() else "view/assets/bridge_white.png"
        self.tray_icon.setIcon(QtGui.QIcon(icon_path))
        self.ui.btn_sync.setEnabled(True)
        if TaskBridgeApp.SETTINGS['autosync'] == '1':
            current_time = datetime.datetime.now()
            next_sync = current_time + datetime.timedelta(0, TaskBridgeApp.SETTINGS['autosync_interval'])
            self.ui.lbl_sync_status.setText('Synchronisation completed at {0}. Next Sync at {1}.'.format(
                current_time.strftime('%H:%M:%S'),
                next_sync.strftime('%H:%M:%S')
            ))
        else:
            self.ui.lbl_sync_status.setText("Synchronisation Complete!")
