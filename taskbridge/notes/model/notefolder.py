"""
Contains the ``NoteFolder`` class, which represents a folder containing notes, either locally or remotely.
Many of the synchronisation methods are here.
"""

from __future__ import annotations

import copy
import datetime
import glob
import os
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import List

from taskbridge import helpers
from taskbridge.notes.model import notescript
from taskbridge.notes.model.note import Note


class NoteFolder:
    """
    Represents a folder containing notes. A link is established here between the local folder and the remote one.
    Also contains a list of notes in this folder.
    """

    #: List of all found note folders
    FOLDER_LIST: List[NoteFolder] = []

    #: Do not sync this folder
    SYNC_NONE: int = 0

    #: Update the remote folder with the changes in the local one (One-way).
    SYNC_LOCAL_TO_REMOTE: int = 1

    #: Update the local folder with the changes in the remote one (One-way).
    SYNC_REMOTE_TO_LOCAL: int = 2

    #: Synchronise changes from both folders.
    SYNC_BOTH: int = 3

    def __init__(self,
                 local_folder: LocalNoteFolder | None = None,
                 remote_folder: RemoteNoteFolder | None = None,
                 sync_direction: int = SYNC_NONE):
        """
        Create a new note folder.

        :param local_folder: the local folder containing the local notes.
        :param remote_folder: the remote folder containing the remote notes.
        :param sync_direction: how to sync the folders.

        ``sync_direction``:

        - ``NoteFolder.NO_SYNC`` - these folders will not be synchronised.
        - ``NoteFolder.SYNC_LOCAL_TO_REMOTE`` - local notes will be pushed to remote.
        - ``NoteFolder.SYNC_REMOTE_TO_LOCAL`` - remote notes will be pulled to local.
        - ``NoteFolder.SYNC_BOTH`` - bidirectional sync based on the note's modification date/time.
        """
        self.local_folder: LocalNoteFolder = local_folder
        self.remote_folder: RemoteNoteFolder = remote_folder
        self.sync_direction: int = sync_direction
        self.local_notes: List[Note] = []
        self.remote_notes: List[Note] = []
        NoteFolder.FOLDER_LIST.append(self)

    def load_local_notes(self) -> tuple[bool, str] | tuple[bool, int]:
        """
        Calls an AppleScript script to fetch the notes in the local folder. The script saves each note with a ``.staged``
        file name in a temporary folder. Each file is then read, parsed and added as a ``Note`` instance in the
        in ``local_notes``.

        :returns:

            -success (:py:class:`bool`) - true if notes are successfully loaded.

            -data (:py:class:`str` | :py:class:`int`) - error message on failure, or number of notes loaded on success.

        """
        self.local_notes.clear()
        get_notes_script = notescript.get_notes_script
        return_code, stdout, stderr = helpers.run_applescript(get_notes_script, self.local_folder.name)

        if return_code != 0:
            return False, stderr

        staging_folder_path = stdout.strip()
        for filename in os.listdir(staging_folder_path):
            f_name, f_ext = os.path.splitext(filename)
            if not f_ext == ".staged":
                continue
            staged_file = os.path.join(staging_folder_path, filename)
            with open(staged_file) as fp:
                staged_content = fp.read()
            self.local_notes.append(Note.create_from_local(staged_content, Path(staging_folder_path)))

        staged = glob.glob(staging_folder_path + '/*.staged')
        for s in staged:
            os.remove(s)

        return True, len(self.local_notes)

    def load_remote_notes(self) -> tuple[bool, str] | tuple[bool, int]:
        """
        Loads the Markdown notes from the remote notes folder. Each note is then parsed and added as a ``Note`` instance
        in ``remote_notes``.

        :returns:

            -success (:py:class:`bool`) - true if notes are successfully loaded.

            -data (:py:class:`str` | :py:class:`int`) - error message on failure, or number of notes loaded on success.

        """
        self.remote_notes.clear()

        for root, dirs, files in os.walk(self.remote_folder.path):
            for remote_file in files:
                f_name, f_ext = os.path.splitext(remote_file)
                if not f_ext == ".md":
                    continue
                remote_note = self.remote_folder.path / remote_file
                with open(remote_note) as fp:
                    remote_content = fp.read()
                self.remote_notes.append(Note.create_from_remote(remote_content, self.remote_folder.path, remote_file))

        return True, len(self.remote_notes)

    def sync_local_note_to_remote(self, local: Note, remote: Note | None, result: dict) -> tuple[bool, str]:
        """
        Sync local notes to remote. This performs an update or an insert.

        :param local: the local note.
        :param remote: the remote note.
        :param result: a dictionary where results of sync will be saved.

        :returns:

            -success (:py:class:`bool`) - true if notes are successfully synchronised.

            -data (:py:class:`str`) - error message on failure, or dictionary of changes.

        """
        if remote is None or local.modified_date > remote.modified_date:
            key = 'remote_added' if remote is None else 'remote_updated'
            remote = copy.deepcopy(local)
            if helpers.confirm("Upsert remote note {}".format(remote.name)):
                i_success, i_data = remote.upsert_remote(self.remote_folder.path)
                if not i_success:
                    return False, i_data
                result[key].append(remote.name)
                return True, i_data
        return True, ''

    def sync_remote_note_to_local(self, local: Note, remote: Note, result: dict) -> tuple[bool, str]:
        """
        Sync remote notes to local. This performs an update or an insert.
        Since the Apple Notes modified date is read only, we have to update the modified date of the remote note as well,
        otherwise the remote note will be overwritten on the next sync.

        :param local: the local note.
        :param remote: the remote note.
        :param result: a dictionary where results of sync will be saved.

        :returns:

            -success (:py:class:`bool`) - true if notes are successfully synchronised.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
        if remote is not None and local.modified_date < remote.modified_date:
            key = 'local_updated'
            local = copy.deepcopy(remote)
            if helpers.confirm("Update local note {}".format(local.name)):
                i_success, i_data = local.update_local(self.local_folder.name)
                if not i_success:
                    return False, i_data
                result[key].append(local.name)

                # Update modification date of remote note
                remote.modified_date = datetime.datetime.now()
                remote.upsert_remote(self.remote_folder.path)

                return True, i_data
        return True, 'Sync skipped since local note has been modified.'

    def sync_local_to_remote(self, result: dict) -> tuple[bool, str]:
        """
        Sync all the local notes in this folder to remote.

        :param result: dictionary where results will be saved.

        :returns:

            -success (:py:class:`bool`) - true if notes are successfully synchronised.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
        success = True
        data = "Local notes in folder synchronised to remote"
        for local_note in self.local_notes:
            # Get the associated remote note, if any
            remote_note = next((n for n in self.remote_notes
                                if n.uuid == local_note.uuid or n.name == local_note.name), None)

            if self.sync_direction == NoteFolder.SYNC_LOCAL_TO_REMOTE:
                # Sync Local --> Remote if remote doesn't exist or is outdated
                success, data = self.sync_local_note_to_remote(local_note, remote_note, result)
            elif self.sync_direction == NoteFolder.SYNC_REMOTE_TO_LOCAL:
                # Sync Local <-- Remote if local is outdated
                success, data = self.sync_remote_note_to_local(local_note, remote_note, result)
            elif self.sync_direction == NoteFolder.SYNC_BOTH:
                # Sync Local <--> Remote, depending on which is newer
                if remote_note is None or local_note.modified_date > remote_note.modified_date:
                    success, data = self.sync_local_note_to_remote(local_note, remote_note, result)
                elif remote_note.modified_date > local_note.modified_date:
                    success, data = self.sync_remote_note_to_local(local_note, remote_note, result)
            if not success:
                break

        return success, data

    def sync_remote_to_local(self, result) -> tuple[bool, str]:
        """
        Sync all remote notes in this folder to local.

        :param result: dictionary where results will be saved.

        :returns:

            -success (:py:class:`bool`) - true if notes are successfully synchronised.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
        success = True
        data = "Remote notes in folder synchronised to local"
        for remote_note in self.remote_notes:
            local_note = next((n for n in self.local_notes
                               if n.uuid == remote_note.modified_date or n.name == remote_note.name), None)
            if ((
                    self.sync_direction == NoteFolder.SYNC_REMOTE_TO_LOCAL or self.sync_direction == NoteFolder.SYNC_BOTH)
                    and local_note is None):
                # Local note is missing and so needs to be created
                key_change = 'local_added'
                local_note = copy.deepcopy(remote_note)
                if helpers.confirm("Create local note {}".format(local_note.name)):
                    success, data = local_note.create_local(self.local_folder.name)
                    if not success:
                        break
                    result[key_change].append(local_note.name)

        return success, data

    def sync_notes(self) -> tuple[bool, dict] | tuple[bool, str]:
        """
        Synchronises notes. This method checks the ``sync_direction`` of this folder to determine what to do. On
        success, it returns a dictionary with the following keys:

        - ``remote_added`` - name of notes added to the remote folder as :py:class:`List[str]`.
        - ``remote_updated`` - name of notes updated in the remote folder as :py:class:`List[str]`.
        - ``local_added`` - name of notes added to the local folder as :py:class:`List[str]`.
        - ``local_updated`` - name of notes updated in the local folder as :py:class:`List[str]`.

        Any of the above may be empty if no such changes were made.

        :returns:

            -success (:py:class:`bool`) - true if notes are successfully synchronised.

            -data (:py:class:`str` | :py:class:`dict`) - error message on failure, or :py:class:`dict` with results as above.

        """
        result = {
            'remote_added': [],
            'remote_updated': [],
            'local_added': [],
            'local_updated': []
        }
        if self.sync_direction == NoteFolder.SYNC_NONE:
            return True, result

        # Sync local notes to remote
        self.sync_local_to_remote(result)

        # Sync remote notes to local
        self.sync_remote_to_local(result)

        # Save current note status
        success, data = NoteFolder.persist_notes()
        if not success:
            return False, 'Failed to save notes to database {}'.format(data)

        return True, result

    def __str__(self):
        if self.sync_direction == NoteFolder.SYNC_BOTH:
            sync_direction = "LOCAL <--> REMOTE"
        elif self.sync_direction == NoteFolder.SYNC_LOCAL_TO_REMOTE:
            sync_direction = "LOCAL --> REMOTE"
        elif self.sync_direction == NoteFolder.SYNC_REMOTE_TO_LOCAL:
            sync_direction = "LOCAL <-- REMOTE"
        else:
            sync_direction = "NO SYNC"
        return "Local: {0} <> Remote: {1} : Sync: {2}".format(
            self.local_folder.name if self.local_folder else 'None',
            self.remote_folder.name if self.remote_folder else 'None',
            sync_direction
        )

    @staticmethod
    def load_local_folders() -> tuple[bool, str] | tuple[bool, List[LocalNoteFolder]]:
        """
        Loads the list of local folders by calling an AppleScript script.

        :returns:

            -success (:py:class:`bool`) - true if folders are successfully loaded.

            -data (:py:class:`str` | :py:class:`List[LocalNoteFolder]`) - error message on failure, list of folders on success.

        """
        load_folders_script = notescript.load_folders_script
        return_code, stdout, stderr = helpers.run_applescript(load_folders_script)

        local_note_folders = []
        if return_code == 0:
            for f_list in stdout.split('|'):
                uuid, name = [f.strip() for f in f_list.split('~~')]
                if name != 'Recently Deleted':
                    local_folder = LocalNoteFolder(name, uuid)
                    local_note_folders.append(local_folder)
            return True, local_note_folders

        return False, stderr

    @staticmethod
    def load_remote_folders(remote_notes_path: Path) -> tuple[bool, List[RemoteNoteFolder]]:
        """
        Loads the list of remote folders by checking the filesystem.

        :returns:

            -success (:py:class:`bool`) - true if folders are successfully loaded.

            -data (:py:class:`str` | :py:class:`List[RemoteNoteFolder]`) - error message on failure, list of folders on
            success.

        """
        remote_note_folders = []
        for root, dirs, files in os.walk(remote_notes_path):
            for remote_dir in dirs:
                if not remote_dir.startswith("."):
                    remote_folder = RemoteNoteFolder(remote_notes_path / remote_dir, remote_dir)
                    remote_note_folders.append(remote_folder)
        return True, remote_note_folders

    @staticmethod
    def assoc_local_remote(local_folders: List[LocalNoteFolder],
                           remote_folders: List[RemoteNoteFolder],
                           remote_notes_path: Path,
                           associations: dict) -> None:
        """
        Associate local folders with remote folders.

        :param local_folders: the list of local note folders.
        :param remote_folders: the list of remote note folders.
        :param remote_notes_path: path to the remote folders, i.e. where on the local filesystem the remote notes are stored.
        :param associations: list of folder associations.

        """
        for local_folder in local_folders:
            # Check which local folders need to be synced with remote folders
            remote_folder = next((f for f in remote_folders if f.name == local_folder.name), None)
            if local_folder.name in associations['bi_directional']:
                sync_direction = NoteFolder.SYNC_BOTH
            elif local_folder.name in associations['local_to_remote']:
                sync_direction = NoteFolder.SYNC_LOCAL_TO_REMOTE
            elif local_folder.name in associations['remote_to_local']:
                sync_direction = NoteFolder.SYNC_REMOTE_TO_LOCAL
            else:
                sync_direction = NoteFolder.SYNC_NONE
            NoteFolder(local_folder, remote_folder, sync_direction)

            # Create missing remote folder
            if local_folder.name in associations['bi_directional'] or local_folder.name in associations['local_to_remote']:
                if remote_folder is None:
                    remote_folder = RemoteNoteFolder(remote_notes_path / local_folder.name, local_folder.name)
                    if helpers.confirm('Create remote folder {}'.format(remote_folder.name)):
                        remote_folder.create()

    @staticmethod
    def assoc_remote_local(local_folders: List[LocalNoteFolder],
                           remote_folders: List[RemoteNoteFolder],
                           associations: dict) -> None:
        """
        Associate remote folders with local folders.

        :param local_folders: the list of local note folders.
        :param remote_folders: the list of remote note folders.
        :param associations: list of folder associations.

        """
        for remote_folder in remote_folders:
            # Check if the remote folder is already associated to a local folder
            existing_association = next(
                (f for f in NoteFolder.FOLDER_LIST if f.remote_folder and f.remote_folder.name == remote_folder.name),
                None)
            # Check if the remote folder should not be synced and already has a counterpart
            if existing_association is None:
                existing_association = next(
                    (f for f in NoteFolder.FOLDER_LIST
                     if f.local_folder is not None
                     and f.local_folder.name == remote_folder.name
                     and f.sync_direction == NoteFolder.SYNC_NONE),
                    None)

            if existing_association is not None:
                continue

            local_folder = next((f for f in local_folders if f.name == remote_folder.name), None)
            if remote_folder.name in associations['bi_directional']:
                sync_direction = NoteFolder.SYNC_BOTH
            elif remote_folder.name in associations['local_to_remote']:
                sync_direction = NoteFolder.SYNC_LOCAL_TO_REMOTE
            elif remote_folder.name in associations['remote_to_local']:
                sync_direction = NoteFolder.SYNC_REMOTE_TO_LOCAL
            else:
                sync_direction = NoteFolder.SYNC_NONE
            NoteFolder(local_folder, remote_folder, sync_direction)

            # Create missing local folder
            if remote_folder.name in associations['bi_directional'] or remote_folder.name in associations['remote_to_local']:
                if local_folder is None:
                    local_folder = LocalNoteFolder(remote_folder.name)
                    if helpers.confirm('Create local folder {}'.format(local_folder.name)):
                        local_folder.create()

    @staticmethod
    def create_linked_folders(local_folders: List[LocalNoteFolder],
                              remote_folders: List[RemoteNoteFolder],
                              remote_notes_path: Path,
                              associations: dict) -> tuple[bool, str]:
        """
        Creates an association between local and remote folders. Missing folders are created; for example, if the folder
        *foo* is present locally, and set to ``SYNC_LOCAL_TO_REMOTE`` or ``SYNC_BOTH`` this method will check whether the
        remote folder *foo* exists and, if not, creates it.

        The list of folders is saved to an SQLite database.

        :param local_folders: the list of local note folders.
        :param remote_folders: the list of remote note folders.
        :param remote_notes_path: path to the remote folders, i.e. where on the local filesystem the remote notes are stored.
        :param associations: list of folder associations.

        The associations dictionary must contain the following keys:

        - ``local_to_remote`` - notes to push from local to remote as :py:class`List[str]`.
        - ``remote_to_local`` - notes to pull from remote to local as :py:class`List[str]`.
        - ``bi_directional`` - notes to synchronise in both folders as :py:class`List[str]`.

        Any other folders found which are not listed above are not synchronised.

        :returns:

            -success (:py:class:`bool`) - true if the folders are successfully linked.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
        # Create Local --> Remote Associations
        NoteFolder.assoc_local_remote(local_folders, remote_folders, remote_notes_path, associations)

        # Create Remote --> Local Associations
        NoteFolder.assoc_remote_local(local_folders, remote_folders, associations)

        success, data = NoteFolder.persist_folders()
        if not success:
            return False, data
        return True, 'Folder associations created.'

    @staticmethod
    def seed_folder_table() -> tuple[bool, str]:
        """
        Creates the initial structure for the table storing folders in SQLite.

        :returns:

            -success (:py:class:`bool`) - true if table is successfully seeded.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_create_folder_table = """CREATE TABLE IF NOT EXISTS tb_folder (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    local_uuid TEXT,
                                    local_name TEXT,
                                    remote_path TEXT,
                                    remote_name TEXT,
                                    sync_direction INT
                                    );"""
                    cursor.execute(sql_create_folder_table)
        except sqlite3.OperationalError as e:
            return False, repr(e)
        return True, 'tb_folder table created'

    @staticmethod
    def persist_folders() -> tuple[bool, str]:
        """
        Save the list of linked note folders to SQLite.

        :returns:

            -success (:py:class:`bool`) - true if folders are successfully saved.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
        folders = []
        for folder in NoteFolder.FOLDER_LIST:
            folders.append((
                folder.local_folder.uuid if folder.local_folder else None,
                folder.local_folder.name if folder.local_folder else None,
                str(folder.remote_folder.path) if folder.remote_folder else None,
                folder.remote_folder.name if folder.remote_folder else None,
                folder.sync_direction
            ))

        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_delete_folders = "DELETE FROM tb_folder"
                    cursor.execute(sql_delete_folders)
                    sql_insert_folders = """INSERT INTO tb_folder(local_uuid, local_name, remote_path, remote_name,
                    sync_direction)
                                VALUES (?, ?, ?, ?, ?)
                                """
                    cursor.executemany(sql_insert_folders, folders)
                    connection.commit()
        except sqlite3.OperationalError as e:
            return False, repr(e)
        return True, 'Folders stored in tb_folder'

    @staticmethod
    def sync_bidirectional_local_deletions(discovered_local: List[LocalNoteFolder]) -> tuple[bool, str]:
        """
        Sync folders that have been marked for bidirectional or local -> remote sync.

        :param discovered_local: list of currently discovered local note folders.

        :returns:

            -success (:py:class:`bool`) - true if folder deletions are successfully synchronised.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
        folder_filter = (NoteFolder.SYNC_BOTH, NoteFolder.SYNC_LOCAL_TO_REMOTE)
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_bi_and_local = "SELECT * FROM tb_folder WHERE sync_direction = ? OR sync_direction = ?"
                    rows = cursor.execute(sql_bi_and_local, folder_filter).fetchall()
                    current_local_names = [f.name for f in discovered_local]
                    removed_local = [f for f in rows if f['local_name'] not in current_local_names]
                    for f in removed_local:
                        # Local folder has been deleted, so delete remote
                        if helpers.confirm("Delete remote folder {}".format(f['remote_name'])):
                            success, data = RemoteNoteFolder(f['remote_path'], f['remote_name']).delete()
                            if not success:
                                return False, data
        except sqlite3.OperationalError as e:
            return False, 'Error retrieving folders from table: {}'.format(e)

        return True, "Bidirectional and local folder deletions synchronised."

    @staticmethod
    def sync_remote_deletions(discovered_remote: List[RemoteNoteFolder]) -> tuple[bool, str]:
        """
        Sync folders that have been marked for local <- remote sync.

        :param discovered_remote: list of currently discovered remote note folders.

        :returns:

            -success (:py:class:`bool`) - true if folder deletions are successfully synchronised.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
        folder_filter = (NoteFolder.SYNC_REMOTE_TO_LOCAL,)
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_remote = "SELECT * FROM tb_folder WHERE sync_direction = ?"
                    rows = cursor.execute(sql_remote, folder_filter).fetchall()
                    current_remote_names = [f.name for f in discovered_remote]
                    removed_remote = [f for f in rows if f['remote_name'] not in current_remote_names]
                    for f in removed_remote:
                        # Remote folder has been deleted, so delete local
                        if helpers.confirm("Delete local folder {}".format(f['local_name'])):
                            success, data = LocalNoteFolder(f['local_name'], f['local_uuid']).delete()
                            if not success:
                                return False, data
        except sqlite3.OperationalError as e:
            return False, 'Error retrieving folders from table: {}'.format(e)

        return True, "Remote folder deletions synchronised."

    @staticmethod
    def sync_folder_deletions(discovered_local: List[LocalNoteFolder], discovered_remote: List[RemoteNoteFolder]) -> \
            tuple[
                bool, str]:
        """
        Synchronises deletions to folders.

        The list of folders found during the last sync is loaded from SQLite and compared to the local and remote folders
        found now. Any folders in the database which are no longer present will then have their counterpart deleted. For
        example, if the local folder *foo* is deleted, the remote folder *foo* will be deleted during sync.

        Note that folder deletions only apply in the sync direction. In the example above, *foo* will only be deleted if
        ``sync_direction`` is set to ``SYNC_LOCAL_TO_REMOTE`` or ``SYNC_BOTH``.

        :param discovered_local: List of currently discovered local note folders.
        :param discovered_remote: List of currently discovered remote note folders.

        :returns:

            -success (:py:class:`bool`) - true if folder deletions are successfully synchronised.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
        success, message = NoteFolder.seed_folder_table()
        if not success:
            return False, message

        # Bi-Directional or Local --> Remote Folders
        NoteFolder.sync_bidirectional_local_deletions(discovered_local)

        # Local <-- Remote Folders
        NoteFolder.sync_remote_deletions(discovered_remote)

        # Empty Table

        with closing(sqlite3.connect(helpers.db_folder())) as connection:
            connection.row_factory = sqlite3.Row
            with closing(connection.cursor()) as cursor:
                cursor.execute("DELETE FROM tb_folder")

        return True, 'Folder deletions synchronised'

    @staticmethod
    def seed_note_table() -> tuple[bool, str]:
        """
        Creates the initial structure for the table storing notes in SQLite.

        :returns:

            -success (:py:class:`bool`) - true if table is successfully created.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_create_note_table = """CREATE TABLE IF NOT EXISTS tb_note (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        folder TEXT,
                                        location TEXT,
                                        uuid TEXT,
                                        name TEXT,
                                        created TEXT,
                                        modified TEXT
                                        );"""
                    cursor.execute(sql_create_note_table)
        except sqlite3.OperationalError as e:
            return False, repr(e)
        return True, 'tb_note table created'

    @staticmethod
    def persist_notes() -> tuple[bool, str]:
        """
        Stores a list of notes in SQLite. Note that the only 'sensitive' part of the note which is stored is the note's name.
        The database is stored locally.

        :returns:

            -success (:py:class:`bool`) - true if table notes are successfully saved to the database.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
        notes = []
        for folder in NoteFolder.FOLDER_LIST:
            if folder.sync_direction == NoteFolder.SYNC_NONE:
                continue

            if folder.sync_direction == NoteFolder.SYNC_LOCAL_TO_REMOTE or folder.sync_direction == NoteFolder.SYNC_BOTH:
                # Add notes from local folder
                for note in folder.local_notes:
                    notes.append((
                        folder.local_folder.name,
                        'local',
                        note.uuid,
                        note.name,
                        helpers.DateUtil.convert('', note.created_date, helpers.DateUtil.SQLITE_DATETIME),
                        helpers.DateUtil.convert('', note.modified_date, helpers.DateUtil.SQLITE_DATETIME)
                    ))

            if folder.sync_direction == NoteFolder.SYNC_REMOTE_TO_LOCAL or folder.sync_direction == NoteFolder.SYNC_BOTH:
                # Add notes from remote folder
                for note in folder.remote_notes:
                    notes.append((
                        folder.remote_folder.name,
                        'remote',
                        note.uuid,
                        note.name,
                        helpers.DateUtil.convert('', note.created_date, helpers.DateUtil.SQLITE_DATETIME),
                        helpers.DateUtil.convert('', note.modified_date, helpers.DateUtil.SQLITE_DATETIME)
                    ))

        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_delete_folders = "DELETE FROM tb_note"
                    cursor.execute(sql_delete_folders)
                    sql_insert_notes = """INSERT INTO tb_note(folder, location, uuid, name, created, modified)
                                        VALUES (?, ?, ?, ?, ?, ?)
                                        """
                    cursor.executemany(sql_insert_notes, notes)
                    connection.commit()
        except sqlite3.OperationalError as e:
            return False, repr(e)
        return True, 'Notes stored in tb_notes'

    @staticmethod
    def delete_local_notes(folder: NoteFolder, result: dict) -> tuple[bool, str]:
        """
        Delete notes from local which were deleted remotely.

        :param folder: the folder data.
        :param result: dictionary where results are appended.

        :returns:

            -success (:py:class:`bool`) - true if local notes are successfully deleted.

            -data (:py:class:`str`) - error message on failure, or success message.
        """
        delete_note_script = notescript.delete_note_script
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_remote_notes = "SELECT * FROM tb_note WHERE folder = ? AND location = ?"
                    remote_filter = (folder.remote_folder.name, 'remote')
                    rows = cursor.execute(sql_remote_notes, remote_filter).fetchall()
                    for row in rows:
                        if row['name'] not in [n.name for n in folder.remote_notes]:
                            if helpers.confirm('Delete local note {}'.format(row['name'])):
                                return_code, stdout, stderr = helpers.run_applescript(delete_note_script,
                                                                                      folder.local_folder.name,
                                                                                      row['name'])
                                note_object = next((n for n in folder.local_notes if n.name == row['name']), None)
                                if note_object is not None:
                                    folder.local_notes.remove(note_object)
                                if return_code != 0:
                                    result['local_not_found'].append(row['name'])
                                else:
                                    result['local_deleted'].append(row['name'])
        except sqlite3.OperationalError as e:
            return False, repr(e)
        return True, "Local notes deleted."

    @staticmethod
    def delete_remote_notes(folder: NoteFolder, remote_folder: Path, result: dict) -> tuple[bool, str]:
        """
        Delete notes from remote which were deleted locally.

        :param folder: the folder data.
        :param remote_folder: the remote folder.
        :param result: dictionary where results are appended.

        :returns:

            -success (:py:class:`bool`) - true if remote notes are successfully deleted.

            -data (:py:class:`str`) - error message on failure, or success message.
        """
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_local_notes = "SELECT * FROM tb_note WHERE folder = ? AND location = ?"
                    local_filter = (folder.local_folder.name, 'local')
                    rows = cursor.execute(sql_local_notes, local_filter).fetchall()
                    for row in rows:
                        if row['uuid'] not in [n.uuid for n in folder.local_notes]:
                            try:
                                remote_note = remote_folder / folder.remote_folder.name / (row['name'] + '.md')
                                if helpers.confirm('Delete remote note {}'.format(row['name'])):
                                    Path.unlink(remote_note)
                                    note_object = next((n for n in folder.remote_notes if n.name == row['name']), None)
                                    for attachment in note_object.attachments:
                                        attachment.delete_remote()
                                    if note_object is not None:
                                        folder.remote_notes.remove(note_object)
                                    result['remote_deleted'].append(row['name'])
                            except FileNotFoundError:
                                result['remote_not_found'].append(row['name'])
        except sqlite3.OperationalError as e:
            return False, repr(e)
        return True, "Remote notes deleted."

    @staticmethod
    def sync_note_deletions(remote_folder: Path) -> tuple[bool, str] | tuple[bool, dict]:
        """
        Synchronises deletions to notes.

        The list of notes found during the last sync is loaded from SQLite and compared to the local and remote notes
        found now. Any notes in the database which are no longer present will then have their counterpart deleted. For
        example, if the local note *foo* is deleted, the remote note *foo* will be deleted during sync.

        Note that note deletions only apply in the sync direction. In the example above, *foo* will only be deleted if
        ``sync_direction`` is set to ``SYNC_LOCAL_TO_REMOTE`` or ``SYNC_BOTH``.

        On success, this method returns a dictionary with changes, containing the following keys:

        - ``remote_deleted`` - name of deleted remote notes as :py:class:`List[str]`.
        - ``local_deleted`` - name of deleted local notes as :py:class:`List[str]`.
        - ``remote_not_found`` - name of notes marked for remote deletion which were not found as :py:class:`List[str]`.
        - ``local_not_found`` - name of notes marked for local deletion which were not found as :py:class:`List[str]`.

        A note not being found is not considered an error, as the user may have deleted the note manually prior to the
        sync running.

        :param remote_folder: Path to the folder on the filesystem containing the remote notes.

        :returns:

            -success (:py:class:`bool`) - true if note deletions are successfully synchronised.

            -data (:py:class:`str` | :py:class`dict`) - error message on failure, or result as above on success.
        """
        success, message = NoteFolder.seed_note_table()
        if not success:
            return False, message

        result = {
            'remote_deleted': [],
            'local_deleted': [],
            'remote_not_found': [],
            'local_not_found': []
        }

        for folder in NoteFolder.FOLDER_LIST:
            if folder.sync_direction == NoteFolder.SYNC_NONE:
                continue

            success, data = folder.load_local_notes()
            if not success:
                return False, 'Failed to load local notes: {}'.format(data)
            success, data = folder.load_remote_notes()
            if not success:
                return False, 'Failed to load remote notes: {}'.format(data)

            # Delete remote notes which were deleted locally
            if folder.sync_direction == NoteFolder.SYNC_LOCAL_TO_REMOTE or folder.sync_direction == NoteFolder.SYNC_BOTH:
                NoteFolder.delete_remote_notes(folder, remote_folder, result)

            # Delete local notes which were deleted remotely
            if folder.sync_direction == NoteFolder.SYNC_REMOTE_TO_LOCAL or folder.sync_direction == NoteFolder.SYNC_BOTH:
                NoteFolder.delete_local_notes(folder, result)

        return True, result

    @staticmethod
    def reset_list():
        """
        Reset the folder list to empty.
        """
        NoteFolder.FOLDER_LIST.clear()


class LocalNoteFolder:
    """
    Represents a local folder storing notes.
    """

    def __init__(self, name: str, uuid: str | None = None):
        """
        Create a new local folder instance. The folder is not actually created until the ``create()`` method is called.

        :param name: the name of the local folder.
        :param uuid: the UUID of the local folder.
        """
        self.uuid: str = uuid
        self.name: str = name

    def create(self) -> tuple[bool, str]:
        """
        Creates this folder locally by calling an AppleScript script.

        :returns:

            -success (:py:class:`bool`) - true if local folder is successfully created.

            -data (:py:class:`str`) - error message on failure, or UUID on success.

        """
        create_folder_script = notescript.create_folder_script
        return_code, uuid, stderr = helpers.run_applescript(create_folder_script, self.name)
        self.uuid = uuid
        return (True, uuid) if return_code == 0 else \
            (False, 'Error creating local folder {0}: {1}'.format(self.name, stderr))

    def delete(self) -> tuple[bool, str]:
        """
        Delete the local folder with this object's name by calling an AppleScript script.

        :returns:

            -success (:py:class:`bool`) - true if local folder is successfully deleted.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
        delete_folder_script = notescript.delete_folder_script
        return_code, stdout, stderr = helpers.run_applescript(delete_folder_script, self.name)
        return (True, 'Folder {} deleted.'.format(self.name)) if return_code == 0 else \
            (True, 'Local folder {0} was probably manually deleted: {1}'.format(self.name, stderr))

    def __str__(self):
        return "Local Folder: {}".format(self.name)


