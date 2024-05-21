import copy
import datetime
import os.path
import pathlib
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path
from unittest import mock

import pytest
from decouple import config

from taskbridge import helpers
from taskbridge.notes.model import notescript
from taskbridge.notes.model.note import Note
from taskbridge.notes.model.notefolder import NoteFolder, LocalNoteFolder, RemoteNoteFolder

TEST_ENV = config('TEST_ENV', default='remote')


class TestNoteFolder:
    TMP_FOLDER = Path("/tmp")
    RES_DIR = Path()
    MOCK_TESTNOTE1_STAGED = ''
    MOCK_TESTNOTE1_MD = ''
    MOCK_TESTNOTE2_HTML = ''
    MOCK_TESTNOTE2_MD = ''

    @classmethod
    def setup_class(cls):
        TestNoteFolder.RES_DIR = pathlib.Path(__file__).parent.resolve() / 'resources'
        with open(TestNoteFolder.RES_DIR / 'mock_testnote1_staged.staged') as fp:
            TestNoteFolder.MOCK_TESTNOTE1_STAGED = fp.read()
        with open(TestNoteFolder.RES_DIR / 'mock_testnote1_md.md') as fp:
            TestNoteFolder.MOCK_TESTNOTE1_MD = fp.read()
        with open(TestNoteFolder.RES_DIR / 'mock_testnote2_html.html') as fp:
            TestNoteFolder.MOCK_TESTNOTE2_HTML = fp.read()
        with open(TestNoteFolder.RES_DIR / 'mock_testnote2_md.md') as fp:
            TestNoteFolder.MOCK_TESTNOTE2_MD = fp.read()

    @staticmethod
    def __create_remote_note() -> Note:
        staged_location = TestNoteFolder.TMP_FOLDER / 'testnote1.staged'
        with open(staged_location, 'w') as fp:
            fp.write(TestNoteFolder.MOCK_TESTNOTE1_STAGED)

        return Note.create_from_local(TestNoteFolder.MOCK_TESTNOTE1_STAGED, TestNoteFolder.TMP_FOLDER)

    @staticmethod
    def __create_local_note() -> Note:
        remote_content = """testnote2

This is a remote note. 

![ladybird.jpg](.attachments.295/ladybird.jpg)


That was a ladybird"""
        remote_file_name = "testnote2.md"
        test_location = TestNoteFolder.RES_DIR / '.attachments.295'
        remote_location = Path("/tmp/Test")
        pathlib.Path(remote_location / ".attachments.295").mkdir(parents=True, exist_ok=True)
        with open(remote_location / remote_file_name, 'w') as fp:
            fp.write(remote_content)
        shutil.copy(test_location / "ladybird.jpg", remote_location / ".attachments.295/")

        return Note.create_from_remote(remote_content, remote_location, remote_file_name)

    @staticmethod
    def __reset_test_folder(create_notes: bool = True):
        # Reset 'remote' folder
        remote_location = Path("/tmp/Test")
        if os.path.isdir(remote_location):
            shutil.rmtree(remote_location)

        # Reset 'local' folder
        delete_folder_script = """tell application "Notes"
set test_folders to every folder whose name is "Test"
repeat with test_folder in test_folders
    set test_notes to every note in test_folder
    repeat with test_note in test_notes
        delete test_note
    end repeat
    delete test_folder
end repeat
end tell"""
        helpers.run_applescript(delete_folder_script, 'Test')

        create_folder_script = notescript.create_folder_script
        helpers.run_applescript(create_folder_script, 'Test')

        if create_notes:
            # Create test note in remote folder
            note = TestNoteFolder.__create_remote_note()
            note.upsert_remote(Path("/tmp/Test"))

            # Create test note in local folder
            note = TestNoteFolder.__create_local_note()
            note.create_local("Test")

    @staticmethod
    def __get_test_folder() -> NoteFolder:
        lf = LocalNoteFolder('Test')
        rf = RemoteNoteFolder(TestNoteFolder.TMP_FOLDER / 'Test', 'Test')
        nf = NoteFolder(lf, rf, NoteFolder.SYNC_BOTH)
        return nf

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud")
    def test_load_local_notes(self):
        TestNoteFolder.__reset_test_folder()

        # Success
        test_folder = TestNoteFolder.__get_test_folder()
        success, data = test_folder.load_local_notes()
        assert success is True
        assert isinstance(data, int)
        assert data == 1

        # noinspection PyUnusedLocal
        def mock_run_applescript(script, *args):
            return 1, '', 'Error'

        # Fail
        with mock.patch('taskbridge.helpers.run_applescript', mock_run_applescript):
            test_folder = TestNoteFolder.__get_test_folder()
            success, data = test_folder.load_local_notes()
            assert success is False
            assert data == 'Error'

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem.")
    def test_load_remote_notes(self):
        TestNoteFolder.__reset_test_folder()

        test_folder = TestNoteFolder.__get_test_folder()
        success, data = test_folder.load_remote_notes()
        assert success is True
        assert isinstance(data, int)
        assert data == 1

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and local filesystem.")
    def test_sync_local_note_to_remote(self):
        TestNoteFolder.__reset_test_folder()

        # Success
        test_folder = TestNoteFolder.__get_test_folder()
        local_note = TestNoteFolder.__create_local_note()
        result = {
            'remote_added': [],
            'remote_updated': []
        }
        success, data = test_folder.sync_local_note_to_remote(local_note, None, result)
        assert success is True
        assert len(result['remote_added']) == 1

        # noinspection PyUnusedLocal
        def mock_upsert_remote(inst, remote_path):
            return False, 'Fail'

        # Fail
        with mock.patch('taskbridge.notes.model.note.Note.upsert_remote', mock_upsert_remote):
            success, data = test_folder.sync_local_note_to_remote(local_note, None, result)
            assert success is False
            assert data == 'Fail'

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and local filesystem.")
    def test_sync_remote_note_to_local(self):
        TestNoteFolder.__reset_test_folder()

        # Success - Local note is updated
        test_folder = TestNoteFolder.__get_test_folder()
        local_note = TestNoteFolder.__create_local_note()
        remote_note = TestNoteFolder.__create_local_note()
        remote_note.modified_date = datetime.datetime.now()
        result = {
            'local_updated': []
        }
        success, data = test_folder.sync_remote_note_to_local(local_note, remote_note, result)
        assert success is True
        assert len(result['local_updated']) == 1

        # Success - Local note is not updated as it is newer
        local_note.modified_date = datetime.datetime.now()
        result = {
            'local_updated': []
        }
        success, data = test_folder.sync_remote_note_to_local(local_note, remote_note, result)
        assert success is True
        assert isinstance(data, str)

        # noinspection PyUnusedLocal
        def mock_update_local(inst, folder):
            return False, 'Fail'

        # Fail
        with mock.patch('taskbridge.notes.model.note.Note.update_local', mock_update_local):
            remote_note.modified_date = datetime.datetime.now()
            success, data = test_folder.sync_remote_note_to_local(local_note, remote_note, result)
            assert success is False
            assert data == 'Fail'

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and local filesystem.")
    def test_sync_local_to_remote(self):
        TestNoteFolder.__reset_test_folder(create_notes=False)

        # Sync BOTH. Remote doesn't exist.
        note = TestNoteFolder.__create_local_note()
        note.create_local("Test")
        test_folder = TestNoteFolder.__get_test_folder()
        test_folder.local_notes.append(note)
        result = {
            'remote_added': [],
            'remote_updated': []
        }
        success, data = test_folder.sync_local_to_remote(result)
        assert success is True
        assert len(result['remote_added']) == 1
        assert len(result['remote_updated']) == 0

        # Fail
        # noinspection PyUnusedLocal
        def mock_sync_local_note_to_remote(inst, local, remote, res):
            return False, 'Fail'

        with mock.patch('taskbridge.notes.model.notefolder.NoteFolder.sync_local_note_to_remote',
                        mock_sync_local_note_to_remote):
            success, data = test_folder.sync_local_to_remote(result)
            assert success is False

        # Sync BOTH. Remote exists and is newer.
        local_note = TestNoteFolder.__create_local_note()
        local_note.create_local("Test")
        remote_note = TestNoteFolder.__create_local_note()
        remote_note.create_local("Test")
        remote_note.modified_date = datetime.datetime.now()
        test_folder = TestNoteFolder.__get_test_folder()
        test_folder.local_notes.append(local_note)
        test_folder.remote_notes.append(remote_note)
        result = {
            'local_updated': []
        }
        success, data = test_folder.sync_local_to_remote(result)
        assert success is True
        assert len(result['local_updated']) == 1

        # Sync Local --> Remote.
        note = TestNoteFolder.__create_local_note()
        note.create_local("Test")
        test_folder = TestNoteFolder.__get_test_folder()
        test_folder.sync_direction = NoteFolder.SYNC_LOCAL_TO_REMOTE
        test_folder.local_notes.append(note)
        result = {
            'remote_added': [],
            'remote_updated': []
        }
        success, data = test_folder.sync_local_to_remote(result)
        assert success is True
        assert len(result['remote_added']) == 1
        assert len(result['remote_updated']) == 0

        # Sync Local <-- Remote.
        local_note = TestNoteFolder.__create_local_note()
        local_note.create_local("Test")
        remote_note = TestNoteFolder.__create_local_note()
        remote_note.create_local("Test")
        remote_note.modified_date = datetime.datetime.now()
        test_folder = TestNoteFolder.__get_test_folder()
        test_folder.sync_direction = NoteFolder.SYNC_REMOTE_TO_LOCAL
        test_folder.local_notes.append(local_note)
        test_folder.remote_notes.append(remote_note)
        result = {
            'local_updated': []
        }
        success, data = test_folder.sync_local_to_remote(result)
        assert success is True
        assert len(result['local_updated']) == 1

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and local filesystem.")
    def test_sync_remote_to_local(self):
        TestNoteFolder.__reset_test_folder(create_notes=False)

        # Sync BOTH. Local doesn't exist.
        note = TestNoteFolder.__create_remote_note()
        note.upsert_remote(Path("/tmp/Test"))
        test_folder = TestNoteFolder.__get_test_folder()
        test_folder.remote_notes.append(note)
        result = {
            'local_added': []
        }
        success, data = test_folder.sync_remote_to_local(result)
        assert success is True
        assert len(result['local_added']) == 1

        # Fail
        # noinspection PyUnusedLocal
        def mock_create_local(inst, folder):
            return False, 'Fail'

        with mock.patch('taskbridge.notes.model.note.Note.create_local', mock_create_local):
            success, data = test_folder.sync_remote_to_local(result)
            assert success is False

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and local filesystem.")
    def test_sync_notes(self):
        TestNoteFolder.__reset_test_folder(create_notes=False)
        test_folder = TestNoteFolder.__get_test_folder()
        remote_note = TestNoteFolder.__create_remote_note()
        remote_note.upsert_remote(Path("/tmp/Test"))
        test_folder.remote_notes.append(remote_note)
        local_note = TestNoteFolder.__create_local_note()
        local_note.create_local("Test")
        test_folder.local_notes.append(local_note)

        # Success - no sync
        test_folder.sync_direction = NoteFolder.SYNC_NONE
        success, data = test_folder.sync_notes()
        assert success is True
        assert isinstance(data, dict)
        assert len(data['remote_added']) == 0
        assert len(data['remote_updated']) == 0
        assert len(data['local_added']) == 0
        assert len(data['local_updated']) == 0

        # Success - Sync with no counterpart
        test_folder.sync_direction = NoteFolder.SYNC_BOTH
        success, data = test_folder.sync_notes()
        assert success is True
        assert len(data['remote_added']) == 1
        assert len(data['local_added']) == 1

        # Success - Sync with updated counterpart
        old_remote = copy.deepcopy(remote_note)
        old_local = copy.deepcopy(local_note)
        test_folder.local_notes[0].modified_date = datetime.datetime.now()
        test_folder.remote_notes[0].modified_date = datetime.datetime.now()
        test_folder.local_notes.append(old_remote)
        test_folder.remote_notes.append(old_local)
        success, data = test_folder.sync_notes()
        assert success is True
        assert len(data['remote_updated']) == 1
        assert len(data['local_updated']) == 1

        # Fail (to persist)
        def mock_persist_notes():
            return False, 'Fail'

        with mock.patch('taskbridge.notes.model.notefolder.NoteFolder.persist_notes', mock_persist_notes):
            success, data = test_folder.sync_notes()
            assert success is False

    def test___str(self):
        test_folder = TestNoteFolder.__get_test_folder()

        test_folder.sync_direction = NoteFolder.SYNC_BOTH
        assert test_folder.__str__() == "Local: Test <> Remote: Test : Sync: LOCAL <--> REMOTE"

        test_folder.sync_direction = NoteFolder.SYNC_LOCAL_TO_REMOTE
        assert test_folder.__str__() == "Local: Test <> Remote: Test : Sync: LOCAL --> REMOTE"

        test_folder.sync_direction = NoteFolder.SYNC_REMOTE_TO_LOCAL
        assert test_folder.__str__() == "Local: Test <> Remote: Test : Sync: LOCAL <-- REMOTE"

        test_folder.sync_direction = NoteFolder.SYNC_NONE
        assert test_folder.__str__() == "Local: Test <> Remote: Test : Sync: NO SYNC"

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud")
    def test_load_local_folders(self):
        # Success
        success, folders = NoteFolder.load_local_folders()
        assert success is True
        assert len(folders) > 1

        # Fail
        # noinspection PyUnusedLocal
        def mock_run_applescript(script):
            return 1, '', 'Fail'

        with mock.patch('taskbridge.helpers.run_applescript', mock_run_applescript):
            success, folders = NoteFolder.load_local_folders()
            assert success is False

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem.")
    def test_load_remote_folders(self):
        # Success
        success, folders = NoteFolder.load_remote_folders(Path('/tmp'))
        assert success is True
        assert len(folders) > 1

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and local filesystem.")
    def test_assoc_local_remote(self):
        remote_location = Path("/tmp/Notes")
        if os.path.isdir(remote_location):
            shutil.rmtree(remote_location)
        pathlib.Path(remote_location).mkdir(parents=True, exist_ok=True)

        folder_both = LocalNoteFolder("Both")
        folder_local_to_remote = LocalNoteFolder("LocalToRemote")
        folder_remote_to_local = LocalNoteFolder('RemoteToLocal')
        folder_local_only = LocalNoteFolder("LocalOnly")

        local_folders = [folder_both, folder_local_to_remote, folder_remote_to_local, folder_local_only]
        remote_folders = []
        associations = {
            'bi_directional': ['Both'],
            'local_to_remote': ['LocalToRemote'],
            'remote_to_local': ['RemoteToLocal']
        }
        NoteFolder.FOLDER_LIST.clear()

        NoteFolder.assoc_local_remote(local_folders, remote_folders, remote_location, associations)
        assert len(NoteFolder.FOLDER_LIST) == 4

        nf_both = next((f for f in NoteFolder.FOLDER_LIST if f.local_folder.name == "Both"), None)
        assert nf_both is not None
        assert nf_both.sync_direction == NoteFolder.SYNC_BOTH

        nf_local_remote = next((f for f in NoteFolder.FOLDER_LIST if f.local_folder.name == "LocalToRemote"), None)
        assert nf_local_remote is not None
        assert nf_local_remote.sync_direction == NoteFolder.SYNC_LOCAL_TO_REMOTE

        nf_remote_local = next((f for f in NoteFolder.FOLDER_LIST if f.local_folder.name == "RemoteToLocal"), None)
        assert nf_remote_local is not None
        assert nf_remote_local.sync_direction == NoteFolder.SYNC_REMOTE_TO_LOCAL

        nf_local_only = next((f for f in NoteFolder.FOLDER_LIST if f.local_folder.name == "LocalOnly"), None)
        assert nf_local_only is not None
        assert nf_local_only.sync_direction == NoteFolder.SYNC_NONE

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and local filesystem.")
    def test_assoc_remote_local(self):
        remote_location = Path("/tmp/Notes")
        if os.path.isdir(remote_location):
            shutil.rmtree(remote_location)

        folder_both = RemoteNoteFolder(Path("/tmp/Notes/Both"), "Both")
        pathlib.Path(remote_location / "Both").mkdir(parents=True, exist_ok=True)
        folder_local_to_remote = RemoteNoteFolder(Path("/tmp/Notes/LocalToRemote"), "LocalToRemote")
        pathlib.Path(remote_location / "LocalToRemote").mkdir(parents=True, exist_ok=True)
        folder_remote_to_local = RemoteNoteFolder(Path("/tmp/Notes/RemoteToLocal"), 'RemoteToLocal')
        pathlib.Path(remote_location / "RemoteToLocal").mkdir(parents=True, exist_ok=True)
        folder_remote_only = RemoteNoteFolder(Path("/tmp/Notes/RemoteOnly"), "RemoteOnly")
        pathlib.Path(remote_location / "RemoteOnly").mkdir(parents=True, exist_ok=True)

        local_folders = []
        remote_folders = [folder_both, folder_local_to_remote, folder_remote_to_local, folder_remote_only]
        associations = {
            'bi_directional': ['Both'],
            'local_to_remote': ['LocalToRemote'],
            'remote_to_local': ['RemoteToLocal']
        }
        NoteFolder.FOLDER_LIST.clear()

        NoteFolder.assoc_remote_local(local_folders, remote_folders, associations)
        assert len(NoteFolder.FOLDER_LIST) == 4

        nf_both = next((f for f in NoteFolder.FOLDER_LIST if f.remote_folder.name == "Both"), None)
        assert nf_both is not None
        assert nf_both.sync_direction == NoteFolder.SYNC_BOTH

        nf_local_remote = next((f for f in NoteFolder.FOLDER_LIST if f.remote_folder.name == "LocalToRemote"), None)
        assert nf_local_remote is not None
        assert nf_local_remote.sync_direction == NoteFolder.SYNC_LOCAL_TO_REMOTE

        nf_remote_local = next((f for f in NoteFolder.FOLDER_LIST if f.remote_folder.name == "RemoteToLocal"), None)
        assert nf_remote_local is not None
        assert nf_remote_local.sync_direction == NoteFolder.SYNC_REMOTE_TO_LOCAL

        nf_remote_only = next((f for f in NoteFolder.FOLDER_LIST if f.remote_folder.name == "RemoteOnly"), None)
        assert nf_remote_only is not None
        assert nf_remote_only.sync_direction == NoteFolder.SYNC_NONE

        # Clean up
        delete_folder_script = notescript.delete_folder_script
        helpers.run_applescript(delete_folder_script, 'Both')
        helpers.run_applescript(delete_folder_script, 'RemoteToLocal')

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and local filesystem.")
    def test_create_linked_folders(self):
        remote_location = Path("/tmp/Notes")
        if os.path.isdir(remote_location):
            shutil.rmtree(remote_location)

        folder_both_local = LocalNoteFolder("Both")
        folder_both_remote = RemoteNoteFolder(Path("/tmp/Notes/Both"), "Both")
        pathlib.Path(remote_location / "Both").mkdir(parents=True, exist_ok=True)
        folder_local_to_remote = LocalNoteFolder("LocalToRemote")
        folder_remote_to_local = RemoteNoteFolder(Path("/tmp/Notes/RemoteToLocal"), "RemoteToLocal")
        pathlib.Path(remote_location / "RemoteToLocal").mkdir(parents=True, exist_ok=True)
        folder_local_only = LocalNoteFolder("LocalOnly")
        folder_remote_only = RemoteNoteFolder(Path("/tmp/Notes/RemoteOnly"), "RemoteOnly")
        pathlib.Path(remote_location / "RemoteOnly").mkdir(parents=True, exist_ok=True)

        local_folders = [folder_both_local, folder_local_to_remote, folder_local_only]
        remote_folders = [folder_both_remote, folder_remote_to_local, folder_remote_only]
        associations = {
            'bi_directional': ['Both'],
            'local_to_remote': ['LocalToRemote'],
            'remote_to_local': ['RemoteToLocal']
        }
        NoteFolder.FOLDER_LIST.clear()

        NoteFolder.create_linked_folders(local_folders, remote_folders, remote_location, associations)
        assert len(NoteFolder.FOLDER_LIST) == 5

        nf_both = next((f for f in NoteFolder.FOLDER_LIST if f.local_folder.name == "Both"), None)
        assert nf_both is not None
        assert nf_both.sync_direction == NoteFolder.SYNC_BOTH

        nf_local_to_remote = next((f for f in NoteFolder.FOLDER_LIST if f.local_folder.name == "LocalToRemote"), None)
        assert nf_local_to_remote is not None
        assert nf_local_to_remote.sync_direction == NoteFolder.SYNC_LOCAL_TO_REMOTE

        nf_remote_to_local = next(
            (f for f in NoteFolder.FOLDER_LIST if f.remote_folder is not None and f.remote_folder.name == "RemoteToLocal"),
            None)
        assert nf_remote_to_local is not None
        assert nf_remote_to_local.sync_direction == NoteFolder.SYNC_REMOTE_TO_LOCAL

        nf_local_only = next((f for f in NoteFolder.FOLDER_LIST if f.local_folder.name == "LocalOnly"), None)
        assert nf_local_only is not None
        assert nf_local_only.sync_direction == NoteFolder.SYNC_NONE

        nf_remote_only = next(
            (f for f in NoteFolder.FOLDER_LIST if f.remote_folder is not None and f.remote_folder.name == "RemoteOnly"), None)
        assert nf_remote_only is not None
        assert nf_remote_only.sync_direction == NoteFolder.SYNC_NONE

        # Fail to persist

        def mock_persist_folders():
            return False, "Fail"

        with mock.patch("taskbridge.notes.model.notefolder.NoteFolder.persist_folders", mock_persist_folders):
            success, data = NoteFolder.create_linked_folders(local_folders, remote_folders, remote_location, associations)
            assert success is False

        # Clean up
        delete_folder_script = notescript.delete_folder_script
        helpers.run_applescript(delete_folder_script, 'RemoteToLocal')

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem.")
    def test_seed_folder_table(self):
        # Success
        NoteFolder.seed_folder_table()
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_table_exists = "SELECT name FROM sqlite_master WHERE type='table' AND name='tb_folder';"
                    table_result = cursor.execute(sql_table_exists)

                    table_list = [t for t in table_result if t['name'] == "tb_folder"]
                    assert len(table_list) == 1

                    sql_columns_exist = "PRAGMA table_info('tb_folder');"
                    columns_result = cursor.execute(sql_columns_exist)

                    columns = ['id', 'local_uuid', 'local_name', 'remote_path', 'remote_name', 'sync_direction']
                    for col in columns_result:
                        assert col['name'] in columns
        except sqlite3.OperationalError as e:
            assert False, repr(e)

        # Fail

        class MockSqlite3:
            def connect(self):
                raise MockSqlite3.OperationalError

            class OperationalError(BaseException):
                def __repr__(self):
                    return "Fail"

        with mock.patch('taskbridge.notes.model.notefolder.sqlite3', MockSqlite3):
            success, data = NoteFolder.seed_folder_table()
            assert success is False

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem.")
    def test_persist_folders(self):
        folder_local_to_remote = LocalNoteFolder("LocalToRemote")
        folder_remote_to_local = RemoteNoteFolder(Path("/tmp/Notes/RemoteToLocal"), "RemoteToLocal")

        NoteFolder.FOLDER_LIST.clear()
        NoteFolder.FOLDER_LIST.append(NoteFolder(folder_local_to_remote, None, NoteFolder.SYNC_LOCAL_TO_REMOTE))
        NoteFolder.FOLDER_LIST.append(NoteFolder(None, folder_remote_to_local, NoteFolder.SYNC_REMOTE_TO_LOCAL))
        NoteFolder.persist_folders()

        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_get_folders = "SELECT * FROM tb_folder;"
                    results = cursor.execute(sql_get_folders).fetchall()

                    for result in results:
                        if result['local_name'] == 'LocalToRemote':
                            assert result['sync_direction'] == NoteFolder.SYNC_LOCAL_TO_REMOTE
                        elif result['remote_name'] == 'RemoteToLocal':
                            assert result['sync_direction'] == NoteFolder.SYNC_REMOTE_TO_LOCAL
                        else:
                            assert False, 'Unrecognised record in tb_folder'
        except sqlite3.OperationalError as e:
            assert False, repr(e)

        # Clean Up
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_delete_containers = "DELETE FROM tb_folder"
                    cursor.execute(sql_delete_containers)
                    connection.commit()
        except sqlite3.OperationalError as e:
            print(e)

        # Fail
        class MockSqlite3:
            def connect(self):
                raise MockSqlite3.OperationalError

            class OperationalError(BaseException):
                def __repr__(self):
                    return "Fail"

        with mock.patch('taskbridge.notes.model.notefolder.sqlite3', MockSqlite3):
            success, data = NoteFolder.persist_folders()
            assert success is False

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and local filesystem.")
    def test_sync_bidirectional_local_deletions(self):
        NoteFolder.FOLDER_LIST.clear()

        # Create the folders
        local_folder_bi = LocalNoteFolder("folder_bi")
        local_folder_l2r = LocalNoteFolder("local_to_remote")
        local_folder_bi.create()
        local_folder_l2r.create()
        remote_folder_bi = RemoteNoteFolder(Path("/tmp/Notes/folder_bi"), "folder_bi")
        remote_folder_l2r = RemoteNoteFolder(Path("/tmp/Notes/local_to_remote"), "local_to_remote")
        remote_folder_bi.create()
        remote_folder_l2r.create()

        # Persist the folders
        NoteFolder.FOLDER_LIST.append(NoteFolder(local_folder_bi, remote_folder_bi, NoteFolder.SYNC_BOTH))
        NoteFolder.FOLDER_LIST.append(NoteFolder(local_folder_l2r, remote_folder_l2r, NoteFolder.SYNC_LOCAL_TO_REMOTE))
        success, data = NoteFolder.persist_folders()
        assert success is True

        # Delete the local folders
        local_folder_bi.delete()
        local_folder_l2r.delete()

        # Sync the deletions
        discovered_local = [LocalNoteFolder("Test")]
        success, data = NoteFolder.sync_bidirectional_local_deletions(discovered_local)
        assert success is True

        # Verify the deletions
        dirs = [d for d in os.listdir("/tmp/Notes/") if os.path.isdir(d)]
        assert 'folder_bi' not in dirs
        assert 'local_to_remote' not in dirs

        # Fail - SQL Error
        class MockSqlite3:
            def connect(self):
                raise MockSqlite3.OperationalError

            class OperationalError(BaseException):
                def __repr__(self):
                    return "Fail"

        with mock.patch('taskbridge.notes.model.notefolder.sqlite3', MockSqlite3):
            success, data = NoteFolder.sync_bidirectional_local_deletions(discovered_local)
            assert success is False

        # Fail - Deletion error

        # noinspection PyUnusedLocal
        def mock_delete(stuff):
            return False, "Fail"

        with mock.patch('taskbridge.notes.model.notefolder.RemoteNoteFolder.delete', mock_delete):
            success, data = NoteFolder.sync_bidirectional_local_deletions(discovered_local)
            assert success is False

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and local filesystem.")
    def test_sync_remote_deletions(self):
        NoteFolder.FOLDER_LIST.clear()

        # Create the folder
        local_folder_r2l = LocalNoteFolder("remote_to_local")
        local_folder_r2l.create()
        remote_folder_r2l = RemoteNoteFolder(Path("/tmp/Notes/remote_to_local"), "remote_to_local")
        remote_folder_r2l.create()

        # Persist the folder
        NoteFolder.FOLDER_LIST.append(NoteFolder(local_folder_r2l, remote_folder_r2l, NoteFolder.SYNC_REMOTE_TO_LOCAL))
        success, data = NoteFolder.persist_folders()
        assert success is True

        # Delete the remote folder
        remote_folder_r2l.delete()

        # Sync the deletions
        discovered_remote = [RemoteNoteFolder(Path("/tmp/Notes/Test"), "Test")]
        success, data = NoteFolder.sync_remote_deletions(discovered_remote)
        assert success is True

        # Verify the deletions
        success, folders = NoteFolder.load_local_folders()
        deleted_folder = next((f for f in folders if f.name == "remote_to_local"), None)
        assert deleted_folder is None

        # Fail - SQL Error
        class MockSqlite3:
            def connect(self):
                raise MockSqlite3.OperationalError

            class OperationalError(BaseException):
                def __repr__(self):
                    return "Fail"

        with mock.patch('taskbridge.notes.model.notefolder.sqlite3', MockSqlite3):
            success, data = NoteFolder.sync_remote_deletions(discovered_remote)
            assert success is False

        # Fail - Deletion error

        # noinspection PyUnusedLocal
        def mock_delete(stuff):
            return False, "Fail"

        with mock.patch('taskbridge.notes.model.notefolder.LocalNoteFolder.delete', mock_delete):
            success, data = NoteFolder.sync_remote_deletions(discovered_remote)
            assert success is False

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and local filesystem.")
    def test_sync_folder_deletions(self):
        NoteFolder.FOLDER_LIST.clear()

        # Create the folders
        local_folder_bi = LocalNoteFolder("folder_bi")
        local_folder_l2r = LocalNoteFolder("local_to_remote")
        local_folder_r2l = LocalNoteFolder("remote_to_local")
        local_folder_bi.create()
        local_folder_l2r.create()
        local_folder_r2l.create()
        remote_folder_bi = RemoteNoteFolder(Path("/tmp/Notes/folder_bi"), "folder_bi")
        remote_folder_l2r = RemoteNoteFolder(Path("/tmp/Notes/local_to_remote"), "local_to_remote")
        remote_folder_r2l = RemoteNoteFolder(Path("/tmp/Notes/remote_to_local"), "remote_to_local")
        remote_folder_bi.create()
        remote_folder_l2r.create()
        remote_folder_r2l.create()

        # Persist the folders
        NoteFolder.FOLDER_LIST.append(NoteFolder(local_folder_bi, remote_folder_bi, NoteFolder.SYNC_BOTH))
        NoteFolder.FOLDER_LIST.append(NoteFolder(local_folder_l2r, remote_folder_l2r, NoteFolder.SYNC_LOCAL_TO_REMOTE))
        NoteFolder.FOLDER_LIST.append(NoteFolder(local_folder_r2l, remote_folder_r2l, NoteFolder.SYNC_REMOTE_TO_LOCAL))
        success, data = NoteFolder.persist_folders()
        assert success is True

        # Delete the bi-directional and l2r local folders
        local_folder_bi.delete()
        local_folder_l2r.delete()

        # Delete the r2l remote folder
        remote_folder_r2l.delete()

        # Sync the deletions
        discovered_local = [LocalNoteFolder("Test"), LocalNoteFolder("remote_to_local")]
        discovered_remote = [RemoteNoteFolder(Path("/tmp/Notes/Test"), "Test"),
                             RemoteNoteFolder(Path("/tmp/Notes/folder_bi"), "folder_bi"),
                             RemoteNoteFolder(Path("/tmp/Notes/local_to_remote"), "local_to_remote")]
        success, data = NoteFolder.sync_folder_deletions(discovered_local, discovered_remote)
        assert success is True

        # Verify the deletions
        dirs = [d for d in os.listdir("/tmp/Notes/") if os.path.isdir(d)]
        assert 'folder_bi' not in dirs
        assert 'local_to_remote' not in dirs
        success, folders = NoteFolder.load_local_folders()
        deleted_folder = next((f for f in folders if f.name == "remote_to_local"), None)
        assert deleted_folder is None

        # Fail - seed failed
        def mock_seed_folder_table():
            return False, 'Fail'

        with mock.patch('taskbridge.notes.model.notefolder.NoteFolder.seed_folder_table', mock_seed_folder_table):
            success, data = NoteFolder.sync_folder_deletions(discovered_local, discovered_remote)
            assert success is False

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem.")
    def test_seed_note_table(self):
        NoteFolder.seed_note_table()
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_table_exists = "SELECT name FROM sqlite_master WHERE type='table' AND name='tb_note';"
                    table_result = cursor.execute(sql_table_exists)

                    table_list = [t for t in table_result if t['name'] == "tb_note"]
                    assert len(table_list) == 1

                    sql_columns_exist = "PRAGMA table_info('tb_note');"
                    columns_result = cursor.execute(sql_columns_exist)

                    columns = ['id', 'folder', 'location', 'uuid', 'name', 'created', 'modified']
                    for col in columns_result:
                        assert col['name'] in columns
        except sqlite3.OperationalError as e:
            assert False, repr(e)

        # Fail - SQL Error
        class MockSqlite3:
            def connect(self):
                raise MockSqlite3.OperationalError

            class OperationalError(BaseException):
                def __repr__(self):
                    return "Fail"

        with mock.patch('taskbridge.notes.model.notefolder.sqlite3', MockSqlite3):
            success, data = NoteFolder.seed_note_table()
            assert success is False

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem.")
    def test_persist_notes(self):
        NoteFolder.FOLDER_LIST.clear()

        local_note = TestNoteFolder.__create_local_note()
        remote_note = TestNoteFolder.__create_remote_note()

        f_no_sync = NoteFolder(LocalNoteFolder("Test"), RemoteNoteFolder(Path("/tmp/Notes/Test"), "Test"),
                               NoteFolder.SYNC_NONE)
        f_l2r = NoteFolder(LocalNoteFolder("l2r"), RemoteNoteFolder(Path("/tmp/Notes/l2r"), "l2r"),
                           NoteFolder.SYNC_LOCAL_TO_REMOTE)
        f_l2r.local_notes.append(local_note)
        f_r2l = NoteFolder(LocalNoteFolder("r2l"), RemoteNoteFolder(Path("/tmp/Notes/r2l"), "r2l"),
                           NoteFolder.SYNC_REMOTE_TO_LOCAL)
        f_r2l.remote_notes.append(remote_note)

        NoteFolder.FOLDER_LIST.append(f_no_sync)
        NoteFolder.FOLDER_LIST.append(f_l2r)
        NoteFolder.FOLDER_LIST.append(f_r2l)

        success, data = NoteFolder.persist_notes()
        assert success is True

        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_get_notes = "SELECT * FROM tb_note;"
                    results = cursor.execute(sql_get_notes).fetchall()

                    persisted = [r for r in results if r['name'] in ('testnote1', 'testnote2')]
                    assert len(persisted) == 4
        except sqlite3.OperationalError as e:
            assert False, repr(e)

        # Clean Up
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_delete_notes = "DELETE FROM tb_note"
                    cursor.execute(sql_delete_notes)
                    connection.commit()
        except sqlite3.OperationalError as e:
            print(e)

        # Fail - SQL Error
        class MockSqlite3:
            def connect(self):
                raise MockSqlite3.OperationalError

            class OperationalError(BaseException):
                def __repr__(self):
                    return "Fail"

        with mock.patch('taskbridge.notes.model.notefolder.sqlite3', MockSqlite3):
            success, data = NoteFolder.persist_notes()
            assert success is False

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and local filesystem.")
    def test_delete_local_notes(self):
        NoteFolder.FOLDER_LIST.clear()
        TestNoteFolder.__reset_test_folder(create_notes=False)
        test_folder = TestNoteFolder.__get_test_folder()

        # Create the note
        note = TestNoteFolder.__create_local_note()
        note.create_local("Test")
        pathlib.Path("/tmp/Test").mkdir(parents=True, exist_ok=True)
        note.upsert_remote(Path("/tmp/Test"))
        test_folder.remote_notes.append(note)
        note_not_found = Note(name="NotFound", created_date=datetime.datetime.now(), modified_date=datetime.datetime.now())
        test_folder.remote_notes.append(note_not_found)

        # Persist the note
        NoteFolder.persist_notes()

        # Delete the remote note
        Path.unlink(Path("/tmp/Test/testnote2.md"))
        test_folder.remote_notes.remove(note)
        test_folder.remote_notes.remove(note_not_found)

        # Sync the deletion
        result = {
            'local_not_found': [],
            'local_deleted': []
        }
        success, data = NoteFolder.delete_local_notes(test_folder, result)
        assert success is True
        assert 'testnote2' in result['local_deleted']
        assert 'NotFound' in result['local_not_found']

        # Fail - SQL Error
        class MockSqlite3:
            def connect(self):
                raise MockSqlite3.OperationalError

            class OperationalError(BaseException):
                def __repr__(self):
                    return "Fail"

        with mock.patch('taskbridge.notes.model.notefolder.sqlite3', MockSqlite3):
            success, data = NoteFolder.delete_local_notes(test_folder, result)
            assert success is False

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and local filesystem.")
    def test_delete_remote_notes(self):
        NoteFolder.FOLDER_LIST.clear()
        TestNoteFolder.__reset_test_folder(create_notes=False)
        test_folder = TestNoteFolder.__get_test_folder()

        # Create the note
        note = TestNoteFolder.__create_local_note()
        note.create_local("Test")
        pathlib.Path("/tmp/Test/Test").mkdir(parents=True, exist_ok=True)
        note.upsert_remote(Path("/tmp/Test/Test"))
        test_folder.local_notes.append(note)
        test_folder.remote_notes.append(note)
        note_not_found = Note(name="NotFound", created_date=datetime.datetime.now(), modified_date=datetime.datetime.now())
        test_folder.local_notes.append(note_not_found)

        # Persist the note
        NoteFolder.persist_notes()

        # Delete the local note
        delete_note_script = notescript.delete_note_script
        helpers.run_applescript(delete_note_script, "Test", "testnote2")
        test_folder.local_notes.remove(note)
        test_folder.local_notes.remove(note_not_found)

        # Sync the deletion
        result = {
            'remote_not_found': [],
            'remote_deleted': []
        }
        success, data = NoteFolder.delete_remote_notes(test_folder, Path("/tmp/Test"), result)
        assert success is True
        assert 'testnote2' in result['remote_deleted']
        assert 'NotFound' in result['remote_not_found']

        # Fail - SQL Error
        class MockSqlite3:
            def connect(self):
                raise MockSqlite3.OperationalError

            class OperationalError(BaseException):
                def __repr__(self):
                    return "Fail"

        with mock.patch('taskbridge.notes.model.notefolder.sqlite3', MockSqlite3):
            success, data = NoteFolder.delete_remote_notes(test_folder, Path("/tmp/Test"), result)
            assert success is False

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and local filesystem.")
    def test_sync_note_deletions(self):
        NoteFolder.FOLDER_LIST.clear()
        TestNoteFolder.__reset_test_folder(create_notes=False)
        test_folder = TestNoteFolder.__get_test_folder()

        # Create a folder which shouldn't be synced
        lf = LocalNoteFolder('BOGUS')
        rf = RemoteNoteFolder(TestNoteFolder.TMP_FOLDER / 'BOGUS', 'BOGUS')
        NoteFolder(lf, rf, NoteFolder.SYNC_NONE)

        # Create the local note
        note_local = TestNoteFolder.__create_local_note()
        note_local.create_local("Test")
        pathlib.Path("/tmp/Test/Test").mkdir(parents=True, exist_ok=True)
        note_local.upsert_remote(Path("/tmp/Test/Test"))
        test_folder.local_notes.append(note_local)
        test_folder.remote_notes.append(note_local)

        # Create the remote note
        note_remote = TestNoteFolder.__create_remote_note()
        note_remote.create_local("Test")
        note_remote.upsert_remote((Path("/tmp/Test/Test")))
        test_folder.local_notes.append(note_remote)
        test_folder.remote_notes.append(note_remote)

        # Persist the notes
        NoteFolder.persist_notes()

        # Delete the local note
        delete_note_script = notescript.delete_note_script
        helpers.run_applescript(delete_note_script, "Test", "testnote2")
        test_folder.local_notes.remove(note_local)

        # Delete the remote note
        Path.unlink(Path("/tmp/Test/Test/testnote1.md"))
        test_folder.remote_notes.remove(note_remote)

        # Sync the deletions
        success, result = NoteFolder.sync_note_deletions(Path("/tmp/Test"))
        assert success is True
        assert isinstance(result, dict)
        assert 'testnote1' in result['local_deleted']
        assert 'testnote2' in result['remote_deleted']
        assert len(result['local_not_found']) == 0
        assert len(result['remote_not_found']) == 0

        # Fail seeding
        def mock_seed_note_table():
            return False, 'Fail'

        with mock.patch('taskbridge.notes.model.notefolder.NoteFolder.seed_note_table', mock_seed_note_table):
            success, data = NoteFolder.sync_note_deletions(Path("/tmp/Test"))
            assert success is False

        # Fail to load local notes

        # noinspection PyUnusedLocal
        def mock_load_local_notes(inst):
            return False, 'Fail'
        with mock.patch('taskbridge.notes.model.notefolder.NoteFolder.load_local_notes', mock_load_local_notes):
            success, data = NoteFolder.sync_note_deletions(Path("/tmp/Test"))
            assert success is False

        # Fail to load remote notes

        # noinspection PyUnusedLocal
        def mock_load_remote_notes(inst):
            return False, 'Fail'

        with mock.patch('taskbridge.notes.model.notefolder.NoteFolder.load_remote_notes', mock_load_remote_notes):
            success, data = NoteFolder.sync_note_deletions(Path("/tmp/Test"))
            assert success is False

    def test_reset_list(self):
        NoteFolder.FOLDER_LIST.append(NoteFolder(None, None, NoteFolder.SYNC_NONE))
        NoteFolder.reset_list()
        assert len(NoteFolder.FOLDER_LIST) == 0
