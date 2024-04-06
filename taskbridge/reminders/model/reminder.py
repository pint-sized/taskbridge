from __future__ import annotations

import datetime
from typing import List

import caldav

import helpers
import reminders.model.remindercontainer as model
from helpers import DateUtil
from reminders.model import reminderscript


class Reminder:
    def __init__(self,
                 uuid: str | None,
                 name: str,
                 created_date: datetime.datetime | None,
                 modified_date: datetime.datetime | None,
                 completed_date: datetime.datetime | None,
                 body: str | None,
                 remind_me_date: datetime.datetime | None,
                 due_date: datetime.datetime | datetime.date | None,
                 all_day: bool = False,
                 completed: bool = False,
                 ):
        self.uuid: str | None = uuid
        self.name: str = name
        self.created_date: datetime.datetime | None = created_date
        self.modified_date: datetime.datetime | None = modified_date
        self.completed_date: datetime.datetime | None = completed_date
        self.body: str | None = body
        self.completed: bool = completed
        self.remind_me_date: datetime.datetime | None = remind_me_date
        self.due_date: datetime.datetime | datetime.date | None = due_date
        self.all_day: bool = all_day
        self.default_alarm_hour = 9

    @staticmethod
    def create_from_local(values: List[str]) -> Reminder:
        return Reminder(
            uuid=values[0],
            name=values[1],
            created_date=DateUtil.convert(DateUtil.APPLE_DATETIME, values[2].strip()),
            modified_date=DateUtil.convert(DateUtil.APPLE_DATETIME, values[7].strip()),
            completed_date=DateUtil.convert(DateUtil.APPLE_DATETIME, values[7].strip()),
            body=values[9] if values[9] != 'missing value' else None,
            remind_me_date=DateUtil.convert(DateUtil.APPLE_DATETIME, values[6].strip()),
            due_date=DateUtil.convert(DateUtil.APPLE_DATETIME, values[4].strip()),
            all_day=False if values[5] == "false" else True,
            completed=False if values[3] == "false" else True
        )

    @staticmethod
    def create_from_remote(caldav_task: caldav.CalendarObjectResource) -> Reminder:
        comp = caldav_task.icalendar_component

        return Reminder(
            uuid=comp['UID'].to_ical().decode() if 'UID' in comp else None,
            name=comp['summary'].to_ical().decode(),
            created_date=comp['DTSTAMP'].dt if 'DTSTAMP' in comp else None,
            modified_date=comp['LAST-MODIFIED'].dt if 'LAST-MODIFIED' in comp else None,
            completed_date=comp['COMPLETED'].dt if 'COMPLETED' in comp else None,
            body=comp['description'].to_ical().decode() if 'DESCRIPTION' in comp else None,
            remind_me_date=comp['TRIGGER'].dt if 'TRIGGER' in comp else None,
            due_date=comp['DUE'].dt if 'DUE' in comp else None,
            all_day=True if comp['DUE'].dt.strftime("%H:%M:%S") == "00:00:00" else False,
            completed='COMPLETED' in comp
        )

    def upsert_local(self, container: model.ReminderContainer) -> tuple[bool, str]:
        add_reminder_script = reminderscript.add_reminder_script

        return_code, stdout, stderr = (
            helpers.run_applescript(add_reminder_script,
                                    self.uuid if self.uuid.startswith('x-coredata') else '',
                                    self.name,
                                    self.body if self.body is not None else '',
                                    'true' if self.completed else 'false',
                                    DateUtil.convert('', self.completed_date, DateUtil.APPLE_DATETIME) if self.completed_date else '',
                                    DateUtil.convert('', self.due_date, DateUtil.APPLE_DATETIME) if self.due_date else '',
                                    'true' if self.all_day else 'false',
                                    DateUtil.convert('', self.remind_me_date, DateUtil.APPLE_DATETIME) if self.remind_me_date else '',
                                    container.local_list.name
                                    ))
        if return_code == 0:
            # Set the UUID to that returned by AS
            if self.uuid is None:
                self.uuid = stdout.strip()
            return True, self.uuid
        return False, "Failed to upsert local reminder {0}: {1}".format(self.name, stderr)

    def upsert_remote(self, container: model.ReminderContainer) -> tuple[bool, str]:
        remote = None
        tasks_in_caldav = container.remote_calendar.cal_obj.search(todo=True, uid=self.uuid)
        if len(tasks_in_caldav) == 0:
            tasks_in_caldav = container.remote_calendar.cal_obj.search(todo=True, summary=self.name)

        if len(tasks_in_caldav) > 0:
            remote = tasks_in_caldav[0]

        if remote is None:
            # Add new remote task
            success, data = self.get_ical_string()
            if not success:
                return False, 'Unable to convert reminder {} to iCal string'.format(self.name)
            ical_string = data
            container.remote_calendar.cal_obj.save_todo(ical=ical_string)
            return True, 'Remote reminder added: {}'.format(self.name)
        else:
            # Update existing remote task
            if self.due_date.strftime("%H:%M:%S") == "00:00:00":
                due_date = DateUtil.convert('', self.due_date, DateUtil.CALDAV_DATE)
            else:
                due_date = DateUtil.convert('', self.due_date, DateUtil.CALDAV_DATETIME)

            if self.remind_me_date.strftime("%H:%M:%S") == "00:00:00":
                # Alarm with no time
                self.remind_me_date = self.remind_me_date.replace(hour=self.default_alarm_hour, minute=0)
            alarm_trigger = DateUtil.convert('', self.remind_me_date, DateUtil.CALDAV_DATETIME)

            remote.icalendar_component["uid"] = self.uuid
            remote.icalendar_component["summary"] = self.name
            remote.icalendar_component["due"] = due_date
            remote.icalendar_component["status"] = 'COMPLETED' if self.completed else 'NEEDS-ACTION'
            remote.icalendar_component["trigger"] = alarm_trigger
            if self.completed:
                remote.icalendar_component["PERCENT-COMPLETE"] = "100"
                remote.icalendar_component["COMPLETED"] = DateUtil.convert('', self.completed_date, DateUtil.CALDAV_DATETIME)
            remote.save()
            return True, 'Remote reminder updated: {}'.format(self.name)

    def update_uuid(self, container: model.ReminderContainer, new_uuid: str) -> tuple[bool, str]:
        tasks_in_caldav = container.remote_calendar.cal_obj.search(todo=True, uid=self.uuid)
        if len(tasks_in_caldav) > 0:
            remote = tasks_in_caldav[0]
            self.uuid = new_uuid
            remote.icalendar_component["uid"] = self.uuid
            remote.save()
            return True, 'Remote reminder UID updated'
        return False, 'Could not find remote reminder to update UUID: {} ({})'.format(self.uuid, self.name)

    def get_ical_string(self) -> tuple[bool, str]:
        due_date = None
        try:
            if self.due_date.strftime("%H:%M:%S") == "00:00:00":
                ds = DateUtil.convert('', self.due_date, DateUtil.CALDAV_DATE)
                if ds:
                    due_date = 'DATE:' + ds
            else:
                ds = DateUtil.convert('', self.due_date, DateUtil.CALDAV_DATETIME)
                if ds:
                    due_date = 'DATE-TIME:' + ds
            if due_date is not None:
                due_string = "DUE;VALUE={due_date}".format(due_date=due_date)
            else:
                due_string = None
        except AttributeError as e:
            return False, 'Unable to parse reminder due date for {0} ({1}): {2}'.format(self.due_date, self.name, e)

        alarm_trigger = None
        try:
            if self.remind_me_date.strftime("%H:%M:%S") == "00:00:00":
                # Alarm with no time
                self.remind_me_date = self.remind_me_date.replace(hour=self.default_alarm_hour, minute=0)
            ds = DateUtil.convert('', self.remind_me_date, DateUtil.CALDAV_DATETIME)
            if ds:
                alarm_trigger = 'DATE-TIME:' + ds
            if alarm_trigger is not None:
                alarm_string = """BEGIN:VALARM
TRIGGER;VALUE={alarm_trigger}
ACTION:DISPLAY
DESCRIPTION:{summary}
END:VALARM""".format(alarm_trigger=alarm_trigger, summary=self.name)
            else:
                alarm_string = None
        except AttributeError as e:
            return False, 'Unable to parse reminder remind me date for {0} ({1}): {2}'.format(self.remind_me_date, self.name, e)

        modification_date = DateUtil.convert('', self.modified_date, DateUtil.CALDAV_DATETIME)

        ical_string = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Pint-Sized Software//TaskBridge//NONSGML v1.0//EN
BEGIN:VTODO
"""
        if due_string is not None:
            ical_string += due_string + "\n"

        ical_string += """DTSTAMP:{modification_date}
LAST-MODIFIED:{modification_date}
SUMMARY:{summary}
STATUS:{status}
UID:{id}
""".format(modification_date=modification_date,
           summary=self.name,
           status='COMPLETED' if self.completed else 'NEEDS-ACTION',
           id=self.uuid)

        if alarm_string is not None:
            ical_string += alarm_string + "\n"

        ical_string += """END:VTODO
END:VCALENDAR
"""
        return True, ical_string

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name
