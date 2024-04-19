import os
import json

import pytest
import caldav
import keyring
from decouple import config

import taskbridge.helpers as helpers
from taskbridge.reminders.model.reminder import Reminder
from taskbridge.reminders.model.remindercontainer import ReminderContainer, LocalList, RemoteCalendar
from taskbridge.reminders.controller import ReminderController
from taskbridge.helpers import DateUtil

TEST_ENV = config('TEST_ENV', default='remote')


class TestReminder:

    @staticmethod
    def __create_reminder_from_local() -> Reminder:
        uuid = "x-apple-id://1234-5678-9012"
        name = "Test reminder"
        created_date = "Thursday, 18 April 2024 at 08:00:00"
        completed = 'false'
        due_date = "Thursday, 18 April 2024 at 18:00:00"
        all_day = 'false'
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
    def __connect_caldav():
        conf_file = helpers.settings_folder() / 'conf.json'
        if not os.path.exists(conf_file):
            assert False, "Failed to load configuration file."
        with open(helpers.settings_folder() / 'conf.json', 'r') as fp:
            settings = json.load(fp)

        ReminderController.CALDAV_USERNAME = settings['caldav_username']
        ReminderController.CALDAV_URL = settings['caldav_url']
        ReminderController.CALDAV_HEADERS = {}
        ReminderController.CALDAV_PASSWORD = keyring.get_password("TaskBridge", "CALDAV-PWD")
        ReminderController.TO_SYNC = settings['reminder_sync']
        ReminderController.connect_caldav()

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

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires CalDAV credentials")
    def test_upsert_remote(self):
        TestReminder.__connect_caldav()
        success, remote_calendars = ReminderContainer.load_caldav_calendars()
        if not success:
            assert False, "Failed to load remote calendars."
        remote_calendar = next((rc for rc in remote_calendars if rc.name == "Sync"), None)

        local_list = LocalList("Sync")
        container = ReminderContainer(local_list, remote_calendar, True)
        reminder = TestReminder.__create_reminder_from_local()
        success, data = reminder.upsert_remote(container)
        assert success is True

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
