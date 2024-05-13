"""
This is the note synchronisation controller. It contains all methods required for note synchronisation. These are called
by the GUI, but can be called separately if imported.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from taskbridge.notes.model.notefolder import NoteFolder, LocalNoteFolder, RemoteNoteFolder


class NoteController:
    """
    Contains various static methods for the stages of note synchronisation.
    """

    #: Path to the remote notes folder
    REMOTE_NOTE_FOLDER: Path = None
    #: List of local note folders
    LOCAL_NOTE_FOLDERS: List[LocalNoteFolder] = []
    #: List of remote note folders
    REMOTE_NOTE_FOLDERS: List[RemoteNoteFolder] = []
    #: Dictionary of associations
    ASSOCIATIONS: dict = {}

    @staticmethod
    def get_local_folders() -> tuple[bool, str]:
        """
        Get the list of local notes folders.

        :returns:

            -success (:py:class:`bool`) - true if the folders are successfully retrieved.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
        success, data = NoteFolder.load_local_folders()
        if not success:
            error = 'Failed to fetch local notes folders: {}'.format(data)
            logging.critical(error)
            return False, error
        NoteController.LOCAL_NOTE_FOLDERS = data
        debug_msg = 'Found local notes folders: {}'.format(
            [str(folder) for folder in NoteController.LOCAL_NOTE_FOLDERS])
        logging.debug(debug_msg)
        return True, debug_msg

    @staticmethod
    def get_remote_folders() -> tuple[bool, str]:
        """
        Get the list of remote note folders.

        :returns:

            -success (:py:class:`bool`) - true if the folders are successfully retrieved.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
        success, data = NoteFolder.load_remote_folders(NoteController.REMOTE_NOTE_FOLDER)
        if not success:
            error = 'Failed to fetch remote notes folders: {}'.format(data)
            logging.critical(error)
            return False, error
        NoteController.REMOTE_NOTE_FOLDERS = data
        debug_msg = 'Found remote notes folders: {}'.format(
            [str(folder) for folder in NoteController.REMOTE_NOTE_FOLDERS])
        logging.debug(debug_msg)
        return True, debug_msg

    @staticmethod
    def sync_folder_deletions() -> tuple[bool, str]:
        """
        Synchronise deleted local/remote notes folders.

        :returns:

            -success (:py:class:`bool`) - true if the folders deletions are successfully synchronised.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
        success, data = NoteFolder.sync_folder_deletions(NoteController.LOCAL_NOTE_FOLDERS,
                                                         NoteController.REMOTE_NOTE_FOLDERS)
        if not success:
            error = 'Failed to sync folder deletions {}'.format(data)
            logging.critical(error)
            return False, error
        debug_msg = 'Folder deletions synchronised.'
        logging.debug(debug_msg)
        return True, debug_msg

    @staticmethod
    def associate_folders() -> tuple[bool, str] | tuple[bool, List[NoteFolder]]:
        """
        Associate local/remote folders.

        :returns:

            -success (:py:class:`bool`) - true if the folders are successfully associated.

            -data (:py:class:`str` | :py:class:`List[NoteFolder]`) - error message on failure, or list of associations
            on success.

        """
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
        """
        Synchronise notes deleted locally/remotely.

        :returns:

            -success (:py:class:`bool`) - true if note deletions are successfully synchronised.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
        success, data = NoteFolder.sync_note_deletions(NoteController.REMOTE_NOTE_FOLDER)
        if not success:
            error = 'Failed to synchronise note deletions {}'.format(data)
            logging.critical(error)
            return False, error
        debug_msg = (
            "Deleted notes synchronisation:: Deleted Local: {} | Deleted Remote: {} | Remote Not Found: {} | Local "
            "Not Found: {}").format(
            ','.join(data['local_deleted'] if 'local_deleted' in data else ['No local notes deleted']),
            ','.join(data['remote_deleted'] if 'remote_deleted' in data else ['No remote notes deleted']),
            ','.join(data['remote_not_found'] if 'remote_not_found' in data else ['All remote notes found']),
            ','.join(data['local_not_found'] if 'local_not_found' in data else ['No local notes found'])
        )
        logging.debug(debug_msg)
        return True, debug_msg

    @staticmethod
    def sync_notes() -> tuple[bool, str] | tuple[bool, dict]:
        """
        Synchronise notes. Returns a dictionary with the following keys:

        - ``remote_added`` - name of notes added to the remote folder as :py:class:`List[str]`.
        - ``remote_updated`` - name of notes updated in the remote folder as :py:class:`List[str]`.
        - ``local_added`` - name of notes added to the local folder as :py:class:`List[str]`.
        - ``local_updated`` - name of notes updated in the local folder as :py:class:`List[str]`.

        Any of the above may be empty if no such changes were made.

        :returns:

            -success (:py:class:`bool`) - true if notes are successfully synchronised.

            -data (:py:class:`str` | :py:class:`dict`) - error message on failure, or :py:class:`dict` with results as
            above.

        """
        data = None
        for folder in NoteFolder.FOLDER_LIST:
            success, data = folder.sync_notes()
            if not success:
                error = 'Failed to sync notes {}'.format(data)
                logging.critical(error)
                return False, error

        debug_msg = (
            "Notes synchronisation:: Remote Added: {} | Remote Updated: {} | Local Added: {} | Local Updated: {"
            "}").format(
            ','.join(data['remote_added'] if 'remote_added' in data else ['No remote notes added']),
            ','.join(data['remote_updated'] if 'remote_updated' in data else ['No remote notes updated']),
            ','.join(data['local_added'] if 'local_added' in data else ['No local notes added']),
            ','.join(data['local_updated'] if 'local_updated' in data else ['No local notes updated'])
        )
        logging.debug(debug_msg)
        return True, data
