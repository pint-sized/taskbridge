from __future__ import annotations

from datetime import datetime
from typing import List

from Model.Util import Util


class Reminder:
    REMINDER_LIST: List[Reminder] = []
    __APPLE_DATE_FORMAT = "%A, %d %B %Y at %H:%M:%S"

    def __init__(self, **kwargs):
        self.id: str = kwargs.get('id', '')
        self.name: str = kwargs.get('name', '')
        self.creation_date: datetime = kwargs.get('creation_date', datetime.now())
        self.completed: bool = kwargs.get('completed', False)
        self.due_date: datetime = kwargs.get('due_date', datetime.now())
        self.reminder_date: datetime = kwargs.get('reminder_date', datetime.now())
        self.modification_date: datetime = kwargs.get('modification_date', datetime.now())
        self.completion_date: datetime = kwargs.get('completion_date', datetime.now())
        self.default_alarm_hour: int = kwargs.get('default_alarm_hour', 9)
        Reminder.REMINDER_LIST.append(self)

    @staticmethod
    def from_tokenized(line: str, token: str = '|') -> None:
        values = line.split(token)
        Reminder(
            id=values[0],
            name=values[1],
            creation_date=Util.get_apple_datetime(values[2]),
            completed=False if values[3] == "false" else True,
            due_date=Util.get_apple_datetime(values[4]),
            reminder_date=Util.get_apple_datetime(values[6]),
            modification_date=Util.get_apple_datetime(values[7]),
            completion_date=Util.get_apple_datetime(values[7])
        )

    @property
    def status(self) -> str:
        return "COMPLETED" if self.completed else "NEEDS-ATTENTION"

    def get_ical_string(self) -> str:

        due_date = None
        try:
            if self.due_date.strftime("%H:%M:%S") == "00:00:00":
                ds = Util.get_caldav_date_string(self.due_date)
                if ds:
                    due_date = 'DATE:' + ds
            else:
                ds = Util.get_caldav_datetime_string(self.due_date)
                if ds:
                    due_date = 'DATE-TIME:' + ds
            if due_date is not None:
                due_string = "DUE;VALUE={due_date}".format(due_date=due_date)
            else:
                due_string = None
        except AttributeError:
            due_string = None

        alarm_trigger = None
        try:
            if self.reminder_date.strftime("%H:%M:%S") == "00:00:00":
                # Alarm with no time
                self.reminder_date = self.reminder_date.replace(hour=self.default_alarm_hour, minute=0)
            ds = Util.get_caldav_datetime_string(self.reminder_date)
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
        except AttributeError:
            alarm_string = None

        modification_date = Util.get_caldav_datetime_string(self.modification_date)

        ical_string = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Pint-Sized Software//BitMirror//NONSGML v1.0//EN
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
           id=self.id)

        if alarm_string is not None:
            ical_string += alarm_string + "\n"

        ical_string += """END:VTODO
END:VCALENDAR
"""
        return ical_string
