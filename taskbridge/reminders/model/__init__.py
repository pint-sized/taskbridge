"""
This is the model of the reminder-syncing part of TaskBridge. Here, you'll find the following:

- ``reminder.py`` - Contains the ``Reminder`` class which represents a reminder.
- ``remindercontainer.py`` - Contains the ``ReminderContainer`` class which represents a container (either local or remote)
which contains reminders. Many sync operations are performed here. Also contains the ``LocalList`` class which represents a
local reminder list, and ``RemoteCalendar`` class, which represents a remote CalDav *VTODO* calendar.
- ``reminderscript.py`` - Contains a list of AppleScript scripts for managing local reminders.

"""

from . import reminder, remindercontainer, reminderscript

__all__ = ['reminder', 'remindercontainer', 'reminderscript', ]
