import datetime
import os
import json
from pathlib import Path

import pytest
import caldav
import keyring
from caldav.lib.error import AuthorizationError
from decouple import config

import taskbridge.helpers as helpers
from taskbridge.reminders.model import reminderscript
from taskbridge.reminders.model.reminder import Reminder
from taskbridge.reminders.model.remindercontainer import ReminderContainer, LocalList, RemoteCalendar
from taskbridge.reminders.controller import ReminderController
from taskbridge.helpers import DateUtil

TEST_ENV = config('TEST_ENV', default='remote')


class TestReminder:
    CALDAV_CONNECTED: bool = False

    @staticmethod
    def __create_reminder_from_local() -> Reminder:
        uuid = "x-apple-id://1234-5678-9012"
        name = "Test reminder"
        created_date = "Thursday, 18 April 2024 at 08:00:00"
        completed = 'false'
        due_date = "Thursday, 18 April 2024 at 18:00:00"
        all_day = 'missing value'
        remind_me_date = "Thursday, 18 April 2024 at 18:00:00"
        modified_date = "Thursday, 18 April 2024 at 17:50:00"
        completion = 'missing value'
        body = "Test reminder body."

        values = [uuid, name, created_date, completed, due_date, all_day, remind_me_date, modified_date, completion, body]
        reminder = Reminder.create_from_local(values)
        return reminder

    # noinspection SpellCheckingInspection
    @staticmethod
    def __create_reminder_from_remote() -> Reminder:
        obj = caldav.CalendarObjectResource()
        # noinspection PyUnresolvedReferences
        obj._set_data("""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Nextcloud Tasks v0.15.0
BEGIN:VTODO
CREATED:20240418T084019
DESCRIPTION:Test reminder body
DTSTAMP:20240418T084042
DUE:20240418T180000
LAST-MODIFIED:20240418T084042
SUMMARY:Test reminder
UID:f4a682ac-86f2-4f81-a08e-ccbff061d7da
END:VTODO
END:VCALENDAR
""")
        reminder = Reminder.create_from_remote(obj)
        return reminder

    @staticmethod
    def __connect_caldav(fail: bool = False, test_caldav: bool = True):
        if TestReminder.CALDAV_CONNECTED and not fail:
            TestReminder.CALDAV_CONNECTED = False
            return

        if test_caldav:
            conf_file = Path(os.path.abspath(os.path.dirname(__file__))) / "conf.json"
        else:
            conf_file = helpers.settings_folder() / 'conf.json'
        if not os.path.exists(conf_file):
            assert False, "Failed to load configuration file at {}".format(conf_file)

        with open(conf_file, 'r') as fp:
            settings = json.load(fp)

        ReminderController.CALDAV_USERNAME = settings['caldav_username']
        ReminderController.CALDAV_URL = settings['caldav_url']
        ReminderController.CALDAV_HEADERS = {}

        if fail:
            ReminderController.CALDAV_PASSWORD = 'bogus'
        elif test_caldav:
            ReminderController.CALDAV_PASSWORD = config('TEST_CALDAV_PASSWORD')
        else:
            ReminderController.CALDAV_PASSWORD = keyring.get_password("TaskBridge", "CALDAV-PWD")

        ReminderController.TO_SYNC = settings['reminder_sync']
        ReminderController.connect_caldav()
        TestReminder.CALDAV_CONNECTED = True

    def test_create_from_local(self):
        uuid = "x-apple-id://1234-5678-9012"
        name = "Test reminder"
        created_date = "Thursday, 18 April 2024 at 08:00:00"
        remind_me_date = "Thursday, 18 April 2024 at 18:00:00"
        modified_date = "Thursday, 18 April 2024 at 17:50:00"
        body = "Test reminder body."
        reminder = TestReminder.__create_reminder_from_local()

        assert reminder.uuid == uuid
        assert reminder.name == name
        assert reminder.created_date == DateUtil.convert(DateUtil.APPLE_DATETIME, created_date)
        assert reminder.modified_date == DateUtil.convert(DateUtil.APPLE_DATETIME, modified_date)
        assert reminder.completed_date == DateUtil.convert(DateUtil.APPLE_DATETIME, modified_date)
        assert reminder.body == body
        assert reminder.remind_me_date == DateUtil.convert(DateUtil.APPLE_DATETIME, remind_me_date)
        assert reminder.due_date == DateUtil.convert(DateUtil.APPLE_DATETIME, reminder.due_date)
        assert reminder.all_day is False
        assert reminder.completed is False

    def test_create_from_remote(self):
        reminder = TestReminder.__create_reminder_from_remote()

        assert reminder.uuid == "f4a682ac-86f2-4f81-a08e-ccbff061d7da"
        assert reminder.name == "Test reminder"
        assert reminder.created_date == DateUtil.convert(DateUtil.CALDAV_DATETIME, "20240418T084042")
        assert reminder.modified_date == DateUtil.convert(DateUtil.CALDAV_DATETIME, "20240418T084042")
        assert reminder.body == "Test reminder body"
        assert reminder.due_date == DateUtil.convert(DateUtil.CALDAV_DATETIME, "20240418T180000")
        assert reminder.all_day is False
        assert reminder.completed is False

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud")
    def test_upsert_local(self):
        local_list = LocalList("Sync")
        remote_calendar = RemoteCalendar(calendar_name="Sync")
        container = ReminderContainer(local_list, remote_calendar, True)
        reminder = TestReminder.__create_reminder_from_remote()
        success, data = reminder.upsert_local(container)
        assert success is True
        local_uuid = data

        # Test failure
        values = ["x-coredata://invalid", "Invalid", 'invalid', None, 'missing value', 'missing value', 'missing value',
                  "Thursday, 31 December 2999 at 17:50:00", False, '']
        bad_reminder = Reminder.create_from_local(values)
        success, data = bad_reminder.upsert_local(container)
        assert success is False

        # Clean Up
        delete_reminder_script = reminderscript.delete_reminder_script
        helpers.run_applescript(delete_reminder_script, local_uuid)

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires CalDAV credentials")
    def test_upsert_remote(self):
        TestReminder.__connect_caldav()
        success, remote_calendars = ReminderContainer.load_caldav_calendars()
        if not success:
            assert False, "Failed to load remote calendars."
        remote_calendar = next((rc for rc in remote_calendars if rc.name == "Sync"), None)

        # Typical Reminder
        local_list = LocalList("Sync")
        container = ReminderContainer(local_list, remote_calendar, True)
        reminder = TestReminder.__create_reminder_from_local()
        success, data = reminder.upsert_remote(container)
        assert success is True

        # Reminder with all-day due date, no time remind date and completed
        reminder = TestReminder.__create_reminder_from_local()
        reminder.due_date = datetime.datetime(2024, 12, 31, 0, 0, 0)
        reminder.remind_me_date = datetime.datetime(2024, 12, 31, 0, 0, 0)
        reminder.all_day = True
        reminder.completed = True
        reminder.completed_date = datetime.datetime(2024, 12, 31, 0, 0, 0)
        success, data = reminder.upsert_remote(container)
        assert success is True

        # Update same reminder
        success, data = reminder.upsert_remote(container)
        assert success is True

        # Test changing due date
        reminder2 = TestReminder.__create_reminder_from_local()
        reminder2.name = "SECOND TEST"
        success, data = reminder2.upsert_remote(container)
        assert success is True
        reminder2.due_date = datetime.datetime(2024, 12, 31, 19, 30, 25)
        success, data = reminder2.upsert_remote(container)
        assert success is True

        # Test Failure 1 (new, invalid due date)
        reminder3 = TestReminder.__create_reminder_from_local()
        reminder3.uuid = "1234567890"
        reminder3.name = "Invalid Reminder ABC"
        reminder3.due_date = "INVALID"
        success, ical_string = reminder3.upsert_remote(container)
        assert success is False

        # Test Failure 2 (existing, invalid due date)
        reminder4 = TestReminder.__create_reminder_from_local()
        reminder4.name = "Invalid Reminder ABC"
        reminder4.due_date = "INVALID"
        success, ical_string = reminder4.upsert_remote(container)
        assert success is False

        # Clean Up
        to_delete = container.remote_calendar.cal_obj.search(todo=True, uid=reminder.uuid)
        if len(to_delete) > 0:
            try:
                for kill in to_delete:
                    kill.delete()
            except AuthorizationError:
                print('Warning, failed to delete remote item.')

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud")
    def test_update_uuid(self):
        TestReminder.__connect_caldav()
        success, remote_calendars = ReminderContainer.load_caldav_calendars()
        if not success:
            assert False, "Failed to load remote calendars."
        remote_calendar = next((rc for rc in remote_calendars if rc.name == "Sync"), None)
        local_list = LocalList("Sync")
        container = ReminderContainer(local_list, remote_calendar, True)
        reminder = TestReminder.__create_reminder_from_local()
        success, data = reminder.upsert_remote(container)
        assert success, 'Failed to upsert remote reminder.'
        reminder.update_uuid(container, "NEW-UUID-1234-5678")
        assert reminder.uuid == "NEW-UUID-1234-5678"

        # Test Failure
        reminder.uuid = "Invalid UUID"
        success, data = reminder.update_uuid(container, "NEW UUID")
        assert success is False

        # Clean Up
        to_delete = container.remote_calendar.cal_obj.search(todo=True, uid="NEW-UUID-1234-5678")
        if len(to_delete) > 0:
            try:
                to_delete[0].delete()
            except AuthorizationError:
                print('Warning, failed to delete remote item.')

    def test_get_ical_string(self):
        reminder = TestReminder.__create_reminder_from_local()
        success, ical_string = reminder.get_ical_string()
        assert success is True
        assert ical_string == """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Pint-Sized Software//TaskBridge//NONSGML v1.0//EN
BEGIN:VTODO
DUE;VALUE=DATE-TIME:20240418T180000
DTSTAMP:20240418T175000
LAST-MODIFIED:20240418T175000
SUMMARY:Test reminder
STATUS:NEEDS-ACTION
UID:x-apple-id://1234-5678-9012
BEGIN:VALARM
TRIGGER;VALUE=DATE-TIME:20240418T180000
ACTION:DISPLAY
DESCRIPTION:Test reminder
END:VALARM
END:VTODO
END:VCALENDAR
"""

        # Test 2 (Due date and remind date with no time, completed)
        reminder2 = TestReminder.__create_reminder_from_local()
        reminder2.due_date = datetime.datetime(2024, 12, 31)
        reminder2.remind_me_date = datetime.datetime(2024, 12, 31)
        reminder2.all_day = True
        reminder2.completed = True
        reminder2.completed_date = datetime.datetime(2024, 12, 31)
        success, ical_string = reminder2.get_ical_string()
        assert success is True

        # Test 3 (No due date, No alarm)
        reminder3 = TestReminder.__create_reminder_from_local()
        reminder3.due_date = None
        reminder2.remind_me_date = None
        success, ical_string = reminder3.get_ical_string()
        assert success is True

        # Test failure 1 (invalid due date)
        reminder4 = TestReminder.__create_reminder_from_local()
        reminder4.due_date = "INVALID"
        success, ical_string = reminder4.get_ical_string()
        assert success is False

        # Test failure 2 (invalid alarm date)
        reminder5 = TestReminder.__create_reminder_from_local()
        reminder5.remind_me_date = "INVALID"
        success, ical_string = reminder5.get_ical_string()
        assert success is False

    def test___str__(self):
        reminder = TestReminder.__create_reminder_from_local()
        name = reminder.__str__()
        assert name == "Test reminder"

    def test___repr__(self):
        reminder = TestReminder.__create_reminder_from_local()
        name = reminder.__repr__()
        assert name == "Test reminder"
