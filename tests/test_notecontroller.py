from pathlib import Path
from unittest import mock

from taskbridge.notes.controller import NoteController
from taskbridge.notes.model.notefolder import NoteFolder, LocalNoteFolder, RemoteNoteFolder


class TestNoteController:
    FOLDER_BASE = 'taskbridge.notes.model.notefolder'

    def test_get_local_folders(self):
        succeed = True

        def mock_load_local_folders():
            return succeed, ""

        with mock.patch("{}.NoteFolder.load_local_folders".format(TestNoteController.FOLDER_BASE), mock_load_local_folders):
            # Success
            succeed = True
            success, data = NoteController.get_local_folders()
            assert success is True

            # Fail
            succeed = False
            success, data = NoteController.get_local_folders()
            assert success is False

    def test_get_remote_folders(self):
        succeed = True

        # noinspection PyUnusedLocal
        def mock_load_remote_folders(loc):
            return succeed, ""

        with mock.patch("{}.NoteFolder.load_remote_folders".format(TestNoteController.FOLDER_BASE), mock_load_remote_folders):
            # Success
            succeed = True
            success, data = NoteController.get_remote_folders()
            assert success is True

            # Fail
            succeed = False
            success, data = NoteController.get_remote_folders()
            assert success is False

    def test_sync_folder_deletions(self):
        succeed = True

        # noinspection PyUnusedLocal
        def mock_sync_folder_deletions(local_folders, remote_folders):
            return succeed, ""

        with mock.patch("{}.NoteFolder.sync_folder_deletions".format(TestNoteController.FOLDER_BASE), mock_sync_folder_deletions):
            # Success
            succeed = True
            success, data = NoteController.sync_folder_deletions()
            assert success is True

            # Fail
            succeed = False
            success, data = NoteController.sync_folder_deletions()
            assert success is False

    def test_associate_folders(self):
        succeed = True

        # noinspection PyUnusedLocal
        def mock_create_linked_folders(local, remote, loc, assoc):
            return succeed, ""

        with mock.patch("{}.NoteFolder.create_linked_folders".format(TestNoteController.FOLDER_BASE), mock_create_linked_folders):
            # Success
            succeed = True
            success, data = NoteController.associate_folders()
            assert success is True

            # Fail
            succeed = False
            success, data = NoteController.associate_folders()
            assert success is False

    def test_sync_deleted_notes(self):
        succeed = True

        # noinspection PyUnusedLocal
        def mock_sync_note_deletions(remote_folder):
            return succeed, ""

        with mock.patch("{}.NoteFolder.sync_note_deletions".format(TestNoteController.FOLDER_BASE), mock_sync_note_deletions):
            # Success
            succeed = True
            success, data = NoteController.sync_deleted_notes()
            assert success is True

            # Fail
            succeed = False
            success, data = NoteController.sync_deleted_notes()
            assert success is False

    def test_sync_notes(self):
        succeed = True

        # noinspection PyUnusedLocal
        def mock_sync_notes(inst):
            if not succeed:
                return False, ""

            return True, {
                'remote_added': [],
                'remote_updated': [],
                'local_added': [],
                'local_updated': []
            }

        with mock.patch('{}.NoteFolder.sync_notes'.format(TestNoteController.FOLDER_BASE), mock_sync_notes):
            NoteFolder.FOLDER_LIST.append(NoteFolder(
                LocalNoteFolder("Test"),
                RemoteNoteFolder(Path("/tmp/test"), "Test"),
                NoteFolder.SYNC_NONE
            ))

            # Success
            succeed = True
            success, data = NoteController.sync_notes()
            assert success is True

            # Fail
            succeed = False
            success, data = NoteController.sync_notes()
            assert success is False
