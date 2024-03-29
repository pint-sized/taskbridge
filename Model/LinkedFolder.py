from __future__ import annotations
from typing import List

from Model import NoteFolder


class LinkedFolder:
    FOLDER_LIST: List[LinkedFolder] = []

    NO_SYNC: int = 0
    LOCAL_TO_REMOTE: int = 1
    REMOTE_TO_LOCAL: int = 2
    BI_DIRECTONAL: int = 3

    def __init__(self, local_folder: NoteFolder, remote_folder: str, sync_direction: int = NO_SYNC):
        self.local_folder: NoteFolder = local_folder
        self.remote_folder: str = remote_folder
        self.sync_direction: int = sync_direction
        LinkedFolder.FOLDER_LIST.append(self)
