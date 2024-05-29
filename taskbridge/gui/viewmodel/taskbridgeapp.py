"""
Contains the main view controller for the main window of the app.
"""

from __future__ import annotations

import datetime
import json
import os.path
import re
import sys
import webbrowser
from pathlib import Path
from typing import List

import darkdetect
import keyring
import schedule
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import QEvent, Qt, QSize
from PyQt6.QtGui import QIcon, QKeyEvent
from PyQt6.QtWidgets import QHeaderView, QTableWidgetItem, QFileDialog, QMessageBox, QMainWindow, QDialog, QWidget

from taskbridge import helpers
from taskbridge.gui.viewmodel.ui_aboutwindow import Ui_Dialog
from taskbridge.notes.controller import NoteController
from taskbridge.notes.model.notefolder import NoteFolder
from taskbridge.reminders.controller import ReminderController
from taskbridge.reminders.model.remindercontainer import ReminderContainer
from taskbridge.gui.viewmodel import threadedtasks
from taskbridge.gui.viewmodel.mainwindow import MainWindow
from taskbridge.gui.viewmodel.notecheckbox import NoteCheckBox
from taskbridge.gui.viewmodel.remindercheckbox import ReminderCheckbox


class TaskBridgeApp(QMainWindow):
    """
    View controller for the main window. The :py:att``SETTINGS`` dictionary accepts the following keys:

    - ``sync_notes`` - if '1', notes are synchronised and corresponding configuration is enabled.
    - ``sync_reminders`` - if '1', reminders are synchronised and corresponding configuration is enabled.
    - ``remote_notes_folder`` - path to the remote note folder.
    - ``associations`` - dictionary which contains list of notes to be synced bidirectionally in ``bi_directional`` and
    others in ``local_to_remote`` and ``remote_to_local`` respectively.
    - ``prune_reminders`` - if '1', completed reminders are deleted before synchronisation.
    - ``caldav_server`` - host of the CalDav server.
    - ``caldav_path`` - path to the calendar list for this user on the CalDav server.
    - ``caldav_url`` - automatically set by combining ``caldav_server`` and ``caldav_path``.
    - ``caldav_username`` - username for the CalDav server.
    - ``caldav_type`` - stores either 'NextCloud' or 'CalDav' and enables appropriate settings in GUI.
    - ``reminder_sync`` - list of reminder contains to be synchronised.
    - ``log_level`` - the logging level. Can be 'debug', 'info', 'warning' or 'critical'.
    - ``autosync`` - if '1', automatic synchronisation is enabled.
    - ``autosync_interval`` - the interval for automatic synchronisation.
    - ``autosync_unit`` - determines the unit for ``autosync_interval``. Either 'Minutes' or 'Hours'.

    """

    #: Application settings
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

    #: If True, there are unsaved changes.
    PENDING_CHANGES: bool = False

    def __init__(self, assets_path: str):
        """
        Initialise the window and load settings.

        :param assets_path: Path to the GUI assets folder

        """

        super().__init__()
        self.reminder_pw_worker = threadedtasks.ReminderPreWarm(self.display_reminders_table)
        self.note_pw_worker = threadedtasks.NotePreWarm(self.display_notes_table)
        self.autosync_worker = None
        self.sync_worker = None
        self.tray_icon = None
        self.assets_path: str = assets_path
        TaskBridgeApp.bootstrap_settings()
        QtCore.QDir.addSearchPath('assets', assets_path)
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
    def bootstrap_settings() -> None:
        """
        Create configuration file if it doesn't exist.
        """
        conf_file = helpers.settings_folder() / 'conf.json'
        if not os.path.exists(conf_file):
            with open(helpers.settings_folder() / 'conf.json', 'w') as fp:
                json.dump(TaskBridgeApp.SETTINGS, fp)

    @staticmethod
    def load_settings() -> None:
        """
        Load settings from configuration file.
        """
        conf_file = helpers.settings_folder() / 'conf.json'
        if not os.path.exists(conf_file):
            return
        with open(helpers.settings_folder() / 'conf.json') as fp:
            TaskBridgeApp.SETTINGS = json.load(fp)

    @staticmethod
    def _show_message(title: str, message: str, message_type: str = 'info') -> None:
        """
        Show an informational or error message.

        :param title: window title for the message dialog.
        :param message: message to show.
        :param message_type: the type of message. Either 'info' or 'error'.
        """
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical if message_type == 'error' else QMessageBox.Icon.Information)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    @staticmethod
    def _ask_question(title: str, message: str) -> int:
        """
        Show a question dialog.

        :param title: the window title for the dialog.
        :param message: message to show.
        """
        ask = QMessageBox()
        ask.setIcon(QMessageBox.Icon.Warning)
        ask.setText(message)
        ask.setWindowTitle(title)
        ask.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        ask.activateWindow()
        action = ask.exec()
        return action

    @staticmethod
    def open_docs() -> None:
        """
        Open TaskBridge documentation in browser.
        """
        webbrowser.open("https://github.com/keithvassallomt/TaskBridge")

    @staticmethod
    def show_about() -> None:
        """
        Show the About dialog.
        """
        dialog = QDialog()
        dialog.ui = Ui_Dialog()
        dialog.ui.setupUi(dialog)
        dialog.ui.lbl_taskbridge_logo.setPixmap(QtGui.QPixmap('assets:ui/TaskBridge.png'))
        dialog.setWindowFlags(dialog.windowFlags() | QtCore.Qt.WindowType.CustomizeWindowHint)
        dialog.setWindowFlags(dialog.windowFlags() & ~QtCore.Qt.WindowType.WindowMaximizeButtonHint)
        dialog.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.exec()

    def get_table_icon(self, image: str) -> str:
        """
        Gets an icon for inline-display in table. Returns correct icon depending on whether dark mode is set.

        :param image: the name of the image to display from the 'taskbridge/gui/assets/table' folder.

        :return: path to the correct image.
        """
        colour = 'white' if darkdetect.isDark() else 'black'
        image_path = self.assets_path + '/table/{0}_{1}.png'.format(image, colour)
        return image_path

    def save_settings(self, what: str | None = None, silent: bool = True) -> None:
        """
        Save settings to file.

        :param what: what was saved. Used when displaying confirmation dialog and to prompt for reminder pruning.
        :param silent: if True, no confirmation dialog is shown.
        """
        if (what == 'reminders' and not self.ui.cb_reminder_autoprune.isChecked) and not silent:
            title = "Enable Completed Reminder Pruning?"
            message = ("You have not selected to automatically prune completed reminders. This can significantly slow "
                       "the sync process. Do you want to enable automatic completed reminders pruning?")
            action = TaskBridgeApp._ask_question(title, message)
            if action == QMessageBox.StandardButton.Yes:
                self.ui.cb_reminder_autoprune.setChecked(True)
                TaskBridgeApp.SETTINGS['prune_reminders'] = '1'

        with open(helpers.settings_folder() / 'conf.json', 'w') as fp:
            json.dump(TaskBridgeApp.SETTINGS, fp)
        if not silent:
            TaskBridgeApp._show_message("Settings Saved", "Your {} sync settings have been saved.".format(what))
        TaskBridgeApp.PENDING_CHANGES = False

    def trigger_unsaved(self, view: str) -> None:
        """
        Triggers an unsaved changes state and enables the form to save changes.

        :param view: the view for which to enable the save/cancel form.
        """
        TaskBridgeApp.PENDING_CHANGES = True
        if view == 'notes':
            self.ui.frm_notes.setEnabled(True)
        elif view == 'reminders':
            self.ui.frm_reminders.setEnabled(True)

    def bootstrap_ui(self) -> None:
        """
        Bootstraps the TaskBridge UI.
        """
        self.ui.tab_container.setCurrentIndex(0)
        self.ui.stackedWidget.setCurrentIndex(0)
        self.ui.tbl_notes.setRowCount(0)
        self.note_boxes.clear()
        self.reminder_boxes.clear()
        self.bootstrap_notes()
        self.bootstrap_reminders()
        self.bootstrap_sync()
        self.ui.actionSync.triggered.connect(lambda: self.switch_ui(0))
        self.ui.actionReminders.triggered.connect(lambda: self.switch_ui(1))
        self.ui.actionNotes.triggered.connect(lambda: self.switch_ui(2))
        self.ui.actionDocumentation.triggered.connect(TaskBridgeApp.open_docs)
        self.ui.actionAbout_TaskBridge.triggered.connect(TaskBridgeApp.show_about)
        self.ui.actionQuit_TaskBridge.triggered.connect(self.quit_gracefully)
        self.ui.cb_notes_sync.clicked.connect(self.handle_notes_sync)
        self.ui.cb_reminders_sync.clicked.connect(self.handle_reminders_sync)
        self.ui.setWindowIcon(QtGui.QIcon('assets:ui/TaskBridge.png'))
        self.ui.btn_notes_refresh.setIcon(QtGui.QIcon('assets:ui/refresh.png'))
        self.ui.btn_clear_logs.setIcon(QtGui.QIcon('assets:ui/trash.png'))
        self.ui.lbl_sync_graphic.setPixmap(QtGui.QPixmap('assets:ui/TaskBridge.png'))
        self.ui.lbl_sync_graphic.setScaledContents(True)
        self.ui.btn_clear_logs.clicked.connect(self.clear_logs)
        self.ui.tab_container.currentChanged.connect(self.check_changes)
        self.ui.btn_sync_view.clicked.connect(self.switch_sync_view)
        self.ui.cmb_sync_log_level.setCurrentText(TaskBridgeApp.SETTINGS['log_level'].title())
        self.ui.cmb_sync_log_level.currentIndexChanged.connect(self.set_logging_level)
        self.ui.btn_sync.clicked.connect(self.do_sync)

        # Note view handlers
        self.ui.btn_notes_choose.clicked.connect(self.handle_folder_browse)
        self.ui.btn_notes_save.clicked.connect(lambda: self.save_settings("notes", False))
        self.ui.btn_notes_cancel.clicked.connect(self.handle_notes_cancel)
        self.ui.btn_notes_refresh.clicked.connect(self.load_note_folders)
        self.ui.tbl_notes.cellClicked.connect(self.handle_note_checkbox)
        self.ui.txt_notes_folder.installEventFilter(self)

        # Reminder view handlers
        self.ui.btn_reminder_save.clicked.connect(lambda: self.save_settings("reminders", False))
        self.ui.btn_reminder_cancel.clicked.connect(self.handle_reminders_cancel)
        self.ui.btn_reminder_login.clicked.connect(self.handle_login)
        self.ui.tbl_reminders.cellClicked.connect(self.handle_reminder_checkbox)
        for widget in self.login_widgets:
            widget.installEventFilter(self)
        self.ui.rb_server_caldav.clicked.connect(lambda: self.trigger_unsaved("reminders"))
        self.ui.rb_server_nextcloud.clicked.connect(lambda: self.trigger_unsaved("reminders"))
        self.ui.cb_reminder_autoprune.clicked.connect(self.handle_prune_checkbox)

    def switch_ui(self, index: int) -> None:
        """
        Switches to the given tab. Also updates the menu.

        :param index: the tab number to switch to.
        """
        menus = [self.ui.actionSync, self.ui.actionReminders, self.ui.actionNotes]
        self.ui.tab_container.setCurrentIndex(index)
        for i in range(len(menus)):
            menus[i].setChecked(True) if i == index else menus[i].setChecked(False)

    def clear_logs(self) -> None:
        """
        Clears the log view.
        """
        self.ui.txt_log_display.clear()

    def set_logging_level(self) -> None:
        """
        Sets the logging level (and saves).
        """
        log_level = self.ui.cmb_sync_log_level.currentText().lower()
        TaskBridgeApp.SETTINGS['log_level'] = log_level
        if self.logging_worker:
            self.logging_worker.set_logging_level(log_level)
        self.save_settings()

    def switch_sync_view(self) -> None:
        """
        Switches between the two stacks in the Sync view (logo or debug).
        """
        if self.ui.stackedWidget.currentIndex() == 0:
            self.ui.stackedWidget.setCurrentIndex(1)
            self.ui.btn_sync_view.setArrowType(Qt.ArrowType.LeftArrow)
        else:
            self.ui.stackedWidget.setCurrentIndex(0)
            self.ui.btn_sync_view.setArrowType(Qt.ArrowType.RightArrow)

    def check_changes(self) -> None:
        """
        Checks for unsaved changes and prompts to save. If cancelled, resets changes.
        """
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

    def eventFilter(self, widget: QWidget, event: QEvent | QKeyEvent) -> bool:
        """
        Handles various minor UI events.

        :param widget: the widget which fired the event.
        :param event: the event which was fired.

        :return: False to allow further even handling to occur.
        """
        # Focusing out of any login form widget validates the form (to enable/disable login button)
        if event.type() == QEvent.Type.FocusOut and widget in self.login_widgets:
            self.ui.btn_reminder_login.setEnabled(self.validate_login_form()[0])

        # Tabbing out of username with a NextCloud server automatically populates the reminder path
        if (widget == self.ui.txt_reminder_username and self.ui.txt_reminder_username.text() and
                self.ui.rb_server_nextcloud.isChecked()):
            self.ui.txt_reminder_path.setText(
                '/remote.php/dav/calendars/{}'.format(self.ui.txt_reminder_username.text()))

        # Tabbing out of the password field triggers the login button being enabled
        if event.type() == QEvent.Type.KeyRelease and widget == self.ui.txt_reminder_password:
            self.ui.btn_reminder_login.setEnabled(self.validate_login_form()[0])

        # Making changes to the reminder login form triggers unsaved changes
        if event.type() == QEvent.Type.KeyRelease and widget in self.login_widgets:
            self.trigger_unsaved('reminders')

        # Changing the autosync frequency revalidates the form
        if event.type() == QEvent.Type.FocusOut and widget == self.ui.spn_sync_frequency:
            self.validate_autosync_form()

        # Changing the remote notes folder triggers unsaved changes
        if event.type() == QEvent.Type.KeyRelease and widget == self.ui.txt_notes_folder:
            self.trigger_unsaved('notes')
            self.ui.frm_notes.setEnabled(True)

        # Tabbing out of the remote folder triggers refresh
        if event.type() == QEvent.Type.KeyPress and widget == self.ui.txt_notes_folder:
            if event.key() == Qt.Key.Key_Tab:
                self.load_note_folders()

        return False

    # NOTE HANDLING ----------------------------------------------------------------------------------------------------
    @staticmethod
    def set_note_folder_association(folder_name: str, direction: str | None = None) -> None:
        """
        Updates :py:att`SETTINGS` with the association setting for this folder

        :param folder_name: the folder whose association was changed.
        :param direction: the sync direction as per keys in :py:att`SETTINGS`.
        """
        assoc = TaskBridgeApp.SETTINGS['associations']
        for sync_direction in assoc.keys():
            if folder_name in assoc[sync_direction]:
                assoc[sync_direction].remove(folder_name)

        if direction is not None:
            assoc[direction].append(folder_name)

    def handle_notes_sync(self) -> None:
        """
        Triggered when the Synchronise Notes option is checked.
        """
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

    def bootstrap_notes(self) -> None:
        """
        Initialises the notes table
        """
        self.ui.tbl_notes.setColumnCount(5)
        self.ui.tbl_notes.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ui.tbl_notes.setHorizontalHeaderItem(0, QTableWidgetItem('Folder'))
        self.ui.tbl_notes.setHorizontalHeaderItem(1, QTableWidgetItem('Location'))
        icon = QIcon(QtGui.QPixmap(self.get_table_icon('local_to_remote')))
        self.ui.tbl_notes.setHorizontalHeaderItem(2, QTableWidgetItem(icon, None, QTableWidgetItem.ItemType.UserType))
        self.ui.tbl_notes.horizontalHeaderItem(2).setToolTip('Sync local notes to remote')
        icon = QIcon(QtGui.QPixmap(self.get_table_icon('remote_to_local')))
        self.ui.tbl_notes.setHorizontalHeaderItem(3, QTableWidgetItem(icon, None, QTableWidgetItem.ItemType.UserType))
        self.ui.tbl_notes.horizontalHeaderItem(3).setToolTip('Sync remote notes to local')
        icon = QIcon(QtGui.QPixmap(self.get_table_icon('bidirectional')))
        self.ui.tbl_notes.setHorizontalHeaderItem(4, QTableWidgetItem(icon, None, QTableWidgetItem.ItemType.UserType))
        self.ui.tbl_notes.horizontalHeaderItem(4).setToolTip('Bi-directional sync')
        self.ui.tbl_notes.setIconSize(QSize(56, 56))
        self.refresh_notes()

    def refresh_notes(self) -> None:
        """
        Clears the notes table and reloads the notes folders.
        """
        self.ui.tbl_notes.setRowCount(0)
        self.apply_notes_settings()
        self.ui.cb_notes_sync.setChecked(TaskBridgeApp.SETTINGS['sync_notes'] == '1')
        remote_path = TaskBridgeApp.SETTINGS['remote_notes_folder']
        if remote_path == '':
            self.ui.cb_notes_sync.setChecked(False)
            return
        self.ui.gb_notes.setEnabled(True)
        self.load_note_folders()

    def apply_notes_settings(self) -> None:
        """
        Applies settings to the notes view from configuration file.
        """
        if TaskBridgeApp.SETTINGS['sync_notes'] == '1':
            self.ui.txt_notes_folder.setText(str(TaskBridgeApp.SETTINGS['remote_notes_folder']))
            self.ui.cb_notes_sync.setChecked(True)
        else:
            self.ui.cb_notes_sync.setChecked(False)
            self.ui.gb_notes.setEnabled(False)
            self.ui.frm_notes.setEnabled(False)

    def load_note_folders(self) -> None:
        """
        Starts the thread to load the note folders.
        """
        if self.note_pw_worker.isRunning():
            return

        if not os.path.exists(self.ui.txt_notes_folder.text()):
            TaskBridgeApp._show_message("Notes Folder Not Found", "Could not find the specified notes folder", "error")
            return

        # Set fields
        NoteController.REMOTE_NOTE_FOLDER = Path(TaskBridgeApp.SETTINGS['remote_notes_folder'])
        NoteController.ASSOCIATIONS = TaskBridgeApp.SETTINGS['associations']

        self.ui.btn_sync.setEnabled(False)
        self.ui.lbl_sync_status.setText("Loading Note Folders...")
        self.note_pw_worker.message_signal.connect(self.display_log)
        self.note_pw_worker.start()

    def display_notes_table(self, folder_list: List[NoteFolder]) -> None:
        """
        Displays the note folders in the table.

        :param folder_list: List of note folders to display.
        """
        self.note_pw_worker.quit()
        if not self.reminder_pw_worker.isRunning():
            self.ui.lbl_sync_status.setText("Currently Idle.")
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
                location_icon = QIcon(self.get_table_icon('local'))
            elif folder.local_folder is None and folder.remote_folder is not None:
                name = folder.remote_folder.name
                location = 'Remote'
                location_icon = QIcon(self.get_table_icon('remote'))
            elif folder.local_folder is not None and folder.remote_folder is not None:
                name = folder.local_folder.name
                location = 'Local & Remote'
                location_icon = QIcon(self.get_table_icon('local_and_remote'))
            else:
                self.display_log("Warning: One of your notes folders could not be found locally or remotely.")
                continue

            assoc = TaskBridgeApp.SETTINGS['associations']
            self.ui.tbl_notes.insertRow(row)
            self.ui.tbl_notes.setItem(row, 0, QTableWidgetItem(name))
            self.ui.tbl_notes.setItem(row, 1, QTableWidgetItem(location_icon, None, QTableWidgetItem.ItemType.UserType))
            self.ui.tbl_notes.setItem(row, 2, NoteCheckBox(check_type='local_to_remote', location=location,
                                                           folder_name=name, associations=assoc))
            self.ui.tbl_notes.setItem(row, 3, NoteCheckBox(check_type='remote_to_local', location=location,
                                                           folder_name=name, associations=assoc))
            self.ui.tbl_notes.setItem(row, 4, NoteCheckBox(check_type='bi_directional', location=location,
                                                           folder_name=name, associations=assoc))

    def handle_note_checkbox(self, row, col) -> None:
        """
        Handles the UI logic for the checkboxes in the notes folder. Refer to the ``NoteCheckbox`` class.
        """
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

    def handle_folder_browse(self) -> None:
        """
        Shows the folder chooser dialog for selecting the remote note folder.
        """
        remote_notes_folder = QFileDialog.getExistingDirectory(None, 'Select Remote Notes Folder')
        TaskBridgeApp.SETTINGS['remote_notes_folder'] = remote_notes_folder
        self.ui.txt_notes_folder.setText(remote_notes_folder)
        self.trigger_unsaved('notes')

    def handle_notes_cancel(self):
        """
        Prompts the user to save unsaved changes in the notes view. If cancelled, changes are discarded.
        """
        action = self._ask_question("Discard Changes?",
                                    "Are you sure you want to discard changes to note synchronisation settings?")
        if action == QMessageBox.StandardButton.Yes:
            TaskBridgeApp.load_settings()
            self.apply_notes_settings()
            if TaskBridgeApp.SETTINGS['sync_notes'] == '1':
                self.load_note_folders()

    # REMINDER HANDLING ------------------------------------------------------------------------------------------------
    def bootstrap_reminders(self):
        """
        Initialises the reminders view.
        """
        self.ui.tbl_reminders.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ui.tbl_reminders.setIconSize(QSize(28, 28))
        self.refresh_reminders()

    def refresh_reminders(self) -> None:
        """
        Resets the reminders view and loads the reminder containers.
        """
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

    def load_reminder_lists(self) -> None:
        """
        Loads the reminder containers by starting a thread.
        """
        if self.reminder_pw_worker.isRunning():
            return

        # Set fields
        ReminderController.CALDAV_USERNAME = TaskBridgeApp.SETTINGS['caldav_username']
        ReminderController.CALDAV_URL = TaskBridgeApp.SETTINGS['caldav_url']
        ReminderController.CALDAV_HEADERS = {}
        ReminderController.CALDAV_PASSWORD = keyring.get_password("TaskBridge", "CALDAV-PWD")
        ReminderController.TO_SYNC = TaskBridgeApp.SETTINGS['reminder_sync']

        # Pre-Warm Reminders
        self.ui.btn_sync.setEnabled(False)
        self.ui.lbl_sync_status.setText("Loading Reminder Lists...")
        self.reminder_pw_worker.message_signal.connect(self.display_log)
        self.reminder_pw_worker.start()

    def display_reminders_table(self, container_list: List[ReminderContainer]) -> None:
        """
        Displays the reminder contains in the reminder view table.

        :param container_list: the list of reminder containers.
        """
        self.reminder_pw_worker.quit()
        if not self.note_pw_worker.isRunning():
            self.ui.lbl_sync_status.setText("Currently Idle.")
            self.ui.btn_sync.setEnabled(True)

        # Display containers in table
        self.ui.tbl_reminders.setRowCount(0)
        row = 0

        for container in container_list:
            if container.local_list is not None and container.remote_calendar is None:
                name = container.local_list.name
                location_icon = QIcon(self.get_table_icon('local'))
            elif container.local_list is None and container.remote_calendar is not None:
                name = container.remote_calendar.name
                location_icon = QIcon(self.get_table_icon('remote'))
            elif container.local_list is not None and container.remote_calendar is not None:
                name = container.local_list.name
                location_icon = QIcon(self.get_table_icon('local_and_remote'))
            else:
                self.display_log("Warning: One of your reminder containers could not be found locally or remotely.")
                continue

            cbox = ReminderCheckbox(name, TaskBridgeApp.SETTINGS['reminder_sync'])
            self.ui.tbl_reminders.insertRow(row)
            self.ui.tbl_reminders.setItem(row, 0, QTableWidgetItem(name))
            self.ui.tbl_reminders.setItem(row, 1,
                                          QTableWidgetItem(location_icon, None, QTableWidgetItem.ItemType.UserType))
            self.ui.tbl_reminders.setItem(row, 2, cbox)

    def apply_reminders_settings(self) -> None:
        """
        Reads reminder settings from file and applies to reminders view.
        """
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
        """
        Validates the login form.

        :returns:

            -success (:py:class:`bool`) - true if form is valid.

            -data (:py:class:`str`) - error message(s) if invalid input, or full CalDav path if valid.

        """
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

    def handle_reminders_cancel(self) -> None:
        """
        Prompts the user to save their reminder view changes. If cancelled, changes are discarded and reminder lists are
        reloaded.
        """
        action = self._ask_question("Discard Changes?",
                                    "Are you sure you want to discard changes to reminder synchronisation settings?")
        if action == QMessageBox.StandardButton.Yes:
            TaskBridgeApp.load_settings()
            self.apply_reminders_settings()
            self.load_reminder_lists()

    def handle_reminders_sync(self) -> None:
        """
        Triggered when the Sync Reminders checkbox is enabled or disabled and sets the reminders UI state.
        """
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

    def handle_login(self) -> None:
        """
        Processes the login form.
        """
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

    def handle_reminder_checkbox(self, row: int, col: int) -> None:
        """
        Triggered when a checkbox in the reminders table is checked and updates :py:att`SETTINGS`.

        :param row: the row in the table containing this checkbox.
        :param col: the column in the table containing this checkbox.
        """
        cbox = self.ui.tbl_reminders.item(row, col)
        if not isinstance(cbox, ReminderCheckbox):
            return

        if cbox.is_checked():
            TaskBridgeApp.SETTINGS['reminder_sync'].append(cbox.container_name)
        else:
            TaskBridgeApp.SETTINGS['reminder_sync'].remove(cbox.container_name)

        self.trigger_unsaved('reminders')

    def handle_prune_checkbox(self) -> None:
        """
        Updates :py:att``SETTINGS`` when the Prune reminders checkbox is clicked.
        """
        TaskBridgeApp.SETTINGS['prune_reminders'] = '1' if self.ui.cb_reminder_autoprune.isChecked() else '0'
        self.trigger_unsaved('reminders')

    # Sync Handling-----------------------------------------------------------------------------------------------------
    def bootstrap_sync(self) -> None:
        """
        Prepare the Sync view.
        """
        self.ui.cb_sync_scheduled.clicked.connect(self.handle_sync_toggle)
        self.ui.cmb_sync_frequency.currentIndexChanged.connect(self.validate_autosync_form)
        self.apply_autosync_settings()
        self.ui.spn_sync_frequency.installEventFilter(self)
        self.ui.btn_sync_set_schedule.clicked.connect(self.set_autosync)

    def do_sync(self) -> None:
        """
        Start the sync thread.
        """
        sync_reminders = TaskBridgeApp.SETTINGS['sync_reminders'] == '1'
        sync_notes = TaskBridgeApp.SETTINGS['sync_notes'] == '1'
        prune_reminders = TaskBridgeApp.SETTINGS['prune_reminders'] == '1'
        if not sync_reminders and not sync_notes:
            TaskBridgeApp._show_message("Nothing to sync", "Both reminder and note sync is disabled, nothing to do!")
            return

        self.ui.btn_sync.setEnabled(False)
        icon_path = self.assets_path + "/tray/bridge_animated_black.gif" if darkdetect.isDark() else \
            self.assets_path + "/tray/bridge_animated_white.gif"
        self.tray_icon.set_animated_icon(icon_path)
        self.ui.lbl_sync_status.setText("Synchronising...")
        self.sync_worker = threadedtasks.Sync(sync_reminders, sync_notes, self.sync_complete, prune_reminders)
        self.sync_worker.message_signal.connect(self.display_log)
        self.sync_worker.progress_signal.connect(self.update_progress)
        self.sync_worker.start()

    def validate_autosync_form(self) -> None:
        """
        Validates the autosync form.

        Valid sync intervals: 10-59 minutes, 1-12 hours.
        """
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

    def set_autosync(self) -> None:
        """
        Updates :py:att`SETTINGS` for autosync.
        """
        interval = self.ui.spn_sync_frequency.value()
        unit = self.ui.cmb_sync_frequency.currentText()
        TaskBridgeApp.SETTINGS['autosync'] = '1'
        TaskBridgeApp.SETTINGS['autosync_interval'] = interval
        TaskBridgeApp.SETTINGS['autosync_unit'] = unit
        self.save_settings()
        self.start_autosync(interval, unit)

    def start_autosync(self, interval: int, unit: str) -> None:
        """
        Starts the autosync thread.

        :param interval: the interval specified by the user.
        :param unit: the interval unit specified by the user. 'Minutes' or 'Hours'.
        """
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

    def apply_autosync_settings(self) -> None:
        """
        Loads autosync settings and applies to UI.
        """
        if TaskBridgeApp.SETTINGS['autosync'] == '1':
            interval = TaskBridgeApp.SETTINGS['autosync_interval']
            unit = TaskBridgeApp.SETTINGS['autosync_unit']
            self.start_autosync(interval, unit)
            self.ui.spn_sync_frequency.setValue(interval)
            self.ui.cmb_sync_frequency.setCurrentText(unit)
            self.ui.cb_sync_scheduled.setChecked(True)
            self.ui.gb_autosync.setEnabled(True)

    def handle_sync_toggle(self) -> None:
        """
        Triggers when the autosync checkbox is clicked and sets UI state.
        """
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
    def quit_gracefully(self) -> None:
        """
        Quits TaskBridge. Terminates all threads and clears schedule before quitting.
        """
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
    def update_status(self, status: str = "Currently idle.") -> None:
        """
        Updates the status label.

        :param status: the status to set.
        """
        self.ui.lbl_sync_status.setText(status)

    def display_log(self, message: str) -> None:
        """
        Displays a log message.

        :param message: the message to display.
        """
        self.ui.txt_log_display.append(message)
        self.ui.txt_log_display.verticalScrollBar().setValue(self.ui.txt_log_display.verticalScrollBar().maximum())

    def update_progress(self, progress: int) -> None:
        """
        Updates the progress bar.

        :param progress: the progress value to set.
        """
        self.ui.progressBar.setValue(progress)

    def display_error(self, message: str) -> None:
        """
        Displays an error message coming from a thread during synchronisation tasks.

        :param message: the message to display.
        """
        self.ui.txt_log_display.append(message)
        self.ui.txt_log_display.verticalScrollBar().setValue(self.ui.txt_log_display.verticalScrollBar().maximum())
        self._show_message("Synchronisation Error", message, 'error')

    def sync_complete(self) -> None:
        """
        Triggered when a sync is completed.
        Sets next UI state.
        """
        icon_path = self.assets_path + "/tray/bridge_black.png" if darkdetect.isDark() \
            else self.assets_path + "/tray/bridge_white.png"
        self.tray_icon.setIcon(QtGui.QIcon(icon_path))
        self.ui.btn_sync.setEnabled(True)

        if TaskBridgeApp.SETTINGS['autosync'] == '1':
            delta = 0
            interval = TaskBridgeApp.SETTINGS['autosync_interval']
            unit = TaskBridgeApp.SETTINGS['autosync_unit']
            if unit == 'Minutes':
                delta = datetime.timedelta(minutes=interval)
            if unit == 'Hours':
                delta = datetime.timedelta(hours=interval)
            current_time = datetime.datetime.now()
            next_sync = current_time + delta
            self.ui.lbl_sync_status.setText('Synchronisation completed at {0}. Next Sync at {1}.'.format(
                current_time.strftime('%H:%M:%S'),
                next_sync.strftime('%H:%M:%S')
            ))
        else:
            self.ui.lbl_sync_status.setText("Synchronisation Complete!")
