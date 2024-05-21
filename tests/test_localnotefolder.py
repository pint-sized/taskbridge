from unittest import mock

import pytest
from decouple import config

from taskbridge.notes.model.notefolder import LocalNoteFolder

TEST_ENV = config('TEST_ENV', default='remote')


class TestLocalNoteFolder:
    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud")
    def test_create(self):
        # Success
        test_folder = LocalNoteFolder("Test")
        success, data = test_folder.create()
        assert success is True

        # Cleanup
        test_folder.delete()

        # Fail

        # noinspection PyUnusedLocal
        def mock_run_applescript(script, *args):
            return 1, '0', 'Fail'

        with mock.patch('taskbridge.helpers.run_applescript', mock_run_applescript):
            test_folder = LocalNoteFolder("Test")
            success, data = test_folder.create()
            assert success is False

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud")
    def test_delete(self):
        # Success - Folder gets deleted
        test_folder = LocalNoteFolder("Test")
        success, data = test_folder.create()
        assert success is True
        success, data = test_folder.delete()
        assert success is True

        # Success - Folder already deleted
        test_folder = LocalNoteFolder("Test")
        success, data = test_folder.delete()
        assert success is True

    def test___str(self):
        test_folder = LocalNoteFolder("Test")
        name = test_folder.__str__()
        assert name == "Local Folder: Test"
