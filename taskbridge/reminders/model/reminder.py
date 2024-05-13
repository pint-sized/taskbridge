"""
Contains the ``Reminder`` class, which represents a reminder (whether local or remote).
"""

from __future__ import annotations

import datetime
from typing import List

import caldav

import taskbridge.reminders.model.remindercontainer as model
from taskbridge import helpers
from taskbridge.helpers import DateUtil
from taskbridge.reminders.model import reminderscript


class Reminder:
    """
    Represents a reminder. Used to create reminders from the local machine via AppleScript or reminders from a remote
    CalDav server.
    """

    def __init__(self,
                 uuid: str | None,
                 name: str,
                 created_date: datetime.datetime | None,
                 modified_date: datetime.datetime,
                 completed_date: datetime.datetime | None,
                 body: str | None,
                 remind_me_date: datetime.datetime | None,
                 due_date: datetime.datetime | datetime.date | None,
                 all_day: bool = False,
                 completed: bool = False,
                 ):
        """
        Create a new reminder.

        :param uuid: the UUID of this reminder.
        :param name: the name (i.e. many text/summary) of this reminder.
        :param created_date: the datetime when this reminder was created.
        :param modified_date: the datetime when this reminder was last modified.
        :param completed_date: if completed, the datetime when this reminder was completed.
        :param body: the body of the reminder (i.e. the description).
        :param remind_me_date: the datetime when the user should be alerted.
        :param due_date: the datetime or date when the reminder is due.
        :param all_day: if ``due_date`` is a date, rather than a datetime, this is set to True.
        :param completed: True if this reminder has been completed.
        """
        self.uuid: str | None = uuid
        self.name: str = name
        self.created_date: datetime.datetime | None = created_date
        self.modified_date: datetime.datetime = modified_date
        self.completed_date: datetime.datetime | None = completed_date
        self.body: str | None = body
        self.completed: bool = completed
        self.remind_me_date: datetime.datetime | None = remind_me_date
        self.due_date: datetime.datetime | datetime.date | None = due_date
        self.all_day: bool = all_day
        self.default_alarm_hour = 9

    @staticmethod
    def create_from_local(values: List[str]) -> Reminder:
        """
        Creates a Reminder instance from the given values.

        The ``values`` list must be as follows (all strings):

        0. Reminder UUID.
        1. Reminder name (i.e. summary).
        2. Reminder creation date.
        3. True if reminder is completed.
        4. Reminder due date.
        5. True if this is an all day reminder.
        6. Reminder alarm date.
        7. Reminder modified date.
        8. Completion date of reminder (ignored)
        9. Body (i.e. description) of the reminder.

        :param values: the list of values as described above.

        :return: a Reminder instance representing the content of the values given.
        """
        values[4] = values[4].strip()
        values[5] = values[5].strip()
        values[6] = values[6].strip()
        values[9] = values[9].strip()
        return Reminder(
            uuid=values[0],
            name=values[1],
            created_date=DateUtil.convert(DateUtil.APPLE_DATETIME, values[2].strip()),
            modified_date=DateUtil.convert(DateUtil.APPLE_DATETIME, values[7].strip()),
            completed_date=DateUtil.convert(DateUtil.APPLE_DATETIME, values[7].strip()),
            body=values[9] if values[9] != 'missing value' else None,
            remind_me_date=None if values[6] == 'missing value' else DateUtil.convert(DateUtil.APPLE_DATETIME, values[6]),
            due_date=None if values[4] == 'missing value' else DateUtil.convert(DateUtil.APPLE_DATETIME, values[4]),
            all_day=False if values[5] == "missing value" else True,
            completed=False if values[3] == "false" else True
        )

    @staticmethod
    def create_from_remote(caldav_task: caldav.CalendarObjectResource) -> Reminder:
        """
        Creates a Reminder instance from a CalDav task.

        :param caldav_task: a task fetched from the CalDav calendar.
        :return: a Reminder instance representing the CalDav task.
        """

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
            all_day=True if 'DUE' in comp and comp['DUE'].dt.strftime("%H:%M:%S") == "00:00:00" else False,
            completed='COMPLETED' in comp
        )

    def upsert_local(self, container: model.ReminderContainer) -> tuple[bool, str]:
        """
        Creates or updates a local reminder.

        :param container: the container containing this reminder.

        :returns:

            -success (:py:class:`bool`) - true if the reminder is successfully upserted.

            -data (:py:class:`str`) - error message on failure, or reminder's UUID.

        """
        add_reminder_script = reminderscript.add_reminder_script

        return_code, stdout, stderr = (
            helpers.run_applescript(add_reminder_script,
                                    self.uuid if self.uuid and self.uuid.startswith('x-coredata') else '',
                                    self.name,
                                    self.body if self.body is not None else '',
                                    'true' if self.completed else 'false',
                                    DateUtil.convert('', self.completed_date,
                                                     DateUtil.APPLE_DATETIME) if self.completed_date else '',
                                    DateUtil.convert('', self.due_date, DateUtil.APPLE_DATETIME) if self.due_date else '',
                                    'true' if self.all_day else 'false',
                                    DateUtil.convert('', self.remind_me_date,
                                                     DateUtil.APPLE_DATETIME) if self.remind_me_date else '',
                                    container.local_list.name
                                    ))
        if return_code == 0:
            # Set the UUID to that returned by AS
            if self.uuid is None:
                self.uuid = stdout.strip()
            return True, stdout.strip()
        return False, "Failed to upsert local reminder {0}: {1}".format(self.name, stderr)

    def __get_tasks_in_caldav(self, container: model.ReminderContainer) -> caldav.CalendarObjectResource | None:
        """
        Fetch an existing remote task in CalDav

        :param container: The parameter to search

        :return: the task in CalDAV matching this tasks UUID/name, or None.
        """

        remote = None
        tasks_in_caldav = container.remote_calendar.cal_obj.search(todo=True, uid=self.uuid)
        if len(tasks_in_caldav) == 0:
            tasks_in_caldav = container.remote_calendar.cal_obj.search(todo=True, summary=self.name)

        if len(tasks_in_caldav) > 0:
            remote = tasks_in_caldav[0]
        return remote

    def __get_task_due_date(self) -> tuple[bool, str]:
        """
        Get the due date for this task in string format

        :returns:

            -success (:py:class:`bool`) - true if the due date is successfully retrieved.

            -data (:py:class:`str`) - error message on failure, or task due date.

        """
        try:
            if not self.due_date:
                due_date = None
            elif self.due_date.strftime("%H:%M:%S") == "00:00:00":
                due_date = DateUtil.convert('', self.due_date, DateUtil.CALDAV_DATE)
            else:
                due_date = DateUtil.convert('', self.due_date, DateUtil.CALDAV_DATETIME)
        except AttributeError:
            return False, "Invalid due date."
        return True, due_date

    def upsert_remote(self, container: model.ReminderContainer) -> tuple[bool, str]:
        """
        Creates or updates a remote reminder.

        :param container: the container containing this reminder.

        :returns:

            -success (:py:class:`bool`) - true if the reminder is successfully upserted.

            -data (:py:class:`str`) - error message on failure or success message.

        """
        remote = self.__get_tasks_in_caldav(container)

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
            success, data = self.__get_task_due_date()
            if not success:
                return success, data
            due_date = data

            if not self.remind_me_date:
                alarm_trigger = None
            else:
                if self.remind_me_date.strftime("%H:%M:%S") == "00:00:00":
                    # Alarm with no time
                    self.remind_me_date = self.remind_me_date.replace(hour=self.default_alarm_hour, minute=0)
                alarm_trigger = DateUtil.convert('', self.remind_me_date, DateUtil.CALDAV_DATETIME)

            remote.icalendar_component["uid"] = self.uuid
            remote.icalendar_component["summary"] = self.name
            if due_date:
                remote.icalendar_component["due"] = due_date
            remote.icalendar_component["status"] = 'COMPLETED' if self.completed else 'NEEDS-ACTION'
            if alarm_trigger:
                remote.icalendar_component["trigger"] = alarm_trigger
            if self.completed:
                remote.icalendar_component["PERCENT-COMPLETE"] = "100"
                remote.icalendar_component["COMPLETED"] = DateUtil.convert('', self.completed_date, DateUtil.CALDAV_DATETIME)
            remote.save()
            return True, 'Remote reminder updated: {}'.format(self.name)

    def update_uuid(self, container: model.ReminderContainer, new_uuid: str) -> tuple[bool, str]:
        """
        Updates the UUID of a reminder. This is used when a remote reminder is synchronised locally. The locally-assigned
        UUID is used to set the UID of the remote reminder. This is done since the local UUID is read-only.

        :param container: the container containing this reminder.
        :param new_uuid: the UUID to assign to the reminder.

        :returns:

            -success (:py:class:`bool`) - true if the reminder's UUID is successfully upserted.

            -data (:py:class:`str`) - error message on failure or success message.

        """
        tasks_in_caldav = container.remote_calendar.cal_obj.search(todo=True, uid=self.uuid)
        if len(tasks_in_caldav) > 0:
            remote = tasks_in_caldav[0]
            self.uuid = new_uuid
            remote.icalendar_component["uid"] = self.uuid
            remote.save()
            return True, 'Remote reminder UID updated'
        return False, 'Could not find remote reminder to update UUID: {} ({})'.format(self.uuid, self.name)

    def get_ical_string(self) -> tuple[bool, str]:
        """
        Returns a representation of this reminder as an iCal string. Used for upserting remote reminders.

        :returns:

            -success (:py:class:`bool`) - true if the reminder is successfully parsed to an iCal string.

            -data (:py:class:`str`) - error message on failure or the iCal string.

        """
        success, data = self._parse_due_date()
        if not success:
            return success, data
        due_string = data

        success, data = self._parse_alarm()
        if not success:
            return success, data
        alarm_string = data

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

    def _parse_due_date(self) -> tuple[bool, str] | tuple[bool, None]:
        """
        Parse this reminder's due date into iCal format.

        :returns:

            -success (:py:class:`bool`) - true if the reminder's due date is successfully parsed.

            -data (:py:class:`str` | None) - error message on failure or the iCal string, or None if no due date.

        """
        if self.due_date is None:
            return True, None

        due_date = None
        due_string = None
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
        except AttributeError as e:
            return False, 'Unable to parse reminder due date for {0} ({1}): {2}'.format(self.due_date, self.name, e)
        return True, due_string

    def _parse_alarm(self) -> tuple[bool, str] | tuple[bool, None]:
        """
        Parse this reminder's alarm date into iCal format.

        :returns:

            -success (:py:class:`bool`) - true if the reminder's alarm date is successfully parsed.

            -data (:py:class:`str` | None) - error message on failure or the iCal string, or None if no remind me date.

        """
        if self.remind_me_date is None:
            return True, None
        alarm_trigger = None
        alarm_string = None
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
        except AttributeError as e:
            return False, 'Unable to parse reminder remind me date for {0} ({1}): {2}'.format(self.remind_me_date, self.name,
                                                                                              e)
        return True, alarm_string

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name
