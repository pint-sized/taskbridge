from __future__ import annotations

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
class ReminderPreWarm(QThread):
    message_signal = pyqtSignal(str)

    def __init__(self, cb: Callable):
        super().__init__()
        self.cb: Callable = cb

    def run(self):
        # Connect to remote server
        self.message_signal.emit("Connecting to remote reminder server...")
        ReminderController.connect_caldav()

        # Get reminder lists
        self.message_signal.emit("Fetching local reminder lists...")
        success, data = ReminderController.fetch_local_reminders()
        if not success:
            return  # TODO show some sort of error
        self.message_signal.emit("Fetching remote reminder lists...")
        success, data = ReminderController.fetch_remote_reminders()
        if not success:
            return  # TODO show some sort of error

        # Sync deletions
        self.message_signal.emit("Synchronising deleted reminder containers...")
        success, data = ReminderController.sync_deleted_containers()
        if not success:
            return  # TODO show some sort of error

        # Associate containers
        self.message_signal.emit("Associating reminder containers...")
        success, data = ReminderController.associate_containers()
        if not success:
            return  # TODO show some sort of error

        # Quit Reminders
        quit_reminders_script = reminderscript.quit_reminders_script
        helpers.run_applescript(quit_reminders_script)

        self.message_signal.emit("")
        self.cb(data)


# noinspection PyUnresolvedReferences
class NotePreWarm(QThread):
    message_signal = pyqtSignal(str)

    def __init__(self, cb: Callable):
        super().__init__()
        self.cb: Callable = cb

    def run(self):
        # Get folder lists
        self.message_signal.emit("Fetching local note folders...")
        success, data = NoteController.get_local_folders()
        if not success:
            return  # TODO show some sort of error
        self.message_signal.emit("Fetching remote note folders...")
        success, data = NoteController.get_remote_folders()
        if not success:
            return  # TODO show some sort of error

        # Sync deletions
        self.message_signal.emit("Synchronising deleted note folders...")
        success, data = NoteController.sync_folder_deletions()
        if not success:
            return  # TODO show some sort of error

        # Associate folders
        self.message_signal.emit("Associating note folders...")
        success, data = NoteController.associate_folders()
        if not success:
            return  # TODO show some sort of error

        # Quit Notes
        quit_notes_script = notescript.quit_notes_script
        helpers.run_applescript(quit_notes_script)

        self.message_signal.emit("")
        self.cb(data)


# noinspection PyUnresolvedReferences
class Sync(QThread):
    message_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self, sync_reminders: bool, sync_notes: bool, cb: Callable, prune_reminders: bool = False):
        super().__init__()
        self.sync_reminders: bool = sync_reminders
        self.sync_notes: bool = sync_notes
        self.cb: Callable = cb
        self.prune_reminders: bool = prune_reminders

    def run(self):
        progress = 0
        progress_increment = 25 if self.sync_reminders and self.sync_notes else 50
        self.progress_signal.emit(progress)

        if self.sync_reminders:
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

        if self.sync_notes:
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

        self.cb()


def run_continuously(interval=1):
    cease_continuous_run = threading.Event()

    class ScheduleThread(threading.Thread):
        @classmethod
        def run(cls):
            while not cease_continuous_run.is_set():
                schedule.run_pending()
                time.sleep(interval)

    continuous_thread = ScheduleThread()
    continuous_thread.start()
    return cease_continuous_run
