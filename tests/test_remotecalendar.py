import pytest
from decouple import config

from taskbridge import helpers
from taskbridge.reminders.model.remindercontainer import RemoteCalendar

TEST_ENV = config('TEST_ENV', default='remote')


class TestRemoteCalendar:

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires CalDAV credentials")
    def test_create(self):
        helpers.CALDAV_PRINCIPAL = None
        cal = RemoteCalendar(calendar_name="Test_Cal")
        success, data = cal.create()
        assert success is False

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires CalDAV credentials")
    def test_delete(self):
        helpers.CALDAV_PRINCIPAL = None
        cal = RemoteCalendar(calendar_name="Test_Cal")
        success, data = cal.delete()
        assert success is False

    def test___str__(self):
        cal = RemoteCalendar(calendar_name="Test_Cal")
        name = cal.__str__()
        assert name == "Test_Cal"

    def test___repr__(self):
        cal = RemoteCalendar(calendar_name="Test_Cal")
        name = cal.__repr__()
        assert name == "Test_Cal"
