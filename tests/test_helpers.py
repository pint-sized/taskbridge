import datetime
import logging
import pathlib
import sys
from pathlib import Path

import pytest
from decouple import config

from taskbridge import helpers
from taskbridge.helpers import DateUtil

TEST_ENV = config('TEST_ENV', default='remote')


class TestHelpers:
    RES_DIR = Path()

    @classmethod
    def setup_class(cls):
        TestHelpers.RES_DIR = pathlib.Path(__file__).parent.resolve() / 'resources'

    def test_confirm(self, monkeypatch):
        helpers.DRY_RUN = True
        monkeypatch.setattr('builtins.input', lambda _: "y")
        result = helpers.confirm("Test Prompt")
        assert result is True

        monkeypatch.setattr('builtins.input', lambda _: "n")
        result = helpers.confirm("Test Prompt")
        assert result is False

        helpers.DRY_RUN = False
        result = helpers.confirm("Test Prompt")
        assert result is True

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system")
    def test_run_applescript(self):
        test_script = 'tell application "Notes" to if it is running then quit'
        return_code, stdout, stderr = helpers.run_applescript(test_script)
        assert return_code == 0

    def test_get_uuid(self):
        uuid = helpers.get_uuid()
        assert len(uuid) == 36

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem")
    def test_html_to_markdown(self):
        with open(TestHelpers.RES_DIR / 'mock_testnote2_html.html') as fp:
            html = fp.read()
        with open(TestHelpers.RES_DIR / 'testnote2_direct.md') as fp:
            markdown = fp.read()
        result = helpers.html_to_markdown(html)
        assert result == markdown

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem")
    def test_markdown_to_html(self):
        with open(TestHelpers.RES_DIR / 'mock_testnote2_md.md') as fp:
            markdown = fp.read()
        with open(TestHelpers.RES_DIR / 'testnote2_direct.html') as fp:
            html = fp.read()
        result = helpers.markdown_to_html(markdown)
        assert result == html

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem")
    def test_db_folder(self):
        data_location = Path.home() / "Library" / "Application Support" / "TaskBridge"
        result = helpers.db_folder()
        assert isinstance(result, Path)
        assert result == data_location / "TaskBridge.db"

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem")
    def test_temp_folder(self):
        data_location = Path.home() / "Library" / "Application Support" / "TaskBridge"
        result = helpers.temp_folder()
        assert isinstance(result, Path)
        assert result == data_location / "tmp/"

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem")
    def test_settings_folder(self):
        data_location = Path.home() / "Library" / "Application Support" / "TaskBridge"
        result = helpers.settings_folder()
        assert isinstance(result, Path)
        assert result == data_location
        assert data_location.is_dir()

    def test_convert(self):
        apple_datetime = "Friday, 24 May 2024 at 09:54:59"
        apple_datetime_alt = "Friday 24 May 2024 at 09:54:59"
        caldav_datetime = "20240524T095459"
        caldav_date = "20240524"
        sqlite_datetime = "2024-05-24 09:54:59"

        result = DateUtil.convert(DateUtil.APPLE_DATETIME, apple_datetime)
        assert isinstance(result, datetime.datetime)
        assert result == datetime.datetime(2024, 5, 24, 9, 54, 59)

        result = DateUtil.convert(DateUtil.APPLE_DATETIME, apple_datetime_alt)
        assert isinstance(result, datetime.datetime)
        assert result == datetime.datetime(2024, 5, 24, 9, 54, 59)

        result = DateUtil.convert(DateUtil.CALDAV_DATETIME, caldav_datetime)
        assert isinstance(result, datetime.datetime)
        assert result == datetime.datetime(2024, 5, 24, 9, 54, 59)

        result = DateUtil.convert(DateUtil.CALDAV_DATE, caldav_date)
        assert isinstance(result, datetime.datetime)
        assert result == datetime.datetime(2024, 5, 24, 0, 0)

        result = DateUtil.convert(DateUtil.SQLITE_DATETIME, sqlite_datetime)
        assert isinstance(result, datetime.datetime)
        assert result == datetime.datetime(2024, 5, 24, 9, 54, 59)

        result = DateUtil.convert(DateUtil.APPLE_DATETIME, "invalid")
        assert result is False

        existing_date = datetime.datetime(2024, 5, 24, 9, 54, 59)
        result = DateUtil.convert('', existing_date)
        assert result == existing_date

        result = DateUtil.convert('', existing_date, DateUtil.APPLE_DATETIME)
        assert result == apple_datetime

        result = DateUtil.convert('', existing_date, DateUtil.APPLE_DATETIME_ALT)
        assert result == apple_datetime_alt

        result = DateUtil.convert('', existing_date, DateUtil.CALDAV_DATETIME)
        assert result == caldav_datetime

        result = DateUtil.convert('', existing_date, DateUtil.CALDAV_DATE)
        assert result == caldav_date

        result = DateUtil.convert('', existing_date, DateUtil.SQLITE_DATETIME)
        assert result == sqlite_datetime

        class MockDateTime:
            def __init__(self, *args):
                pass

            def strftime(self, fmt):
                raise ValueError

        bogus_date = MockDateTime('fail')
        # noinspection PyTypeChecker
        result = DateUtil.convert('', bogus_date, '%m-%d-%Y %T%Q:%M%p')
        assert result is False

    def test_emit(self):
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s %(levelname)s: %(message)s',
        )

        def log_func(msg):
            assert msg == "test"

        logger = logging.getLogger()
        func_handler = helpers.FunctionHandler(lambda msg: log_func(msg))
        logger.addHandler(func_handler)

        logger.critical("test")
        logger.handlers.clear()
