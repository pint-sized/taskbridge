import logging
import os
import pathlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import List

from Controller import notes_as, note_parser
from Model import NoteFolder, LinkedFolder, Util


logger = logging.getLogger(__name__)

NC_NOTES_FOLDER = ''
FOLDERS_BI_DIRECTIONAL = []
FOLDERS_LOCAL_TO_REMOTE = []
FOLDERS_REMOTE_TO_LOCAL = []

DRY_RUN = False


def confirm(prompt: str) -> bool:
    if DRY_RUN:
        ans = input(prompt + ':: [Y]/N> ')
        return ans == 'y' or ans == 'Y' or ans == ''
    return True


def get_local_notes_folders() -> List[NoteFolder]:
    logger.info("Retrieving Local Notes Folders.")
    notes_folders = []
    script_result = notes_as.run(notes_as.GET_FOLDER_LIST)
    stdout = script_result['stdout']
    for f_list in stdout.split('|'):
        data = f_list.split('~~')
        data[1] = data[1].strip()
        if data[1] != 'Recently Deleted':
            if confirm('Process local folder ' + data[1]):
                notes_folders.append(NoteFolder(data[0], data[1]))
    logging.info("Found {0:d} Local Notes Folders: {1:s}".format(
        len(notes_folders),
        ','.join([nf.name for nf in notes_folders])))
    return notes_folders


def get_remote_notes_folders() -> List[str]:
    logger.info("Retrieving Remote Notes Folders.")
    notes_folders = []
    for root, dirs, files in os.walk(NC_NOTES_FOLDER):
        for remote_dir in dirs:
            if not remote_dir.startswith("."):
                if confirm('Process remote folder ' + remote_dir):
                    notes_folders.append(remote_dir)
    logging.info("Found {0:d} Remote Notes Folders: {1:s}".format(
        len(notes_folders),
        ','.join([nf for nf in notes_folders])))

    return notes_folders


def sync_folders(local_folders: List[NoteFolder], remote_folders: List[str]) -> bool:
    logger.info("Associating local folders with remote folders.")
    for local_folder in local_folders:
        if (local_folder.name in FOLDERS_BI_DIRECTIONAL or local_folder.name in FOLDERS_LOCAL_TO_REMOTE) and local_folder.name not in remote_folders:
            logger.info('Creating remote folder {:s}'.format(local_folder.name))
            os.mkdir(NC_NOTES_FOLDER + local_folder.name)
        logger.info("Creating association for folder {:s}".format(local_folder.name))
        if local_folder.name in FOLDERS_BI_DIRECTIONAL:
            sync_dir = LinkedFolder.BI_DIRECTONAL
        elif local_folder.name in FOLDERS_LOCAL_TO_REMOTE:
            sync_dir = LinkedFolder.LOCAL_TO_REMOTE
        elif local_folder.name in FOLDERS_REMOTE_TO_LOCAL:
            sync_dir = LinkedFolder.REMOTE_TO_LOCAL
        else:
            sync_dir = LinkedFolder.NO_SYNC
        LinkedFolder(local_folder, local_folder.name, sync_dir)

    logger.info("Associating remote folders with local folders.")
    for remote_folder in remote_folders:
        assoc_local_folder = next((x for x in local_folders if x.name == remote_folder), None)
        if (remote_folder in FOLDERS_REMOTE_TO_LOCAL or remote_folder in FOLDERS_BI_DIRECTIONAL) and assoc_local_folder is None:
            logger.info("Creating local folder {:s}".format(remote_folder))
            script_result = notes_as.run(notes_as.CREATE_FOLDER, [remote_folder])
            local_folder = NoteFolder(script_result['stdout'], remote_folder)
            logger.info("Creating association for folder {:s}".format(local_folder.name))
            if remote_folder in FOLDERS_BI_DIRECTIONAL:
                sync_dir = LinkedFolder.BI_DIRECTONAL
            elif remote_folder in FOLDERS_LOCAL_TO_REMOTE:
                sync_dir = LinkedFolder.LOCAL_TO_REMOTE
            elif remote_folder in FOLDERS_REMOTE_TO_LOCAL:
                sync_dir = LinkedFolder.REMOTE_TO_LOCAL
            else:
                sync_dir = LinkedFolder.NO_SYNC
            LinkedFolder(local_folder, remote_folder, sync_dir)

    Util.export_folder_db(LinkedFolder.FOLDER_LIST)
    return True


