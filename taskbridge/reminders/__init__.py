"""
This is the model package for the reminder-syncing part of TaskBridge. Here, you'll find the following:

- ``reminder.py`` - Contains the ``Reminder`` class which represents a reminder (either local or remote).
- ``remindercontainer.py`` - Contains the ``ReminderContainer`` class which represents a synced pair of list and calendar,
and the ``LocalList``  and ``RemoteCalendar`` classes that represent a local reminder list and remote task calendar
respectively.
- ``reminderscript.py`` - Contains a list of AppleScript scripts for managing local reminders.

"""

from . import model
from . import controller

__all__ = ['model', 'controller', ]
