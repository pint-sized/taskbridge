"""
This is the note synchronisation controller. It takes care of the note synchronisation process.
"""
from __future__ import annotations

import datetime
import logging
import sys
from pathlib import Path
from typing import List, Callable

from taskbridge import helpers
from taskbridge.notes.model.notefolder import NoteFolder, LocalNoteFolder, RemoteNoteFolder


class NoteController:
    REMOTE_NOTE_FOLDER: Path = None
    LOCAL_NOTE_FOLDERS: List[LocalNoteFolder] = []
    REMOTE_NOTE_FOLDERS: List[RemoteNoteFolder] = []
    ASSOCIATIONS: dict = {}

    @staticmethod
    def get_local_folders() -> tuple[bool, str]:
        success, data = NoteFolder.load_local_folders()
        if not success:
            error = 'Failed to fetch local notes folders: {}'.format(data)
            logging.critical(error)
            return False, error
        NoteController.LOCAL_NOTE_FOLDERS = data
        debug_msg = 'Found local notes folders: {}'.format([str(folder) for folder in NoteController.LOCAL_NOTE_FOLDERS])
        logging.debug(debug_msg)
        return True, debug_msg

    @staticmethod
    def get_remote_folders() -> tuple[bool, str]:
        success, data = NoteFolder.load_remote_folders(NoteController.REMOTE_NOTE_FOLDER)
        if not success:
            error = 'Failed to fetch remote notes folders: {}'.format(data)
            logging.critical(error)
            return False, error
        NoteController.REMOTE_NOTE_FOLDERS = data
        debug_msg = 'Found remote notes folders: {}'.format([str(folder) for folder in NoteController.REMOTE_NOTE_FOLDERS])
        logging.debug(debug_msg)
        return True, debug_msg

    @staticmethod
    def sync_folder_deletions() -> tuple[bool, str]:
        success, data = NoteFolder.sync_folder_deletions(NoteController.LOCAL_NOTE_FOLDERS, NoteController.REMOTE_NOTE_FOLDERS)
        if not success:
            error = 'Failed to sync folder deletions {}'.format(data)
            logging.critical(error)
            return False, error
        debug_msg = 'Folder deletions synchronised.'
        logging.debug(debug_msg)
        return True, debug_msg

    @staticmethod
    def associate_folders() -> tuple[bool, str] | tuple[bool, List[NoteFolder]]:
        NoteFolder.reset_list()
        success, data = NoteFolder.create_linked_folders(
            NoteController.LOCAL_NOTE_FOLDERS,
            NoteController.REMOTE_NOTE_FOLDERS,
            NoteController.REMOTE_NOTE_FOLDER,
            NoteController.ASSOCIATIONS)
        if not success:
            error = 'Failed to associate folders {}'.format(data)
            logging.critical(error)
            return False, error
        debug_msg = 'Folder Associations: {}'.format([str(folder) for folder in NoteFolder.FOLDER_LIST])
        logging.debug(debug_msg)
        return True, NoteFolder.FOLDER_LIST

    @staticmethod
    def sync_deleted_notes() -> tuple[bool, str]:
        success, data = NoteFolder.sync_note_deletions(NoteController.REMOTE_NOTE_FOLDER)
        if not success:
            error = 'Failed to synchronise note deletions {}'.format(data)
            logging.critical(error)
            return False, error
        debug_msg = "Deleted notes synchronisation:: Deleted Local: {} | Deleted Remote: {} | Remote Not Found: {} | Local Not Found: {}".format(
                ','.join(data['local_deleted']),
                ','.join(data['remote_deleted']),
                ','.join(data['remote_not_found']),
                ','.join(data['local_not_found'])
            )
        logging.debug(debug_msg)
        return True, debug_msg

    @staticmethod
    def sync_notes() -> tuple[bool, str] | tuple[bool, dict]:
        data = None
        for folder in NoteFolder.FOLDER_LIST:
            success, data = folder.sync_notes()
            if not success:
                error = 'Failed to sync notes {}'.format(data)
                logging.critical(error)
                return False, error

        debug_msg = "Notes synchronisation:: Remote Added: {} | Remote Updated: {} | Local Added: {} | Local Updated: {}".format(
                ','.join(data['remote_added']),
                ','.join(data['remote_updated']),
                ','.join(data['local_added']),
                ','.join(data['local_updated'])
            )
        logging.debug(debug_msg)
        return True, data

    @staticmethod
    def init_logging(log_level_str: str, log_function: Callable = None):
        log_folder = Path.home() / "Library" / "Logs" / "TaskBridge"
        log_folder.mkdir(parents=True, exist_ok=True)
        log_file = datetime.datetime.now().strftime("Notes_%Y%m%d-%H%M%S") + '.log'
        log_levels = {
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'critical': logging.CRITICAL
        }
        log_level = log_levels[log_level_str]

        logging.basicConfig(
            level=log_level,
            format='%(asctime)s %(levelname)s: %(message)s',
            handlers=[
                logging.FileHandler(log_folder / log_file),
                logging.StreamHandler(sys.stdout),
            ]
        )
        if log_function is not None:
            func_handler = helpers.FunctionHandler(log_function)
            logging.getLogger().addHandler(func_handler)