class RemoteNoteFolder:
    """
    Represents a remote folder for storing notes.
    """

    def __init__(self, path: Path, name: str):
        """
        Create a new remote folder instance. The folder is not actually created until the ``create()`` method is called.

        :param path: path where to create remote folder. Must include folder name.
        :param name: name of the local folder.
        """
        self.path: Path = path
        self.name: str = name

    def create(self) -> tuple[bool, str]:
        """
        Creates the remote folder by adding a folder to the local filesystem which synchronises to remote.

        :returns:

            -success (:py:class:`bool`) - true if remote folder is successfully created.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
        try:
            self.path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return False, 'Error creating remote folder {0}: {1}'.format(self.name, e)
        return True, 'Remote folder {} created.'.format(self.name)

    def delete(self) -> tuple[bool, str]:
        """
        Delete the remote folder with this object's name.

        :returns:

            -success (:py:class:`bool`) - true if remote folder is successfully deleted.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
        try:
            if os.path.exists(self.path):
                shutil.rmtree(self.path)
            else:
                return True, 'Remote folder {} was already deleted.'.format(self.name)
        except OSError as e:
            return False, 'Error deleting remote folder {0}: {1}'.format(self.name, e)
        return True, 'Remote folder {} deleted.'.format(self.name)

    def __str__(self):
        return "Remote Folder: {}".format(self.name)
