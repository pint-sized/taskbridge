from __future__ import annotations

import copy
import glob
import os
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import List

import helpers
from notes.model import notescript
from notes.model.note import Note


class NoteFolder:
    FOLDER_LIST: List[NoteFolder] = []

    SYNC_NONE: int = 0
    SYNC_LOCAL_TO_REMOTE: int = 1
    SYNC_REMOTE_TO_LOCAL: int = 2
    SYNC_BOTH: int = 3

    def __init__(self,
                 local_folder: LocalNoteFolder | None = None,
                 remote_folder: RemoteNoteFolder | None = None,
                 sync_direction: int = SYNC_NONE):
        self.local_folder: LocalNoteFolder = local_folder
        self.remote_folder: RemoteNoteFolder = remote_folder
        self.sync_direction: int = sync_direction
        self.local_notes: List[Note] = []
        self.remote_notes: List[Note] = []
        NoteFolder.FOLDER_LIST.append(self)

    def load_local_notes(self) -> tuple[bool, str] | tuple[bool, int]:
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

    def sync_notes(self) -> tuple[bool, dict] | tuple[bool, str]:
        if self.sync_direction == NoteFolder.SYNC_NONE:
            return True, 'Folder {} is set to NO SYNC so skipped'.format(self.local_folder.name)

        result = {
            'remote_added': [],
            'remote_updated': [],
            'local_added': [],
            'local_updated': []
        }

        def sync_local_to_remote(local: Note, remote: Note | None) -> tuple[bool, str]:
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

        def sync_remote_to_local(local: Note, remote: Note) -> tuple[bool, str]:
            if remote is not None and local.modified_date < remote.modified_date:
                key = 'local_updated'
                local = copy.deepcopy(remote)
                if helpers.confirm("Update local note {}".format(local.name)):
                    i_success, i_data = local.update_local(self.local_folder.name)
                    if not i_success:
                        return False, i_data
                    result[key].append(local.name)
                    return True, i_data
                return True, ''

        # Sync local notes to remote
        for local_note in self.local_notes:
            # Get the associated remote note, if any
            remote_note = next((n for n in self.remote_notes
                                if n.uuid == local_note.uuid or n.name == local_note.name), None)

            if self.sync_direction == NoteFolder.SYNC_LOCAL_TO_REMOTE:
                # Sync Local --> Remote if remote doesn't exist or is outdated
                success, data = sync_local_to_remote(local_note, remote_note)
                if not success:
                    return False, data
            elif self.sync_direction == NoteFolder.SYNC_REMOTE_TO_LOCAL:
                # Sync Local <-- Remote if local is outdated
                success, data = sync_remote_to_local(local_note, remote_note)
                if not success:
                    return False, data
            elif self.sync_direction == NoteFolder.SYNC_BOTH:
                # Sync Local <--> Remote, depending on which is newer
                if remote_note is None or local_note.modified_date > remote_note.modified_date:
                    success, data = sync_local_to_remote(local_note, remote_note)
                    if not success:
                        return False, data
                elif remote_note.modified_date > local_note.modified_date:
                    success, data = sync_remote_to_local(local_note, remote_note)
                    if not success:
                        return False, data

        # Sync remote notes to local
        for remote_note in self.remote_notes:
            local_note = next((n for n in self.local_notes
                               if n.uuid == remote_note.modified_date or n.name == remote_note.name), None)
            if (self.sync_direction == NoteFolder.SYNC_REMOTE_TO_LOCAL or self.sync_direction == NoteFolder.SYNC_BOTH) and local_note is None:
                # Local note is missing and so needs to be created
                key_change = 'local_added'
                local_note = copy.deepcopy(remote_note)
                if helpers.confirm("Create local note {}".format(local_note.name)):
                    success, data = local_note.create_local(self.local_folder.name)
                    if not success:
                        return False, data
                    result[key_change].append(local_note.name)

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
        remote_note_folders = []
        for root, dirs, files in os.walk(remote_notes_path):
            for remote_dir in dirs:
                if not remote_dir.startswith("."):
                    remote_folder = RemoteNoteFolder(remote_notes_path / remote_dir, remote_dir)
                    remote_note_folders.append(remote_folder)
        return True, remote_note_folders

    @staticmethod
    def create_linked_folders(local_folders: List[LocalNoteFolder],
                              remote_folders: List[RemoteNoteFolder],
                              remote_notes_path: Path,
                              associations: dict) -> tuple[bool, str]:

        # Create Local --> Remote Associations
        for local_folder in local_folders:
            # Check which local folders need to be synced with remote folders
            if local_folder.name in associations['bi_directional'] or local_folder.name in associations['local_to_remote']:
                remote_folder = next((f for f in remote_folders if f.name == local_folder.name), None)
                # Create remote folder since it doesn't exist
                if remote_folder is None:
                    remote_folder = RemoteNoteFolder(remote_notes_path / local_folder.name, local_folder.name)
                    if helpers.confirm('Create remote folder {}'.format(remote_folder.name)):
                        remote_folder.create()
                if local_folder.name in associations['bi_directional']:
                    sync_direction = NoteFolder.SYNC_BOTH
                elif local_folder.name in associations['local_to_remote']:
                    sync_direction = NoteFolder.SYNC_LOCAL_TO_REMOTE
                elif local_folder.name in associations['remote_to_local']:
                    sync_direction = NoteFolder.SYNC_REMOTE_TO_LOCAL
                else:
                    sync_direction = NoteFolder.SYNC_NONE
                NoteFolder(local_folder, remote_folder, sync_direction)

        # Create Remote --> Local Associations
        for remote_folder in remote_folders:
            existing_association = next(
                (f for f in NoteFolder.FOLDER_LIST if f.remote_folder and f.remote_folder.name == remote_folder.name),
                None)
            if existing_association is not None:
                # We've already associated this folder, so move to the next one
                continue
            if remote_folder.name in associations['bi_directional'] or remote_folder.name in associations['remote_to_local']:
                local_folder = next((f for f in local_folders if f.name == remote_folder.name), None)
                # Create local folder since it doesn't exist
                if local_folder is None:
                    local_folder = LocalNoteFolder(remote_folder.name)
                    if helpers.confirm('Create local folder {}'.format(local_folder.name)):
                        local_folder.create()
                if remote_folder.name in associations['bi_directional']:
                    sync_direction = NoteFolder.SYNC_BOTH
                elif remote_folder.name in associations['local_to_remote']:
                    sync_direction = NoteFolder.SYNC_LOCAL_TO_REMOTE
                elif remote_folder.name in associations['remote_to_local']:
                    sync_direction = NoteFolder.SYNC_REMOTE_TO_LOCAL
                else:
                    sync_direction = NoteFolder.SYNC_NONE
                NoteFolder(local_folder, remote_folder, sync_direction)

        success, data = NoteFolder.persist_folders()
        if not success:
            return False, data
        return True, 'Folder associations created.'

    @staticmethod
    def seed_folder_table() -> tuple[bool, str]:
        try:
            con = sqlite3.connect(helpers.db_folder())
            cur = con.cursor()
            sql_create_folder_table = """CREATE TABLE IF NOT EXISTS tb_folder (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                local_uuid TEXT,
                local_name TEXT,
                remote_path TEXT,
                remote_name TEXT,
                sync_direction INT
                );"""
            cur.execute(sql_create_folder_table)
        except sqlite3.OperationalError as e:
            return False, repr(e)
        return True, 'tb_folder table created'

    @staticmethod
    def persist_folders() -> tuple[bool, str]:
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
            con = sqlite3.connect(helpers.db_folder())
            cur = con.cursor()
            sql_delete_folders = "DELETE FROM tb_folder"
            cur.execute(sql_delete_folders)
            sql_insert_folders = """INSERT INTO tb_folder(local_uuid, local_name, remote_path, remote_name, sync_direction)
            VALUES (?, ?, ?, ?, ?)
            """
            cur.executemany(sql_insert_folders, folders)
            con.commit()
        except sqlite3.OperationalError as e:
            return False, repr(e)
        return True, 'Folders stored in tb_folder'

    @staticmethod
    def sync_folder_deletions(discovered_local: List[LocalNoteFolder], discovered_remote: List[RemoteNoteFolder]):
        success, message = NoteFolder.seed_folder_table()
        if not success:
            return False, message

        # Bi-Directional or Local --> Remote Folders
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

        # Local <-- Remote Folders
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

        # Empty Table
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    cursor.execute("DELETE FROM tb_folder")
        except sqlite3.OperationalError as e:
            return False, 'Error deleting folder table: {}'.format(e)

        return True, 'Folder deletions synchronised'

    @staticmethod
    def seed_note_table() -> tuple[bool, str]:
        try:
            con = sqlite3.connect(helpers.db_folder())
            cur = con.cursor()
            sql_create_note_table = """CREATE TABLE IF NOT EXISTS tb_note (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    folder TEXT,
                    location TEXT,
                    uuid TEXT,
                    name TEXT,
                    created TEXT,
                    modified TEXT
                    );"""
            cur.execute(sql_create_note_table)
        except sqlite3.OperationalError as e:
            return False, repr(e)
        return True, 'tb_note table created'

    @staticmethod
    def persist_notes() -> tuple[bool, str]:
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
            con = sqlite3.connect(helpers.db_folder())
            cur = con.cursor()
            sql_delete_folders = "DELETE FROM tb_note"
            cur.execute(sql_delete_folders)
            sql_insert_notes = """INSERT INTO tb_note(folder, location, uuid, name, created, modified)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """
            cur.executemany(sql_insert_notes, notes)
            con.commit()
        except sqlite3.OperationalError as e:
            return False, repr(e)
        return True, 'Notes stored in tb_notes'

    @staticmethod
    def sync_note_deletions(remote_folder: Path) -> tuple[bool, str] | tuple[bool, dict]:
        success, message = NoteFolder.seed_note_table()
        if not success:
            return False, message

        delete_note_script = notescript.delete_note_script

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

            # Delete local notes which were deleted remotely
            if folder.sync_direction == NoteFolder.SYNC_REMOTE_TO_LOCAL or folder.sync_direction == NoteFolder.SYNC_BOTH:
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
                                        return_code, stdout, stderr = helpers.run_applescript(delete_note_script, folder.local_folder.name, row['name'])
                                        note_object = next((n for n in folder.local_notes if n.name == row['name']), None)
                                        if note_object is not None:
                                            folder.local_notes.remove(note_object)
                                        if return_code != 0:
                                            result['local_note_found'].append(row['name'])
                                        else:
                                            result['local_deleted'].append(row['name'])
                except sqlite3.OperationalError as e:
                    return False, repr(e)

        return True, result


