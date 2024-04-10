from __future__ import annotations

from typing import Callable

import view.viewmodel.taskbridgeapp as vm
from taskbridge.notes.controller import NoteController
from taskbridge.reminders.controller import ReminderController


def pre_warm_reminders(delegate: vm.TaskBridgeApp, cb: Callable):
    # Connect to remote server
    delegate.update_status("Connecting to remote reminder server...")
    ReminderController.connect_caldav()

    # Get folder lists
    delegate.update_status("Fetching local reminder lists...")
    success, data = ReminderController.fetch_local_reminders()
    if not success:
        return  # TODO show some sort of error
    delegate.update_status("Fetching remote reminder lists...")
    success, data = ReminderController.fetch_remote_reminders()
    if not success:
        return  # TODO show some sort of error

    # Sync deletions
    delegate.update_status("Synchronising deleted reminder containers...")
    success, data = ReminderController.sync_deleted_containers()
    if not success:
        return  # TODO show some sort of error

    # Associate containers
    delegate.update_status("Associating reminder containers...")
    success, data = ReminderController.associate_containers()
    if not success:
        return  # TODO show some sort of error

    delegate.update_status()
    cb(data)


def pre_warm_notes(delegate: vm.TaskBridgeApp, cb: Callable):
    # Get folder lists
    delegate.update_status("Fetching local note folders...")
    success, data = NoteController.get_local_folders()
    if not success:
        return  # TODO show some sort of error
    delegate.update_status("Fetching remote note folders...")
    success, data = NoteController.get_remote_folders()
    if not success:
        return  # TODO show some sort of error

    # Sync deletions
    delegate.update_status("Synchronising deleted note folders...")
    success, data = NoteController.sync_folder_deletions()
    if not success:
        return  # TODO show some sort of error

    # Associate folders
    delegate.update_status("Associating note folders...")
    success, data = NoteController.associate_folders()
    if not success:
        return  # TODO show some sort of error

    delegate.update_status()
    cb(data)
