from __future__ import annotations

import glob
import os.path
import pickle
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import List

from caldav import Calendar
from markdownify import markdownify as md
import markdown2

from Model import LinkedFolder
from Model.LinkedCalendar import LinkedCalendar


class Util:
    @staticmethod
    def get_apple_datetime(date_string: str) -> datetime | bool:
        try:
            result = datetime.strptime(date_string, "%A, %d %B %Y at %H:%M:%S")
            return result
        except ValueError:
            return False

    @staticmethod
    def get_caldav_date(date_string: str) -> datetime | bool:
        try:
            result = datetime.strptime(date_string, "%Y%m%d")
            return result
        except ValueError:
            return False

    @staticmethod
    def get_caldav_datetime(date_string: str) -> datetime | bool:
        try:
            result = datetime.strptime(date_string, "%Y%m%dT%H%M%S")
            return result
        except ValueError:
            return False

    @staticmethod
    def get_apple_datetime_string(date_obj: datetime) -> str | bool:
        try:
            result = date_obj.strftime("%A, %d %B %Y at %H:%M:%S")
            return result
        except ValueError:
            return False

    @staticmethod
    def get_caldav_date_string(date_obj: datetime) -> str | bool:
        try:
            result = date_obj.strftime("%Y%m%d")
            return result
        except ValueError:
            return False

    @staticmethod
    def get_caldav_datetime_string(date_obj: datetime) -> str | bool:
        try:
            result = date_obj.strftime("%Y%m%dT%H%M%S")
            return result
        except ValueError:
            return False

    @staticmethod
    def get_local_uuids(local_list: List) -> List[str]:
        return [o.id for o in local_list]

    # noinspection PyUnresolvedReferences
    @staticmethod
    def get_caldav_uuids(caldav_cal: Calendar) -> List[str]:
        return [o.icalendar_component["uid"] for o in caldav_cal.todos()]

    @staticmethod
    def export_uuids(folder: str, filename: str, uuids: List[str]) -> bool:
        if not os.path.exists('../uuid_db/' + folder):
            Path('../uuid_db/' + folder).mkdir(parents=True, exist_ok=True)
        with open('../uuid_db/' + folder + '/' + filename + '.dat', 'wb') as fp:
            pickle.dump(uuids, fp)
        return True

    @staticmethod
    def import_uuids(folder: str, filename: str) -> List | bool:
        file_path = '../uuid_db/' + folder + '/' + filename + '.dat'
        if not os.path.exists(file_path):
            return False

        with open(file_path, 'rb') as fp:
            uuid_list = pickle.load(fp)
        return uuid_list

    @staticmethod
    def reset_uuid_dbs() -> None:
        files = glob.glob('../uuid_db/caldav/*')
        for f in files:
            os.remove(f)
        files = glob.glob('../uuid_db/local/*')
        for f in files:
            os.remove(f)

    @staticmethod
    def delete_uuid_db(filename: str) -> int:
        deletions = 0
        local_file_name = '../uuid_db/local/' + filename + '.dat'
        caldav_file_name = '../uuid_db/caldav/' + filename + '.dat'
        if os.path.exists(local_file_name):
            os.remove(local_file_name)
            deletions += 1
        if os.path.exists(caldav_file_name):
            os.remove(caldav_file_name)
            deletions += 1

        return deletions

    @staticmethod
    def delete_folder_db_item(folder_name: str) -> bool:
        with open('../folder_db/folders.dat', 'rb') as fp:
            folder_db: List[LinkedFolder] = pickle.load(fp)
            fp.close()
        prev_len = len(folder_db)
        new_db = [f for f in folder_db if f.local_folder.name != folder_name]
        with open('../folder_db/folders.dat', 'wb') as fp:
            pickle.dump(new_db, fp)
            fp.close()
        return len(new_db) < prev_len

    @staticmethod
    def export_list_db(lists: List[LinkedCalendar]) -> bool:
        if not os.path.exists('../list_db'):
            Path('../list_db/').mkdir(parents=True, exist_ok=True)
        with open('../list_db/lists.dat', 'wb') as fp:
            pickle.dump(lists, fp)
        return True

    @staticmethod
    def import_list_db() -> List[LinkedCalendar] | bool:
        file_path = '../list_db/lists.dat'
        if not os.path.exists(file_path):
            return False

        with open(file_path, 'rb') as fp:
            lists = pickle.load(fp)
        return lists

    @staticmethod
    def export_folder_db(folders: List[LinkedFolder]) -> bool:
        if not os.path.exists('../folder_db'):
            Path('../folder_db/').mkdir(parents=True, exist_ok=True)
        with open('../folder_db/folders.dat', 'wb') as fp:
            pickle.dump(folders, fp)
        return True

    @staticmethod
    def import_folder_db() -> List[LinkedFolder] | bool:
        file_path = '../folder_db/folders.dat'
        if not os.path.exists(file_path):
            return False

        with open(file_path, 'rb') as fp:
            folders = pickle.load(fp)
        return folders

    @staticmethod
    def export_note_list(container: str, folder: str, notes: List[str]) -> bool:
        if not os.path.exists('../note_db/' + container):
            Path('../note_db/' + container).mkdir(parents=True, exist_ok=True)
        with open('../note_db/' + container + '/' + folder + '.dat', 'wb') as fp:
            pickle.dump(notes, fp)
        return True

    @staticmethod
    def import_note_list(container: str, folder: str) -> List[str] | bool:
        file_path = '../note_db/' + container + '/' + folder + '.dat'
        if not os.path.exists(file_path):
            return False

        with open(file_path, 'rb') as fp:
            notes = pickle.load(fp)
        return notes

    @staticmethod
    def html_to_markdown(html: str) -> str:
        return md(html.replace('<ul', '<br><ul'),
                  heading_style='ATX')

    @staticmethod
    def markdown_to_html(text):
        html = markdown2.markdown(text, extras={
            'breaks': {'on_newline': True, 'on_backslash': True},
            'cuddled-lists': None
        })
        build = ''
        for line in html.split('\n'):
            build += '<br>' if re.match(r'^\s*$', line) else line
            build += '\n'
        return build

    @staticmethod
    def copy_images_to_remote(staged, remote_folder, image_list):
        local_path = staged + '/.attachments'
        remote_path = remote_folder + '/.attachments/'
        if not os.path.exists(remote_path):
            Path(remote_path).mkdir(parents=True, exist_ok=True)
        for image in image_list:
            try:
                shutil.copy2(local_path + '/' + image['random'], remote_path)
            except FileNotFoundError as e:
                print('Warning, could not find source attachment to copy')
                print(e)

    @staticmethod
    def delete_remote_attachments(remote_note: Path) -> None:
        with open(remote_note) as fp:
            note_content = fp.read()
            fp.close()
        attachments = re.findall(r'!\[.*?]\(\.attachments/(.*?)\)', note_content)
        if len(attachments) > 0:
            remote_folder = os.path.join(os.path.dirname(remote_note), '.attachments')
            for attachment in attachments:
                attachment_filename = Path(os.path.join(remote_folder, attachment))
                os.remove(attachment_filename)