def sync_notes(linked_folders: List[LinkedFolder]) -> None:
    for linked in linked_folders:
        logger.info("Synchronising::: Local:{0} --> Remote:{1}".format(
            linked.local_folder.name, linked.remote_folder))
        sync_local_to_remote(linked)


def sync_local_to_remote(linked_folder: LinkedFolder) -> None:
    if linked_folder.sync_direction == LinkedFolder.NO_SYNC:
        return

    # Export notes to staging area
    folder_name = linked_folder.local_folder.name
    logger.info("Exporting notes from folder {} to staging area".format(folder_name))
    script_result = notes_as.run(notes_as.GET_NOTES_FROM_FOLDER, [folder_name])
    staging_folder = script_result['stdout'].strip()
    logger.info("Exported to staging folder {}".format(staging_folder))

    sync_note_deletions(linked_folder, staging_folder)
    local_notes_in_folder = []

    # Loop through staged items
    for filename in os.listdir(staging_folder):
        f_name, f_ext = os.path.splitext(filename)
        if not f_ext == ".staged":
            continue
        staged = os.path.join(staging_folder, filename)
        local_notes_in_folder.append(staged)

        with open(staged) as fp:
            html = fp.read()
        note_name, local_modification_date, attachments, body = note_parser.from_html(html, staging_folder)
        image_list = [item for item in attachments if item['type'] == 'image']

        local_mod_stamp = local_modification_date.timestamp()
        remote_folder = NC_NOTES_FOLDER + folder_name
        remote_file = remote_folder + '/' + note_name + '.md'

        if not os.path.exists(remote_file) and (linked_folder.local_folder.name in FOLDERS_LOCAL_TO_REMOTE or linked_folder.local_folder.name in FOLDERS_BI_DIRECTIONAL):
            # Remote note doesn't exist, so we create it
            if confirm('Create new remote note ' + remote_file):
                logger.info('Creating Remote Note {}'.format(remote_file))
                with open(remote_file, 'w') as fp:
                    fp.write(body)
                    fp.close()
                os.utime(remote_file, (local_mod_stamp, local_mod_stamp))
                if len(image_list) > 0:
                    Util.copy_images_to_remote(staging_folder, remote_folder, image_list)
        else:
            # Remote exists, so we have to figure out who's newer
            remote_modification_date = datetime.fromtimestamp(os.path.getmtime(remote_file))
            if local_modification_date > remote_modification_date and (linked_folder.local_folder.name in FOLDERS_LOCAL_TO_REMOTE or linked_folder.local_folder.name in FOLDERS_BI_DIRECTIONAL):
                # Local is newer
                if confirm('Update existing remote note ' + remote_file):
                    logger.info('Updating Remote Note {}'.format(remote_file))
                    with open(remote_file, 'w') as fp:
                        fp.write(body)
                        fp.close()
                    os.utime(remote_file, (local_mod_stamp, local_mod_stamp))
                    if len(image_list) > 0:
                        Util.copy_images_to_remote(staging_folder, remote_folder, image_list)
            elif remote_modification_date > local_modification_date and (linked_folder.local_folder.name in FOLDERS_REMOTE_TO_LOCAL or linked_folder.local_folder.name in FOLDERS_BI_DIRECTIONAL):
                # Remote is newer
                if confirm('Update existing local note ' + remote_file):
                    logger.info('Updating Local Note {}'.format(note_name))
                    with open(remote_file) as fp:
                        updated_note = fp.read()
                        fp.close()

                    note_parser.from_markdown(updated_note, remote_folder)
                    note_name = os.path.splitext(os.path.basename(remote_file))[0]
                    script_result = notes_as.run(notes_as.UPDATE_NOTE, [folder_name, note_name])
                    mod_date = script_result['stdout']
                    local_modification_date = Util.get_apple_datetime(mod_date.replace('date', '').strip())
                    local_mod_stamp = local_modification_date.timestamp()
                    os.utime(remote_file, (local_mod_stamp, local_mod_stamp))

    logger.info("Synchronising::: Remote:{0} --> Local:{1}".format(
        linked_folder.remote_folder, folder_name))
    remote_sync = sync_remote_to_local(linked_folder, staging_folder)
    local_notes_in_folder.extend(remote_sync['added'])
    remote_notes_in_folder = remote_sync['existing']

    Util.export_note_list('local', folder_name, local_notes_in_folder)
    Util.export_note_list('remote', folder_name, remote_notes_in_folder)

    # Delete staging area
    if confirm('Delete staging area'):
        shutil.rmtree(staging_folder)


