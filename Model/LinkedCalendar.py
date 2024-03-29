from __future__ import annotations
from typing import List

from caldav import Calendar


class LinkedCalendar:
    CALENDAR_LIST: List[LinkedCalendar] = []

    def __init__(self, reminder_list: ReminderList, caldav_calendar: Calendar):
        self.reminder_list: ReminderList = reminder_list
        self.caldav_calendar: Calendar = caldav_calendar
        LinkedCalendar.CALENDAR_LIST.append(self)


class ReminderList:
    def __init__(self, uuid: str, name: str):
        self.uuid: str = uuid
        self.name: str = name.strip()
