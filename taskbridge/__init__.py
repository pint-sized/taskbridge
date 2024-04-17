"""
This is the main package for TaskBridge.

- ``notes`` - the note-synchronisation part of TaskBridge.
- ``reminders`` - the reminder-synchronisation part of TaskBridge.
- ``gui`` - the TaskBridge GUI and related assets.
- ``helpers`` - helpers used by both note and reminder synchronisation.

"""

from . import helpers

__all__ = ['helpers', ]