def sync_remote_to_local(linked_folder: LinkedFolder, staging_folder: str) -> dict:
    folder_name = linked_folder.remote_folder
    remote_folder = NC_NOTES_FOLDER + folder_name

    remote_notes = []
    notes_added = []

    # Loop through remote items
    for filename in os.listdir(remote_folder):
        f_name, f_ext = os.path.splitext(filename)
        if not f_ext == ".md":
            continue
        remote_file = os.path.join(remote_folder, filename)
        remote_notes.append(remote_file)
        staged_file = os.path.join(staging_folder, f_name + '.staged')
        if (linked_folder.local_folder.name in FOLDERS_REMOTE_TO_LOCAL or linked_folder.local_folder.name in FOLDERS_BI_DIRECTIONAL) and not os.path.exists(staged_file):
            if confirm('Create new local note ' + f_name):
                logger.info('Creating Local Note {}'.format(f_name))
                with open(remote_file) as fp:
                    new_note = fp.read()
                note_name, input_file = note_parser.from_markdown(new_note, remote_folder)
                script_result = notes_as.run(notes_as.CREATE_NOTE, [folder_name, note_name])
                mod_date = script_result['stdout']
                local_modification_date = Util.get_apple_datetime(mod_date.replace('date', '').strip())
                try:
                    local_mod_stamp = local_modification_date.timestamp()
                except AttributeError:
                    local_mod_stamp = datetime.now().timestamp()
                os.utime(remote_file, (local_mod_stamp, local_mod_stamp))
                notes_added.append(remote_file)
    return {
        'added': notes_added,
        'existing': remote_notes
    }


def sync_note_deletions(linked_folder: LinkedFolder, staging_folder_path: str) -> None:
    if linked_folder.sync_direction == LinkedFolder.NO_SYNC:
        return

    remote_folder_path = NC_NOTES_FOLDER + linked_folder.remote_folder

    already_deleted = []

    if linked_folder.local_folder.name in FOLDERS_LOCAL_TO_REMOTE or linked_folder.local_folder.name in FOLDERS_BI_DIRECTIONAL:
        # Notes deleted from local need to be removed from remote
        logger.info("Synchronising items deleted from local folder {0} to remote folder {1}".format(
            linked_folder.local_folder.name, linked_folder.remote_folder
        ))
        stored_local_notes = Util.import_note_list('local', linked_folder.local_folder.name)
        current_local_notes = []
        if not stored_local_notes:
            return
        for filename in os.listdir(staging_folder_path):
            f_name, f_ext = os.path.splitext(filename)
            if not f_ext == ".staged":
                continue
            staged_note = os.path.join(staging_folder_path, filename)
            current_local_notes.append(staged_note)
        deleted_local = [n for n in stored_local_notes if n not in current_local_notes]
        for deleted_item in deleted_local:
            remote_item = Path(os.path.splitext(remote_folder_path / Path(deleted_item).relative_to(staging_folder_path))[0] + '.md')
            if confirm('Delete remote note {}'.format(remote_item)):
                logger.info("Deleting Remote Note {}".format(remote_item))
                try:
                    Util.delete_remote_attachments(remote_item)
                    pathlib.Path.unlink(remote_item)
                except FileNotFoundError:
                    logger.warning("Warning: File {} could not be found for deletion from remote.".format(remote_item))
                already_deleted.append(remote_item.as_posix())

    if linked_folder.local_folder.name in FOLDERS_REMOTE_TO_LOCAL or linked_folder.local_folder.name in FOLDERS_BI_DIRECTIONAL:
        # Notes deleted from remote need to be removed from local
        logger.info("Synchronising items deleted from remote folder {1} to local folder {0}".format(
            linked_folder.local_folder.name, linked_folder.remote_folder
        ))
        stored_remote_notes = Util.import_note_list('remote', linked_folder.local_folder.name)
        current_remote_notes = []
        if not stored_remote_notes:
            return
        for filename in os.listdir(remote_folder_path):
            f_name, f_ext = os.path.splitext(filename)
            if not f_ext == ".md":
                continue
            remote_note = os.path.join(remote_folder_path, filename)
            if remote_note in already_deleted:
                continue
            current_remote_notes.append(remote_note)
        deleted_remote = [n for n in stored_remote_notes if n not in current_remote_notes and n not in already_deleted]
        for deleted_item in deleted_remote:
            # Delete from Notes app
            note_name = os.path.splitext(os.path.basename(deleted_item))[0]
            if confirm('Delete local note ' + note_name):
                logger.info("Deleting Local Note {}".format(note_name))
                notes_as.run(notes_as.DELETE_NOTE, [linked_folder.local_folder.name, note_name])


