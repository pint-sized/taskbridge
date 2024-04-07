"""
This is the note synchronisation controller. It takes care of the note synchronisation process.
"""

import datetime
import logging
import sys
from pathlib import Path

from taskbridge.notes.model.notefolder import NoteFolder


def sync(nc_notes_folder: Path, associations: dict):
    """
    Carries out the note synchronisation process.

    :param nc_notes_folder: path to the folder on the filesystem which synchronises remotely.
    :param associations: list of folder associations as shown below.

    The associations dictionary must contain the following keys:

        - ``local_to_remote`` - notes to push from local to remote as :py:class`List[str]`.
        - ``remote_to_local`` - notes to pull from remote to local as :py:class`List[str]`.
        - ``bi_directional`` - notes to synchronise in both folders as :py:class`List[str]`.

    """
    logging.info('-- STARTING NOTE SYNC --')

    # Fetch local notes folders
    success, data = NoteFolder.load_local_folders()
    if not success:
        logging.critical('Failed to fetch local notes folders: {}'.format(data))
        sys.exit(1)
    local_note_folders = data
    logging.debug('Found local notes folders: {}'.format([str(folder) for folder in local_note_folders]))

    # Fetch remote notes folders
    success, data = NoteFolder.load_remote_folders(nc_notes_folder)
    if not success:
        logging.critical('Failed to fetch remote notes folders: {}'.format(data))
        sys.exit(2)
    remote_note_folders = data
    logging.debug('Found remote notes folders: {}'.format([str(folder) for folder in remote_note_folders]))

    # Sync deleted folders
    success, data = NoteFolder.sync_folder_deletions(local_note_folders, remote_note_folders)
    if not success:
        logging.critical('Failed to sync folder deletions {}'.format(data))
        sys.exit(3)
    logging.debug('Folder deletions synchronised.')

    # Associate folders
    success, data = NoteFolder.create_linked_folders(local_note_folders, remote_note_folders, nc_notes_folder, associations)
    if not success:
        logging.critical('Failed to associate folders {}'.format(data))
        sys.exit(4)
    logging.debug('Folder Associations: {}'.format([str(folder) for folder in NoteFolder.FOLDER_LIST]))

    # Sync deleted notes
    success, data = NoteFolder.sync_note_deletions(nc_notes_folder)
    if not success:
        logging.critical('Failed to synchronise note deletions {}'.format(data))
        sys.exit(5)
    logging.debug("Deleted notes synchronisation:: Deleted Local: {} | Deleted Remote: {} | Remote Not Found: {} | Local Not Found: {}".format(
        ','.join(data['local_deleted']),
        ','.join(data['remote_deleted']),
        ','.join(data['remote_not_found']),
        ','.join(data['local_not_found'])
    ))

    # Sync notes
    for folder in NoteFolder.FOLDER_LIST:
        success, data = folder.sync_notes()
        if not success:
            logging.critical('Failed to sync notes {}'.format(data))
            sys.exit(6)
    logging.debug(
        "Notes synchronisation:: Remote Added: {} | Remote Updated: {} | Local Added: {} | Local Updated: {}".format(
            ','.join(data['remote_added']),
            ','.join(data['remote_updated']),
            ','.join(data['local_added']),
            ','.join(data['local_updated'])
        ))

    logging.info('-- FINISHED NOTE SYNC --')


log_folder = Path.home() / "Library" / "Logs" / "TaskBridge"
log_folder.mkdir(parents=True, exist_ok=True)
log_file = datetime.datetime.now().strftime("Notes_%Y%m%d-%H%M%S") + '.log'
log_level = logging.DEBUG
logging.basicConfig(
    level=log_level,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(log_folder / log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
