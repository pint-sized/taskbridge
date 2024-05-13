from pathlib import Path

import pytest
from decouple import config


from taskbridge.notes.model.notefolder import NoteFolder, LocalNoteFolder, RemoteNoteFolder

TEST_ENV = config('TEST_ENV', default='remote')


class TestNoteFolder:
    TMP_FOLDER = Path("/tmp")

    @staticmethod
    def __get_sync_folder() -> NoteFolder:
        lf = LocalNoteFolder('Sync')
        rf = RemoteNoteFolder(TestNoteFolder.TMP_FOLDER / 'Sync', 'Sync')
        nf = NoteFolder(lf, rf, True)
        return nf

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud")
    def test_load_local_notes(self):
        # Success
        sync_folder = TestNoteFolder.__get_sync_folder()
        success, data = sync_folder.load_local_notes()
        assert success is True
        assert isinstance(data, int)
        assert data > 0
