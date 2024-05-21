from pathlib import Path
from unittest import mock

import pytest
from decouple import config

from taskbridge.notes.model.notefolder import RemoteNoteFolder

TEST_ENV = config('TEST_ENV', default='remote')


class TestRemoteNoteFolder:
    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem")
    def test_create(self):
        test_folder = RemoteNoteFolder(Path("/tmp/Test"), "Test")
        success, data = test_folder.create()
        assert success is True

        # Cleanup
        test_folder.delete()

        # Fail

        # noinspection PyUnusedLocal
        def mock_mkdir(inst, mode=0o777, parents=False, exist_ok=False):
            raise OSError

        with mock.patch("pathlib.Path.mkdir", mock_mkdir):
            success, data = test_folder.create()
            assert success is False

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem")
    def test_delete(self):
        test_folder = RemoteNoteFolder(Path("/tmp/Test"), "Test")
        success, data = test_folder.create()
        assert success is True

        # Success
        success, data = test_folder.delete()
        assert success is True

        # Success - already deleted
        success, data = test_folder.delete()
        assert success is True

        # Fail

        # noinspection PyUnusedLocal
        def mock_rmtree(path, ignore_errors=False, onerror=None, *, onexc=None, dir_fd=None):
            raise OSError

        with mock.patch('shutil.rmtree', mock_rmtree):
            test_folder = RemoteNoteFolder(Path("/tmp/Test"), "Test")
            test_folder.create()
            success, data = test_folder.delete()
            assert success is False

    def test___str(self):
        test_folder = RemoteNoteFolder(Path("/tmp/Test"), "Test")
        name = test_folder.__str__()
        assert name == "Remote Folder: Test"
