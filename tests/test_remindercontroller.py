from unittest import mock

import caldav.lib.error

from taskbridge.reminders.controller import ReminderController
from taskbridge.reminders.model.remindercontainer import LocalList, RemoteCalendar


class TestReminderController:
    CONTAINER_BASE = 'taskbridge.reminders.model.remindercontainer'

    def test_fetch_local_reminders(self):
        succeed = True

        def mock_load_local_lists():
            return succeed, ""

        with mock.patch('{}.ReminderContainer.load_local_lists'.format(TestReminderController.CONTAINER_BASE),
                        mock_load_local_lists):
            # Success
            succeed = True
            success, data = ReminderController.fetch_local_reminders()
            assert success is True

            # Fail
            succeed = False
            success, data = ReminderController.fetch_local_reminders()
            assert success is False

    def test_connect_caldav(self):
        succeed = True

        class MockDAVClient:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

            # noinspection PyMethodMayBeStatic
            def principal(self):
                if succeed:
                    return True
                raise caldav.lib.error.AuthorizationError("Failed to connect")

        with mock.patch('caldav.DAVClient', MockDAVClient):
            # Success
            succeed = True
            success, data = ReminderController.connect_caldav()
            assert success is True

            # Fail
            succeed = False
            success, data = ReminderController.connect_caldav()
            assert success is False

    def test_fetch_remote_reminders(self):
        succeed = True

        def mock_load_caldav_calendars():
            return succeed, ""

        with mock.patch('{}.ReminderContainer.load_caldav_calendars'.format(TestReminderController.CONTAINER_BASE),
                        mock_load_caldav_calendars):
            # Success
            succeed = True
            success, data = ReminderController.fetch_remote_reminders()
            assert success is True

            # Fail
            succeed = False
            success, data = ReminderController.fetch_remote_reminders()
            assert success is False

    def test_sync_deleted_containers(self):
        succeed = True

        # noinspection PyUnusedLocal
        def mock_sync_container_deletions(local_lists, remote_calendars, to_sync):
            if succeed:
                return True, {
                    'updated_local_list': [],
                    'updated_remote_list': []
                }
            return False, ""

        with mock.patch('{}.ReminderContainer.sync_container_deletions'.format(TestReminderController.CONTAINER_BASE),
                        mock_sync_container_deletions):
            # Success
            succeed = True
            success, data = ReminderController.sync_deleted_containers()
            assert success is True

            # Fail
            succeed = False
            success, data = ReminderController.sync_deleted_containers()
            assert success is False

    def test_associate_containers(self):
        succeed = True

        # noinspection PyUnusedLocal
        def mock_create_linked_containers(local_lists, remote_calendars, to_sync):
            if succeed:
                return True, ""
            return False, ""

        with mock.patch('{}.ReminderContainer.create_linked_containers'.format(TestReminderController.CONTAINER_BASE),
                        mock_create_linked_containers):
            # Success
            succeed = True
            success, data = ReminderController.associate_containers()
            assert success is True

            # Fail
            succeed = False
            success, data = ReminderController.associate_containers()
            assert success is False

    def test_sync_deleted_reminders(self):
        succeed = True

        def mock_sync_reminder_deletions():
            if succeed:
                return True, {
                    'deleted_local_reminders': [],
                    'deleted_remote_reminders': []
                }
            return False, ""

        with mock.patch('{}.ReminderContainer.sync_reminder_deletions'.format(TestReminderController.CONTAINER_BASE),
                        mock_sync_reminder_deletions):
            # Success
            succeed = True
            success, data = ReminderController.sync_deleted_reminders()
            assert success is True

            # Fail
            succeed = False
            success, data = ReminderController.sync_deleted_reminders()
            assert success is False

    def test_sync_reminders(self):
        succeed = True

        class MockReminderContainer:
            CONTAINER_LIST = []

            def __init__(self, local_list, remote_calendar, sync):
                self.local_list = local_list
                self.remote_calendar = remote_calendar
                self.sync = sync

            # noinspection PyUnusedLocal, PyMethodMayBeStatic
            def sync_reminders(self, fail: str = None):
                if succeed:
                    return True, {
                        'remote_added': [],
                        'remote_updated': [],
                        'local_added': [],
                        'local_updated': []
                    }
                return False, ""

        MockReminderContainer.CONTAINER_LIST = [
            MockReminderContainer(LocalList('test2'), RemoteCalendar(calendar_name='test2'), True),
            MockReminderContainer(LocalList('test1'), RemoteCalendar(calendar_name='test1'), True)
        ]

        with mock.patch('{}.ReminderContainer.CONTAINER_LIST'.format(TestReminderController.CONTAINER_BASE),
                        MockReminderContainer.CONTAINER_LIST):
            # Success
            succeed = True
            success, data = ReminderController.sync_reminders()
            assert success is True

            # Fail
            succeed = False
            success, data = ReminderController.sync_reminders()
            assert success is False

            # Corner case - no reminders in list
            MockReminderContainer.CONTAINER_LIST.clear()
            success, data = ReminderController.sync_reminders()
            assert success is True

    def test_sync_reminders_to_db(self):
        succeed = True

        def mock_persist_reminders():
            if succeed:
                return True, ""
            return False, ""

        with mock.patch('{}.ReminderContainer.persist_reminders'.format(TestReminderController.CONTAINER_BASE),
                        mock_persist_reminders):
            # Success
            succeed = True
            success, data = ReminderController.sync_reminders_to_db()
            assert success is True

            # Fail
            succeed = False
            success, data = ReminderController.sync_reminders_to_db()
            assert success is False

    def test_count_completed(self):
        succeed = True

        def mock_count_local_completed():
            if succeed:
                return True, 0
            return False, ""

        with mock.patch('{}.ReminderContainer.count_local_completed'.format(TestReminderController.CONTAINER_BASE),
                        mock_count_local_completed):
            # Success
            succeed = True
            success, data = ReminderController.count_completed()
            assert success is True

            # Fail
            succeed = False
            success, data = ReminderController.count_completed()
            assert success is False

    def test_delete_completed(self):
        succeed = True

        def mock_delete_local_completed():
            if succeed:
                return True, ""
            return False, ""

        with mock.patch('{}.ReminderContainer.delete_local_completed'.format(TestReminderController.CONTAINER_BASE),
                        mock_delete_local_completed):
            # Success
            succeed = True
            success, data = ReminderController.delete_completed()
            assert success is True

            # Fail
            succeed = False
            success, data = ReminderController.delete_completed()
            assert success is False