def sync_folder_deletions(current_local: List[NoteFolder], current_remote: List[str]) -> tuple[List[NoteFolder], List[str]]:
    old_state: List[LinkedFolder] = Util.import_folder_db()

    if not old_state:
        logger.info('No previous folder data. Not deleting any notes folders.')
        return current_local, current_remote

    # Check local deleted folders, delete associated folder from remote
    previous_local = [f.local_folder.name for f in old_state]
    current_local_names = [f.name for f in current_local]
    deleted_local_names = [f for f in previous_local if f not in current_local_names]
    for to_delete in deleted_local_names:
        if to_delete in FOLDERS_LOCAL_TO_REMOTE or to_delete in FOLDERS_BI_DIRECTIONAL:
            if confirm('Delete remote folder ' + to_delete):
                logger.info('The local folder {} was deleted. Removing it from remote'.format(to_delete))
                shutil.rmtree(NC_NOTES_FOLDER + to_delete)
                Util.delete_folder_db_item(to_delete)
                current_remote = [f for f in current_remote if f != to_delete]

    # Check remote deleted folders, delete associate folder from local
    previous_remote = [f.remote_folder for f in old_state]
    current_remote_names = [f for f in current_remote]
    deleted_remote_names = [f for f in previous_remote if f not in current_remote_names]
    for to_delete in deleted_remote_names:
        if to_delete in FOLDERS_REMOTE_TO_LOCAL or to_delete in FOLDERS_BI_DIRECTIONAL:
            if confirm('Delete local folder ' + to_delete):
                logger.info('The remote folder {} was deleted. Removing it from local'.format(to_delete))
                notes_as.run(notes_as.DELETE_FOLDER, [to_delete])
                Util.delete_folder_db_item(to_delete)
                current_local = [f for f in current_local if f.name != to_delete]

    return current_local, current_remote


def sync(nc_folder: str, bidirectional: List[str], local_to_remote: List[str], remote_to_local: List[str]):
    global NC_NOTES_FOLDER, FOLDERS_BI_DIRECTIONAL, FOLDERS_LOCAL_TO_REMOTE, FOLDERS_REMOTE_TO_LOCAL
    NC_NOTES_FOLDER = nc_folder
    FOLDERS_BI_DIRECTIONAL = bidirectional
    FOLDERS_LOCAL_TO_REMOTE = local_to_remote
    FOLDERS_REMOTE_TO_LOCAL = remote_to_local

    logging.basicConfig(filename='../log/note_sync.log', level=logging.INFO, format='%(asctime)s %(message)s')
    logger.info('--- STARTING NOTE SYNC ---')
    local_folders = get_local_notes_folders()
    remote_folders = get_remote_notes_folders()
    local_folders, remote_folders = sync_folder_deletions(local_folders, remote_folders)
    if sync_folders(local_folders, remote_folders):
        sync_notes(LinkedFolder.FOLDER_LIST)
    logger.info('--- FINISHED NOTE SYNC ---')
