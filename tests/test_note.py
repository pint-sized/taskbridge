import datetime
import os
import pathlib
import shutil
from pathlib import Path
from unittest import mock

import pytest
from decouple import config

from taskbridge import helpers
from taskbridge.notes.model import notescript
from taskbridge.notes.model.note import Note
from taskbridge.notes.model.notefolder import LocalNoteFolder, NoteFolder

TEST_ENV = config('TEST_ENV', default='remote')


# noinspection SpellCheckingInspection
class TestNote:
    TMP_FOLDER = Path("/tmp")
    RES_DIR = Path()
    MOCK_TESTNOTE1_STAGED = ''
    MOCK_TESTNOTE1_MD = ''
    MOCK_TESTNOTE2_HTML = ''
    MOCK_TESTNOTE2_MD = ''
    MOCK_SIMPLENOTE_STAGED = ''

    @classmethod
    def setup_class(cls):
        TestNote.RES_DIR = pathlib.Path(__file__).parent.resolve() / 'resources'
        with open(TestNote.RES_DIR / 'mock_testnote1_staged.staged') as fp:
            TestNote.MOCK_TESTNOTE1_STAGED = fp.read()
        with open(TestNote.RES_DIR / 'mock_testnote1_md.md') as fp:
            TestNote.MOCK_TESTNOTE1_MD = fp.read()
        with open(TestNote.RES_DIR / 'mock_testnote2_html.html') as fp:
            TestNote.MOCK_TESTNOTE2_HTML = fp.read()
        with open(TestNote.RES_DIR / 'mock_testnote2_md.md') as fp:
            TestNote.MOCK_TESTNOTE2_MD = fp.read()
        with open(TestNote.RES_DIR / 'mock_simplenote_staged.staged') as fp:
            TestNote.MOCK_SIMPLENOTE_STAGED = fp.read()

    @staticmethod
    def _create_note_from_local() -> Note:
        staged_location = TestNote.TMP_FOLDER / 'testnote1.staged'
        with open(staged_location, 'w') as fp:
            fp.write(TestNote.MOCK_TESTNOTE1_STAGED)

        return Note.create_from_local(TestNote.MOCK_TESTNOTE1_STAGED, TestNote.TMP_FOLDER)

    @staticmethod
    def _create_note_from_remote() -> Note:
        remote_content = """testnote2

This is a remote note. 

![ladybird.jpg](.attachments.295/ladybird.jpg)

  
That was a ladybird"""
        remote_file_name = "testnote2.md"
        test_location = TestNote.RES_DIR / '.attachments.295'
        remote_location = Path("/tmp/Sync")
        pathlib.Path(remote_location / ".attachments.295").mkdir(parents=True, exist_ok=True)
        with open(remote_location / remote_file_name, 'w') as fp:
            fp.write(remote_content)
        shutil.copy(test_location / "ladybird.jpg", remote_location / ".attachments.295/")

        return Note.create_from_remote(remote_content, remote_location, remote_file_name)

    @staticmethod
    def _clean_artefacts():
        tmp_local = TestNote.TMP_FOLDER / 'testnote1.staged'
        if os.path.isfile(tmp_local):
            os.remove(tmp_local)

        tmp_remote = TestNote.TMP_FOLDER / "Sync/"
        if os.path.isdir(tmp_remote):
            shutil.rmtree(tmp_remote)
        if os.path.isdir("/tmp/.attachments"):
            shutil.rmtree("/tmp/.attachments")

    def test_create_simple_note(self):
        staged_location = TestNote.TMP_FOLDER / 'simplenote.staged'
        with open(staged_location, 'w') as fp:
            fp.write(TestNote.MOCK_SIMPLENOTE_STAGED)

        note = Note.create_from_local(TestNote.MOCK_SIMPLENOTE_STAGED, TestNote.TMP_FOLDER)
        assert note.name == "simplenote"

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem.")
    def test_create_from_local(self):
        new_note = TestNote._create_note_from_local()
        assert new_note.created_date == datetime.datetime(2024, 3, 29, 15, 59, 24)
        assert new_note.modified_date == datetime.datetime(2024, 4, 5, 8, 14, 1)
        assert new_note.name == 'testnote1'
        assert new_note.uuid is not None
        with open(TestNote.RES_DIR / 'mock_testnote1_html.html') as fp:
            body_html = fp.read()
        assert new_note.body_html == body_html
        assert len(new_note.attachments) == 1
        attachment = new_note.attachments[0]
        with open(TestNote.RES_DIR / 'attachment_1_b64.b64') as fp:
            b64_data = fp.read()
        assert attachment.b64_data == b64_data
        assert attachment.file_name is not None
        assert attachment.file_type == 0
        assert attachment.uuid is not None
        assert attachment.staged_location is not None
        body_markdown = TestNote.MOCK_TESTNOTE1_MD.format(attachment.uuid)
        assert new_note.body_markdown == body_markdown

        # Clean up
        TestNote._clean_artefacts()

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem.")
    def test_create_from_remote(self):
        new_note = TestNote._create_note_from_remote()
        assert new_note.created_date.date() == datetime.datetime.now().date()
        assert new_note.modified_date.date() == datetime.datetime.now().date()
        assert new_note.name == 'testnote2'
        assert new_note.uuid is None
        body_html = TestNote.MOCK_TESTNOTE2_HTML
        assert new_note.body_html == body_html
        assert len(new_note.attachments) == 1
        attachment = new_note.attachments[0]
        with open(TestNote.RES_DIR / 'attachment_2_b64.b64') as fp:
            b64_data = fp.read()
        assert attachment.b64_data == b64_data
        assert attachment.file_name == ".attachments.295/ladybird.jpg"
        assert attachment.file_type == 0
        assert attachment.uuid is not None
        assert attachment.staged_location is None
        assert new_note.body_markdown == TestNote.MOCK_TESTNOTE2_MD

        # Clean up
        TestNote._clean_artefacts()

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem.")
    def test_staged_to_markdown(self):
        new_note = TestNote._create_note_from_local()
        staged_lines = TestNote.MOCK_TESTNOTE1_STAGED.splitlines()
        attachment_end = staged_lines.index("~~END_ATTACHMENTS~~")
        parsed_attachments = new_note.attachments
        uuid = parsed_attachments[0].uuid
        md = Note.staged_to_markdown(staged_lines, parsed_attachments, attachment_end)

        # Success
        assert md == TestNote.MOCK_TESTNOTE1_MD.format(uuid)

        # Fail
        parsed_attachments.clear()
        md = Note.staged_to_markdown(staged_lines, parsed_attachments, attachment_end)
        assert 'ladybird.jpg' not in md

        # Clean up
        TestNote._clean_artefacts()

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem.")
    def test_markdown_to_html(self):
        new_note = TestNote._create_note_from_remote()
        remote_lines = TestNote.MOCK_TESTNOTE2_MD.splitlines()
        attachments = new_note.attachments
        html = Note.markdown_to_html(remote_lines, attachments)

        assert html == TestNote.MOCK_TESTNOTE2_HTML

        # Clean up
        TestNote._clean_artefacts()

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem.")
    def test_create_local(self):
        new_note = TestNote._create_note_from_local()

        # Success
        success, data = new_note.create_local('Sync')
        assert success is True

        # Confirm note has been created
        nf = NoteFolder(LocalNoteFolder("Sync"), None, NoteFolder.SYNC_BOTH)
        nf.load_local_notes()
        created_note = next((n for n in nf.local_notes if n.name == "testnote1"), None)
        assert created_note is not None

        # Fail - note folder doesn't exist
        success, data = new_note.create_local('Bogus')
        assert success is False

        # Fail - Fail to export note to HTML
        data_location = helpers.DATA_LOCATION
        helpers.DATA_LOCATION = Path('/bogus')
        success, data = new_note.create_local('Sync')
        helpers.DATA_LOCATION = data_location
        assert success is False

        # Clean up
        TestNote._clean_artefacts()
        delete_note_script = notescript.delete_note_script
        helpers.run_applescript(delete_note_script, "Sync", "testnote1")

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem.")
    def test_update_local(self):
        new_note = TestNote._create_note_from_local()
        success, data = new_note.create_local('Sync')
        assert success is True

        # Success
        success, data = new_note.update_local('Sync')
        assert success is True

        # Fail - note folder doesn't exist
        success, data = new_note.update_local('Bogus')
        assert success is False

        # Fail - Fail to export note to HTML
        data_location = helpers.DATA_LOCATION
        helpers.DATA_LOCATION = Path('/bogus')
        success, data = new_note.create_local('Sync')
        helpers.DATA_LOCATION = data_location
        assert success is False

        # Fail - OSError

        # noinspection PyUnusedLocal
        def mock_open(name, mode=None, buffering=None):
            raise OSError

        with mock.patch('builtins.open', mock_open):
            success, data = new_note.update_local('Sync')
            assert success is False

        # Clean up
        TestNote._clean_artefacts()
        delete_note_script = notescript.delete_note_script
        helpers.run_applescript(delete_note_script, "Sync", "testnote1")

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem.")
    def test_upsert_remote(self):
        new_note = TestNote._create_note_from_remote()
        new_note.attachments[0].staged_location = (
            Path(TestNote.TMP_FOLDER / "Sync" / ".attachments.295" / "ladybird.jpg"))

        # Success
        success, data = new_note.upsert_remote(TestNote.TMP_FOLDER / "Sync")
        assert success is True

        # Fail - Remote folder doesn't exist
        success, data = new_note.upsert_remote(Path("/bogus"))
        assert success is False

        # Fail - Remote attachment doesn't exist
        new_note = TestNote._create_note_from_remote()
        if os.path.isdir("/tmp/Sync/.attachments"):
            shutil.rmtree("/tmp/Sync/.attachments")
        if os.path.isdir("/tmp/Sync/.attachments.295"):
            shutil.rmtree("/tmp/Sync/.attachments.295")
        success, data = new_note.upsert_remote(TestNote.TMP_FOLDER / "Sync")
        assert success is False

        # Clean up
        TestNote._clean_artefacts()

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem.")
    def test___str__(self):
        new_note = TestNote._create_note_from_local()
        name = new_note.__str__()
        assert name == new_note.name

        # Clean up
        TestNote._clean_artefacts()
