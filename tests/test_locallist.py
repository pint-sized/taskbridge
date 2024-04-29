import pytest
from decouple import config

from taskbridge.reminders.model.remindercontainer import LocalList

TEST_ENV = config('TEST_ENV', default='remote')


class TestRemoteCalendar:
    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud")
    def test_create(self):
        lst = LocalList("Test_List")
        success, data = lst.create(True)
        assert success is False

    def test___str__(self):
        lst = LocalList("Test_List")
        name = lst.__str__()
        assert name == "Test_List"

    def test___repr__(self):
        lst = LocalList("Test_List")
        name = lst.__repr__()
        assert name == "Test_List"