class LocalNoteFolder:
    def __init__(self, name: str, uuid: str | None = None):
        self.uuid: str = uuid
        self.name: str = name

    def create(self) -> tuple[bool, str]:
        create_folder_script = notescript.create_folder_script
        return_code, uuid, stderr = helpers.run_applescript(create_folder_script, self.name)
        self.uuid = uuid
        return (True, uuid) if return_code == 0 else \
            (False, 'Error creating local folder {0}: {1}'.format(self.name, stderr))

    def delete(self) -> tuple[bool, str]:
        delete_folder_script = notescript.delete_folder_script
        return_code, stdout, stderr = helpers.run_applescript(delete_folder_script, self.name)
        return (True, 'Folder {} deleted.'.format(self.name)) if return_code == 0 else \
            (True, 'Local folder {0} was probably manually deleted: {1}'.format(self.name, stderr))

    def __str__(self):
        return "Local Folder: {}".format(self.name)


class RemoteNoteFolder:
    def __init__(self, path: Path, name: str):
        self.path: Path = path
        self.name: str = name

    def create(self) -> tuple[bool, str]:
        try:
            self.path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return False, 'Error creating remote folder {0}: {1}'.format(self.name, e)
        return True, 'Remote folder {} created.'.format(self.name)

    def delete(self) -> tuple[bool, str]:
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
