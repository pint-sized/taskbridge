"""
This is the model of the note-syncing part of TaskBridge. Here, you'll find the following:

- ``note.py`` - Contains the ``Note`` and ``Attachment`` classes that represent a note and its attachment respectively.
- ``notefolder.py`` - Contains the ``NoteFolder`` class which represents a folder (either local or remote) which
contains notes. Many sync operations are performed here.
- ``notescript.py`` - Contains a list of AppleScript scripts for managing local notes.

"""

from . import note, notefolder, notescript

__all__ = ['note', 'notefolder', 'notescript', ]
