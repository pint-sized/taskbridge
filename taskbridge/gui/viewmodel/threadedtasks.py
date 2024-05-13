"""
Contains classes and functions which are run in a separate thread.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable
import threading
import time
import schedule

from PyQt6.QtCore import QThread, pyqtSignal

from taskbridge import helpers
from taskbridge.notes.controller import NoteController
from taskbridge.notes.model import notescript
from taskbridge.reminders.controller import ReminderController
from taskbridge.reminders.model import reminderscript


# noinspection PyUnresolvedReferences
class LoggingThread(QThread):
    """
    Used to collect logs.
    """

    #: Log messages are emitted to this signal.
    log_signal = pyqtSignal(str)
    #: When set, causes this thread to stop.
    stop_logging = threading.Event()

    def __init__(self, logging_level: str, log_stdout: bool = False, log_file: bool = True, log_gui: bool = True):
        """
        Initialises the logging thread.

        :param logging_level: the logging level which can be `DEBUG`, `INFO`, `WARNING` or `CRITICAL`.
        :param log_stdout: if True, logs are sent to standard out.
        :param log_file: if True, logs are sent to file.
        :param log_gui: if True, logs are sent to a function which handles displaying logs in the GUI.
        """
        super().__init__()
        self.logging_level: str = logging_level
        self.log_stdout: bool = log_stdout
        self.log_file: bool = log_file
        self.log_gui: bool = log_gui
        self.logger: logging.Logger = logging.getLogger()
        self.setup_logging()

    def setup_logging(self) -> None:
        """
        Sets up the logging system as configured in the constructor.
        """
        log_folder = Path.home() / "Library" / "Logs" / "TaskBridge"
        log_folder.mkdir(parents=True, exist_ok=True)
        log_file = datetime.now().strftime("TaskBridge_%Y%m%d-%H%M%S") + '.log'
        log_levels = {
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'critical': logging.CRITICAL
        }
        log_level = log_levels[self.logging_level]

        logging.basicConfig(
            level=log_level,
            format='%(asctime)s %(levelname)s: %(message)s',
        )
        if self.log_file:
            logging.getLogger().addHandler(logging.FileHandler(log_folder / log_file))
        if self.log_stdout:
            logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
        if self.log_gui:
            func_handler = helpers.FunctionHandler(lambda msg: self.log_signal.emit(msg))
            logging.getLogger().addHandler(func_handler)

    def set_logging_level(self, logging_level: str) -> None:
        """
        Changes the logging level.

        :param logging_level: the desired logging level.
        """
        self.logger.setLevel(logging_level)

    def run(self) -> None:
        """
        Keeps the logging thread running until it is stopped.
        """
        while not self.stop_logging.is_set():
            time.sleep(1)


# noinspection PyUnresolvedReferences
class ReminderPreWarm(QThread):
    """
    Performs tasks required to allow the user to configure reminder synchronisation and prepare for synchronisation.
    """

    #: Log messages are sent to this signal.
    message_signal = pyqtSignal(str)
    #: Error messages are sent to this signal.
    error_signal = pyqtSignal(str)

    def __init__(self, cb: Callable):
        """
        Initialises the pre-warm.

        :param cb: function which is called when the pre-warm is complete.
        """
        super().__init__()
        self.cb: Callable = cb

    def run(self) -> None:
        """
        Carries out the pre-warm tasks. This includes:

        1. Connect ot the remote reminder server.
        2. Fetch the local reminder lists.
        3. Fetch the remote task calendars.
        4. Synchronise deleted reminder lists and task calendars.
        5. Associate reminder lists and tasks calendars.

        """
        # Check if the Reminders app is running
        is_reminders_running_script = reminderscript.is_reminders_running_script
        return_code, stdout, stderr = helpers.run_applescript(is_reminders_running_script)
        reminders_was_running = stdout.strip() == 'true'

        # Connect to remote server
        self.message_signal.emit("Connecting to remote reminder server...")
        ReminderController.connect_caldav()

        # Get reminder lists
        self.message_signal.emit("Fetching local reminder lists...")
        success, data = ReminderController.fetch_local_reminders()
        if not success:
            self.error_signal.emit("Error fetching local reminder lists: {}".format(data))
            return
        self.message_signal.emit("Fetching remote reminder lists...")
        success, data = ReminderController.fetch_remote_reminders()
        if not success:
            self.error_signal.emit("Error fetching remote reminder lists: {}".format(data))
            return

        # Sync deletions
        self.message_signal.emit("Synchronising deleted reminder containers...")
        success, data = ReminderController.sync_deleted_containers()
        if not success:
            self.error_signal.emit("Error synchronising deleted reminder containers: {}".format(data))
            return

        # Associate containers
        self.message_signal.emit("Associating reminder containers...")
        success, data = ReminderController.associate_containers()
        if not success:
            self.error_signal.emit("Error associating reminder containers: {}".format(data))
            return

        # Quit Reminders if it wasn't running
        if not reminders_was_running:
            quit_reminders_script = reminderscript.quit_reminders_script
            helpers.run_applescript(quit_reminders_script)

        self.message_signal.emit("")
        self.cb(data)


# noinspection PyUnresolvedReferences
class NotePreWarm(QThread):
    """
    Performs tasks required to allow the user to configure note synchronisation and prepare for synchronisation.
    """

    #: Log messages are sent to this signal.
    message_signal = pyqtSignal(str)

    def __init__(self, cb: Callable):
        """
        Initialises the pre-warm.

        :param cb: function which is called when the pre-warm is complete.
        """
        super().__init__()
        self.cb: Callable = cb

    def run(self):
        """
        Carries out the pre-warm tasks. This includes.

        1. Fetch the local notes folders.
        2. Fetch the remote notes folders.
        3. Synchronise deleted folders.
        4. Associate local and remote folders.
        """

        # Check if the Notes app is running
        is_notes_running_script = notescript.is_notes_running_script
        return_code, stdout, stderr = helpers.run_applescript(is_notes_running_script)
        notes_was_running = stdout.strip() == 'true'

        # Get folder lists
        self.message_signal.emit("Fetching local note folders...")
        success, data = NoteController.get_local_folders()
        if not success:
            self.error_signal.emit("Error fetching local note folders: {}".format(data))
            return
        self.message_signal.emit("Fetching remote note folders...")
        success, data = NoteController.get_remote_folders()
        if not success:
            self.error_signal.emit("Error fetching remote note folders: {}".format(data))
            return

        # Sync deletions
        self.message_signal.emit("Synchronising deleted note folders...")
        success, data = NoteController.sync_folder_deletions()
        if not success:
            self.error_signal.emit("Error synchronising deleted note folders: {}".format(data))
            return

        # Associate folders
        self.message_signal.emit("Associating note folders...")
        success, data = NoteController.associate_folders()
        if not success:
            self.error_signal.emit("Error associating note folders: {}".format(data))
            return

        # Quit Notes if it wasn't running
        if not notes_was_running:
            quit_notes_script = notescript.quit_notes_script
            helpers.run_applescript(quit_notes_script)

        self.message_signal.emit("")
        self.cb(data)


# noinspection PyUnresolvedReferences
class Sync(QThread):
    """
    Thread which carries out the main synchronisation for both notes and reminders.
    """

    #: Log messages are sent to this signal.
    message_signal = pyqtSignal(str)
    #: Progress updates are sent to this signal.
    progress_signal = pyqtSignal(int)

    def __init__(self, sync_reminders: bool, sync_notes: bool, cb: Callable, prune_reminders: bool = False):
        """
        Initialises the synchronisation process.

        :param sync_reminders: if True, reminders will be synced.
        :param sync_notes: if True, notes will be synced.
        :param cb: function which is called after synchronisation is complete.
        :param prune_reminders: if True, completed reminders are deleted before sync.
        """
        super().__init__()
        self.sync_reminders: bool = sync_reminders
        self.sync_notes: bool = sync_notes
        self.cb: Callable = cb
        self.prune_reminders: bool = prune_reminders

    def run(self) -> None:
        """
        Carries out the synchronisation process.

        For reminders, if enabled, this involves:
        1. Pruning local completed reminders, if enabled.
        2. Synchronising deleted reminders.
        3. Synchronising reminders.
        4. Saving reminders to the database.

        For notes, if enabled, this involves:
        1. Synchronising deleted notes.
        2. Synchronising notes.

        """
        progress = 0
        progress_increment = 25 if self.sync_reminders and self.sync_notes else 50
        self.progress_signal.emit(progress)

        if self.sync_reminders:
            is_reminders_running_script = reminderscript.is_reminders_running_script
            return_code, stdout, stderr = helpers.run_applescript(is_reminders_running_script)
            reminders_was_running = stdout.strip() == 'true'
            if self.prune_reminders:
                self.message_signal.emit('Pruning completed reminders...')
                ReminderController.delete_completed()
            self.message_signal.emit('Synchronising deleted reminders...')
            ReminderController.sync_deleted_reminders()
            progress += progress_increment
            self.progress_signal.emit(progress)
            self.message_signal.emit('Synchronising reminders...')
            ReminderController.sync_reminders()
            ReminderController.sync_reminders_to_db()
            progress += progress_increment
            self.progress_signal.emit(progress)
            quit_reminders_script = reminderscript.quit_reminders_script
            helpers.run_applescript(quit_reminders_script)
            if not reminders_was_running:
                quit_reminders_script = reminderscript.quit_reminders_script
                helpers.run_applescript(quit_reminders_script)

        if self.sync_notes:
            is_notes_running_script = notescript.is_notes_running_script
            return_code, stdout, stderr = helpers.run_applescript(is_notes_running_script)
            notes_was_running = stdout.strip() == 'true'
            self.message_signal.emit('Synchronising deleted notes...')
            NoteController.sync_deleted_notes()
            progress += progress_increment
            self.progress_signal.emit(progress)
            self.message_signal.emit('Synchronising notes...')
            NoteController.sync_notes()
            progress += progress_increment
            self.progress_signal.emit(progress)
            quit_notes_script = notescript.quit_notes_script
            helpers.run_applescript(quit_notes_script)
            if not notes_was_running:
                quit_notes_script = notescript.quit_notes_script
                helpers.run_applescript(quit_notes_script)

        self.cb()


def run_continuously(interval=1) -> threading.Event():
    """
    Utility function which continuously calls ``schedule`` to run any pending tasks.

    :param interval: interval between cycles.

    :return: a threading event which can be used to stop the continuous run.
    """

    #: When set, the thread will be stopped
    cease_continuous_run = threading.Event()

    class ScheduleThread(threading.Thread):
        """
        Class to run continuous tasks
        """
        @classmethod
        def run(cls):
            """
            Keep tasks running until cancelled
            """
            while not cease_continuous_run.is_set():
                schedule.run_pending()
                time.sleep(interval)

    continuous_thread = ScheduleThread()
    continuous_thread.start()
    return cease_continuous_run
