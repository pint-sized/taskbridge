"""
Contains the ``ReminderContainer`` class, which represents a container for reminders. This is analogous to a *list* of
local reminders, or a *calendar* of remote *VTODO* tasks.
Many of the synchronisation methods are here.
"""

from __future__ import annotations

import copy
import glob
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import List

import caldav
from caldav import Calendar
from caldav.lib import error

import taskbridge.reminders.model.reminder as model
from taskbridge import helpers
from taskbridge.reminders.model import reminderscript


class ReminderContainer:
    """
    Represents a folder or calendar containing reminders. A link is established here between the local list and the remote
    calendar.
    Also contains a list of the reminders in this container, both local and remote.
    """

    #: List of all found reminder containers
    CONTAINER_LIST: List[ReminderContainer] = []

    def __init__(self, local_list: LocalList, remote_calendar: RemoteCalendar, sync: bool):
        """
        Create a new reminder container.

        :param local_list: the local list containing the local reminders.
        :param remote_calendar: the remote calendar containing the remote tasks.
        :param sync: True if the local list and remote calendar should be synchronised.
        """
        self.local_list: LocalList = local_list
        self.remote_calendar: RemoteCalendar = remote_calendar
        self.sync: bool = sync
        self.local_reminders: List[model.Reminder] = []
        self.remote_reminders: List[model.Reminder] = []
        ReminderContainer.CONTAINER_LIST.append(self)

    @staticmethod
    def load_caldav_calendars() -> tuple[bool, str] | tuple[bool, List[RemoteCalendar]]:
        """
        Loads the list of CalDav calendars which support *VTODO* components (i.e. task calendars).

        :returns:

            -success (:py:class:`bool`) - true if the list of remote calendars is successfully loaded.

            -data (:py:class:`str` | :py:class`List[RemoteCalendar]`) - error message on failure or list of remote calendars.

        """
        remote_calendars = []
        calendars = helpers.CALDAV_PRINCIPAL.calendars()
        for c in calendars:
            acceptable_component_types = c.get_supported_components()
            if "VTODO" in acceptable_component_types:
                remote_calendar = RemoteCalendar(c)
                remote_calendars.append(remote_calendar)

        if len(remote_calendars) > 0:
            return True, remote_calendars

        return False, "Unable to load CalDav calendars."

    @staticmethod
    def load_local_lists() -> tuple[bool, str] | tuple[bool, List[LocalList]]:
        """
        Load the list of local reminder lists.

        :returns:

            -success (:py:class:`bool`) - true if the list of local reminder lists is successfully loaded.

            -data (:py:class:`str` | :py:class`List[LocalList]`) - error message on failure or list of local reminder lists.

        """
        get_reminder_lists_script = reminderscript.get_reminder_lists_script
        return_code, stdout, stderr = helpers.run_applescript(get_reminder_lists_script)

        local_lists = []
        if return_code == 0:
            for r_list in stdout.split('|'):
                data = r_list.split(':')
                local_list = LocalList(data[1].strip(), data[0].strip())
                local_lists.append(local_list)
            return True, local_lists

        return False, "Unable to load local reminder lists."

    @staticmethod
    def count_local_completed() -> tuple[bool, str] | tuple[bool, int]:
        """
        Counts the number of completed reminders.

        :returns:

            -success (:py:class:`bool`) - true if the number of completed reminders is successfully retrieved

            -data (:py:class:`str` | :py:class`int`) - error message or number of completed reminders.

        """
        count_completed_script = reminderscript.count_completed_script
        return_code, stdout, stderr = helpers.run_applescript(count_completed_script)

        if return_code == 0:
            return True, int(stdout.strip())

        return False, "Unable to count completed reminders {}".format(stderr)

    @staticmethod
    def delete_local_completed() -> tuple[bool, str]:
        """
        Deletes completed reminders. This is important, as too many reminders can cause synchronisation to be very slow.

        :returns:

            -success (:py:class:`bool`) - true if completed reminders are successfully deleted

            -data (:py:class:`str`) - error message or fail, or success message.

        """
        delete_completed_script = reminderscript.delete_completed_script
        return_code, stdout, stderr = helpers.run_applescript(delete_completed_script)

        if return_code == 0:
            return True, "Completed reminders deleted"

        return False, "Unable to delete completed reminders: {}".format(stderr)

    @staticmethod
    def create_linked_containers(local_lists: List[LocalList], remote_calendars: List[RemoteCalendar],
                                 to_sync: List[str]) -> tuple[bool, str] | tuple[bool, List[ReminderContainer]]:
        """
        Creates an association between local reminder lists and remote task calendars. Missing containers are created;
        for example, if the list *foo* is present locally, and ``sync`` is set to True, this method will check if the
        remote calendar *foo* exists and, if not, creates it.

        The list of containers is saved to an SQLite database.

        **Important: The local list 'Reminders' is ALWAYS associated with the remote calendar 'Tasks'.**

        :param local_lists: list of local reminder lists.
        :param remote_calendars: list of remote task calendars.
        :param to_sync: list of reminder/task lists/calendars to synchronise. Sync is always bidirectional.

        :returns:

            -success (:py:class:`bool`) - true if the containers are successfully linked.

            -data (:py:class:`str` | :py:class`List[ReminderContainer]`) - error message on list of containers.

        """

        # Associate local lists with remote calendars
        for local_list in local_lists:
            should_sync = local_list.name in to_sync
            remote_name = "Tasks" if local_list.name == "Reminders" else local_list.name
            remote_calendar = next((rc for rc in remote_calendars if rc.name == remote_name), None)
            if remote_calendar is None:
                remote_calendar = RemoteCalendar(calendar_name=remote_name)
                if should_sync:
                    if helpers.confirm('Create remote calendar {}'.format(remote_name)):
                        remote_calendar = RemoteCalendar(calendar_name=remote_name)
                        success, data = remote_calendar.create()
                        if not success:
                            return False, data
            ReminderContainer(local_list, remote_calendar, should_sync)

        # Associate remote calendars with local lists
        for remote_calendar in remote_calendars:
            synced_remote_calendars = [cont.remote_calendar for cont in ReminderContainer.CONTAINER_LIST]
            if remote_calendar.name in [rc.name for rc in synced_remote_calendars]:
                continue

            should_sync = remote_calendar.name in to_sync
            local_name = "Reminders" if remote_calendar.name == "Tasks" else remote_calendar.name
            local_list = next((ll for ll in local_lists if ll.name == local_name), None)
            if local_list is None:
                local_list = LocalList(list_name=local_name)
                if should_sync:
                    if helpers.confirm('Create local list {}'.format(local_name)):
                        local_list = LocalList(list_name=local_name)
                        success, data = local_list.create()
                        if not success:
                            return False, data
            ReminderContainer(local_list, remote_calendar, should_sync)

        ReminderContainer.persist_containers()
        return True, "Associations completed"

    @staticmethod
    def seed_container_table() -> tuple[bool, str]:
        """
        Creates the initial structure for the table storing containers in SQLite.

        :returns:

            -success (:py:class:`bool`) - true if the table is successfully seeded.

            -data (:py:class:`str`) - error message on failure or success message.

        """
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_create_container_table = """CREATE TABLE IF NOT EXISTS tb_container (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT, 
                                        local_name TEXT,
                                        remote_name TEXT,
                                        sync INT
                                        );"""
                    cursor.execute(sql_create_container_table)
        except sqlite3.OperationalError as e:
            return False, repr(e)
        return True, 'tb_container table created'

    @staticmethod
    def persist_containers() -> tuple[bool, str]:
        """
        Save the list of containers to SQLite.

        :returns:

            -success (:py:class:`bool`) - true if the containers are successfully saved.

            -data (:py:class:`str`) - error message on failure or success message.

        """
        containers = []
        for container in ReminderContainer.CONTAINER_LIST:
            containers.append((
                container.local_list.name,
                container.remote_calendar.name,
                1 if container.sync else 0
            ))

        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_delete_containers = "DELETE FROM tb_container"
                    cursor.execute(sql_delete_containers)
                    sql_insert_containers = "INSERT INTO tb_container(local_name, remote_name, sync) VALUES (?, ?, ?)"
                    cursor.executemany(sql_insert_containers, containers)
                    connection.commit()
        except sqlite3.OperationalError as e:
            return False, repr(e)
        return True, 'Containers stored tb_container'

    @staticmethod
    def seed_reminder_table() -> tuple[bool, str]:
        """
        Creates the initial structure for the table storing reminders in SQLite.

        :returns:

            -success (:py:class:`bool`) - true if the table is successfully seeded.

            -data (:py:class:`str`) - error message on failure or success message.

        """
        try:
            con = sqlite3.connect(helpers.db_folder())
            cur = con.cursor()
            sql_create_reminder_table = """CREATE TABLE IF NOT EXISTS tb_reminder (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        local_uuid TEXT,
                        local_name TEXT,
                        remote_uuid TEXT,
                        remote_name TEXT,
                        local_container TEXT,
                        remote_container TEXT
                        );"""
            cur.execute(sql_create_reminder_table)
        except sqlite3.OperationalError as e:
            return False, repr(e)
        return True, 'tb_reminder table created'

    @staticmethod
    def persist_reminders() -> tuple[bool, str]:
        """
        Save the list of reminders to SQLite.
        Due to the fact that local reminder UUIDs are read-only, this list may contain reminders without an associated
        remote UID. For this reason, the reminder's summary (which is typically the only text content) has to be saved to
        the database. Without this, many reminders couldn't be matched. The database is stored locally.

        :returns:

            -success (:py:class:`bool`) - true if the reminders as successfully saved.

            -data (:py:class:`str`) - error message on failure or success message.

        """
        reminders = []
        for container in ReminderContainer.CONTAINER_LIST:
            for reminder in container.local_reminders:
                reminders.append((
                    reminder.uuid,
                    reminder.name,
                    '',
                    '',
                    container.local_list.name,
                    ''
                ))

            for reminder in container.remote_reminders:
                reminders.append((
                    '',
                    '',
                    reminder.uuid,
                    reminder.name,
                    '',
                    container.remote_calendar.name
                ))

        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_delete_reminders = "DELETE FROM tb_reminder"
                    cursor.execute(sql_delete_reminders)
                    sql_insert_containers = """
                    INSERT INTO tb_reminder(local_uuid, local_name, remote_uuid, remote_name, local_container, remote_container) 
                    VALUES (?, ?, ?, ?, ?, ?)"""
                    cursor.executemany(sql_insert_containers, reminders)
                    connection.commit()
        except sqlite3.OperationalError as e:
            return False, repr(e)
        return True, 'Reminders stored in tb_reminder'

    @staticmethod
    def sync_container_deletions(discovered_local: List[LocalList], discovered_remote: List[RemoteCalendar],
                                 to_sync: List[str]) -> tuple[bool, str] | tuple[bool, dict]:
        """
        Synchronises deletions to reminder containers.

        The list of containers found during the last sync is loaded from SQLite and compared to the local and remote
        lists found now. Any lists in the database which are no longer present will have their counterpart deleted. For
        example, if the local list *foo* is deleted, the remote calendar *foo* will be deleted during sync.

        Note that container deletions only apply if the list/calendar is found in the ``to_sync`` argument.

        On success, this method returns a dictionary with changes, containing the following keys:

        - ``updated_local_list`` - the list of local reminder lists, taking into account deleted lists.
        - ``updated_remote_list`` - the list of remote task calendars, taking into account deleted calendars.

        :param discovered_local: the list of local reminder lists.
        :param discovered_remote: the list of remote task calendars.
        :param to_sync: the list of lists/calendars which should be synchronised.

        :returns:

            -success (:py:class:`bool`) - true if container deletions are successfully synchronised.

            -data (:py:class:`str` | :py:class:`dict`) - error message on failure or result as above on success.

        """
        success, message = ReminderContainer.seed_container_table()
        if not success:
            return False, message

        result = {
            'updated_local_list': discovered_local,
            'updated_remote_list': discovered_remote
        }

        # Sync local deletions to remote
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_get_containers = "SELECT * FROM tb_container WHERE sync = ?"
                    saved_containers = cursor.execute(sql_get_containers, '1').fetchall()
        except sqlite3.OperationalError as e:
            return False, 'Error retrieving containers from table: {}'.format(e)

        if not len(saved_containers) > 0:
            return True, result

        current_local_containers = [ll.name for ll in discovered_local]
        removed_local_containers = [ll for ll in saved_containers if ll['local_name'] not in current_local_containers]
        for local in removed_local_containers:
            if local['local_name'] in to_sync:
                # Local container has been deleted, so delete remote
                if helpers.confirm('Delete remote container {}'.format(local['local_name'])):
                    remote_name = "Tasks" if local['local_name'] == "Reminders" else local['local_name']
                    success, data = RemoteCalendar(calendar_name=remote_name).delete()
                    if not success:
                        return False, data
                    discovered_remote = [dc for dc in discovered_remote if dc.name != remote_name]
                    result['updated_remote_list'] = discovered_remote

        current_remote_containers = [rc.name for rc in discovered_remote]
        removed_remote_containers = [rc for rc in saved_containers if
                                     rc['remote_name'] not in current_remote_containers]
        for remote in removed_remote_containers:
            if remote['remote_name'] in to_sync and remote['remote_name'] not in [rl['remote_name'] for rl in
                                                                                  removed_local_containers]:
                # Remote container has been deleted, so delete local
                if helpers.confirm('Delete local container {}'.format(remote['remote_name'])):
                    local_name = "Reminders" if remote['remote_name'] == "Tasks" else remote['remote_name']
                    success, data = LocalList(list_name=local_name).delete()
                    if not success:
                        return False, data
                    discovered_local = [dc for dc in discovered_local if dc.name != local_name]
                    result['updated_local_list'] = discovered_local

        # Empty table
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    cursor.execute("DELETE FROM tb_container")
        except sqlite3.OperationalError as e:
            return False, 'Error deleting container table: {}'.format(e)

        return True, result

    @staticmethod
    def sync_reminder_deletions() -> tuple[bool, str] | tuple[bool, dict]:
        """
        Synchronises deletions to reminders.

        The list of reminders found during the last sync is loaded from SQLite and compared to the local and remote reminders
        found now. Any reminders in the database which are no longer present will have their counterpart deleted. For
        example, if the local reminder *foo* is deleted, the remote reminder *foo* will be deleted during sync.

        Note that reminder deletion only applies to those containers with ``sync`` set to True.

        On success, this method returns a dictionary with changes, containing the following keys:

        - ``deleted_local_reminders`` - a list of local reminders deleted as :py:class:`List[Reminder]`.
        - ``deleted_remote_reminders`` - a list of remote tasks deleted as :py:class:`List[Reminder]`.

        A reminder not being found is not considered an error, as the user may have deleted the reminder manually prior
        to the sync running.

        :returns:

            -success (:py:class:`bool`) - true if reminder deletions are successfully synchronised.

            -data (:py:class:`str` | :py:class:`dict`) - error message on failure or result as above on success.

        """
        success, message = ReminderContainer.seed_reminder_table()
        if not success:
            return False, message

        for container in ReminderContainer.CONTAINER_LIST:
            success, data = container.load_local_reminders()
            if not success:
                return False, 'Failed to load local reminders: {}'.format(data)
            success, data = container.load_remote_reminders()
            if not success:
                return False, 'Failed to load remote reminders: {}'.format(data)

        result = {
            'deleted_local_reminders': [],
            'deleted_remote_reminders': []
        }

        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_get_reminders = "SELECT * FROM tb_reminder"
                    saved_reminders = cursor.execute(sql_get_reminders).fetchall()
        except sqlite3.OperationalError as e:
            return False, 'Error retrieving reminders from table: {}'.format(e)

        if not len(saved_reminders) > 0:
            return True, result

        for container in ReminderContainer.CONTAINER_LIST:
            container_saved_local = [r for r in saved_reminders if r['local_container'] == container.local_list.name]
            container_saved_remote = [r for r in saved_reminders if
                                      r['remote_container'] == container.remote_calendar.name]

            # Reminders deleted locally need to be deleted from CalDav
            local_deleted = [r for r in container_saved_local if
                             r['local_name'] not in [lr.name for lr in container.local_reminders]]
            for deleted in local_deleted:
                remote_reminder = next((r for r in container.remote_reminders
                                        if r.uuid == deleted['local_uuid'] or r.name == deleted['local_name']), None)
                if remote_reminder is not None:
                    if helpers.confirm("Delete remote reminder {}".format(remote_reminder.name)):
                        to_delete = container.remote_calendar.cal_obj.search(todo=True, uid=remote_reminder.uuid)
                        if len(to_delete) > 0:
                            to_delete[0].delete()
                            container.remote_reminders.remove(remote_reminder)
                            result['deleted_remote_reminders'].append(remote_reminder)
                        else:
                            return False, 'Failed to delete remote reminder {0} ({1})'.format(remote_reminder.uuid, remote_reminder.name)

            # Reminders deleted remotely need to be deleted from local
            remote_deleted = [r for r in container_saved_remote if
                              r['remote_name'] not in [rr.name for rr in container.remote_reminders]]
            for deleted in remote_deleted:
                local_reminder = next((r for r in container.local_reminders
                                       if r.uuid == deleted['remote_uuid'] or r.name == deleted['remote_name']), None)
                if local_reminder is not None:
                    if helpers.confirm("Delete local reminder {}".format(local_reminder.name)):
                        delete_reminder_script = reminderscript.delete_reminder_script
                        return_code, stdout, stderr = helpers.run_applescript(delete_reminder_script, local_reminder.uuid)
                        if return_code != 0:
                            return False, 'Failed to delete local reminder {0} ({1})'.format(local_reminder.uuid, local_reminder.name)
                        container.local_reminders.remove(local_reminder)
                        result['deleted_local_reminders'].append(local_reminder)

        # Empty table
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    cursor.execute("DELETE FROM tb_reminder")
        except sqlite3.OperationalError as e:
            return False, 'Error deleting reminder table: {}'.format(e)

        return True, result

    def load_local_reminders(self) -> tuple[bool, str] | tuple[bool, int]:
        """
        Load the list of local reminders in this local container (list) via an AppleScript script.
        The reminders are saved in a pipe-separated *.psv* file in a temporary folder, and then parsed from there.

        :returns:

            -success (:py:class:`bool`) - true if the reminders are successfully loaded.

            -data (:py:class:`str` | :py:class:`int`) - error message on failure or number of loaded reminders on success.

        """
        get_reminders_in_list_script = reminderscript.get_reminders_in_list_script
        return_code, stdout, stderr = helpers.run_applescript(get_reminders_in_list_script, self.local_list.name)

        if return_code != 0:
            return False, stderr

        export_path = Path(stdout.strip()) / (self.local_list.name + '.psv')
        try:
            with open(export_path, 'r') as fp:
                file_data = fp.read()
                fp.close()
        except FileNotFoundError as e:
            return False, 'Could not open exported reminder file {0}: {1}'.format(export_path, e)
        for local_reminder in file_data.split('\n'):
            values = local_reminder.split('|')
            if len(values) > 0 and values[0] != '':
                self.local_reminders.append(model.Reminder.create_from_local(values))

        psv_files = glob.glob(stdout.strip() + '/*.psv')
        for psv in psv_files:
            os.remove(psv)

        return True, len(self.local_reminders)

    def load_remote_reminders(self) -> tuple[bool, str] | tuple[bool, int]:
        """
        Load the list of remote reminders (tasks) in this remote container (calendar) via CalDav.

        :returns:

            -success (:py:class:`bool`) - true if the reminders are successfully loaded.

            -data (:py:class:`str` | :py:class:`int`) - error message on failure or number of loaded reminders on success.

        """
        caldav_tasks = self.remote_calendar.cal_obj.todos()
        for task in caldav_tasks:
            self.remote_reminders.append(model.Reminder.create_from_remote(task))

        return True, len(self.remote_reminders)

    def sync_reminders(self) -> tuple[bool, str] | tuple[bool, dict]:
        """
        Synchronises reminders. This method only synchronises reminders for containers with ``sync`` set to True.
        On success, the method returns a dictionary with the following keys:

        - ``remote_added`` - name of reminders added to the remote calendar as :py:class:`List[str]`.
        - ``remote_updated`` - name of reminders updated in the remote calendar as :py:class:`List[str]`.
        - ``local_added`` - name of reminders added to the local list as :py:class:`List[str]`.
        - ``local_updated`` - name of reminders updated in the local list as :py:class:`List[str]`.

        Any of the above may be empty if no changes were made.

        :returns:

            -success (:py:class:`bool`) - true if the reminders are successfully synchronised.

            -data (:py:class:`str` | :py:class:`dict`) - error message on failure or :py:class:`dict` with results as above.

        """

        if not self.sync:
            return True, 'Container {} is set to NO SYNC so skipped'.format(self.local_list.name)

        result = {
            'remote_added': [],
            'remote_updated': [],
            'local_added': [],
            'local_updated': []
        }

        # Sync local reminders to remote
        for local_reminder in self.local_reminders:
            # Get the associated remote reminder, if any
            remote_reminder = next((r for r in self.remote_reminders
                                    if r.uuid == local_reminder.uuid or r.name == local_reminder.name), None)
            if remote_reminder is None or local_reminder.modified_date > remote_reminder.modified_date:
                key = 'remote_added' if remote_reminder is None else 'remote_updated'
                remote_reminder = copy.deepcopy(local_reminder)
                if helpers.confirm("Upsert remote reminder {}".format(remote_reminder.name)):
                    success, data = remote_reminder.upsert_remote(self)
                    if not success:
                        return False, data
                    result[key].append(remote_reminder.name)
            elif local_reminder.modified_date < remote_reminder.modified_date:
                key = 'local_updated'
                local_reminder = copy.deepcopy(remote_reminder)
                if helpers.confirm("Update local reminder {}".format(local_reminder.name)):
                    success, data = local_reminder.upsert_local(self)
                    if not success:
                        return False, data
                    else:
                        u_success, u_data = remote_reminder.update_uuid(self, data)
                        if not u_success:
                            return False, u_data
                    result[key].append(local_reminder.name)

        # Sync remote reminders to local
        for remote_reminder in self.remote_reminders:
            # Get the associated local reminder, if any
            local_reminder = next((r for r in self.local_reminders
                                   if r.uuid == remote_reminder.uuid or r.name == remote_reminder.name), None)
            if local_reminder is None:
                key = 'local_added'
                local_reminder = copy.deepcopy(remote_reminder)
                if helpers.confirm("Add local reminder {}".format(local_reminder.name)):
                    success, data = local_reminder.upsert_local(self)
                    if not success:
                        return False, data
                    else:
                        u_success, u_data = remote_reminder.update_uuid(self, data)
                        if not u_success:
                            return False, u_data
                    result[key].append(local_reminder.name)

        return True, result

    def __str__(self):
        return "<Local: {local}, Remote: {remote}, Sync: {sync}>".format(
            local=self.local_list.name,
            remote=self.remote_calendar.name,
            sync=self.sync
        )

    def __repr__(self):
        return "<Local: {local}, Remote: {remote}, Sync: {sync}>".format(
            local=self.local_list.name,
            remote=self.remote_calendar.name,
            sync=self.sync
        )


class RemoteCalendar:
    """
    Represents a remote CalDav calendar supporting *VTODO* components.
    """

    def __init__(self, cal_obj: Calendar | None = None, calendar_name: str | None = None):
        """
        Create a new remote calendar instance. The calendar is not actually created until the ``create()`` method is called.

        :param cal_obj: for existing remote calendars, the calendar object.
        :param calendar_name: for new calendars, the name of the calendar to create.
        """

        if cal_obj is not None:
            self.id: str | None = cal_obj.id
            self.name: str | None = cal_obj.name
            self.cal_obj: Calendar = cal_obj
        else:
            self.name: str = calendar_name

    def create(self) -> tuple[bool, str]:
        """
        Creates this calendar using CalDav.

        :returns:

            -success (:py:class:`bool`) - true if the calendar is successfully created.

            -data (:py:class:`str`) - error message on failure or success message.

        """
        cal_obj = helpers.CALDAV_PRINCIPAL.make_calendar(self.name)
        if isinstance(cal_obj, caldav.Calendar):
            self.id = cal_obj.id
            self.cal_obj = cal_obj
            return True, "Created remote calendar {}".format(self.name)
        return False, "Failed to create remote calendar {}".format(self.name)

    def delete(self) -> tuple[bool, str]:
        """
        Delete the remote calendar with this object's name using CalDav.

        :returns:

            -success (:py:class:`bool`) - true if the calendar is successfully deleted.

            -data (:py:class:`str`) - error message on failure or success message.

        """
        cal = helpers.CALDAV_PRINCIPAL.calendar(name=self.name)
        try:
            cal.delete()
        except error.DeleteError as e:
            return False, 'Failed to delete remote calendar {0}: {1}'.format(self.name, e)
        return True, 'Remote calendar {} deleted'.format(self.name)

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name


class LocalList:
    """
    Represents a local folder storing reminders.
    """
    def __init__(self, list_name: str, list_id: str | None = None):
        """
        Create a new local list instance. The list is not actually created until the ``create()`` method is called.

        :param list_name: the name of the list to create.
        :param list_id: for existing lists, their UUID.
        """
        self.id: str = list_id
        self.name: str = list_name

    def create(self) -> tuple[bool, str]:
        """
        Creates the local list using AppleScript.

        :returns:

            -success (:py:class:`bool`) - true if the reminder list is successfully created.

            -data (:py:class:`str`) - error message on failure or success message.

        """
        create_reminder_list_script = reminderscript.create_reminder_list_script
        return_code, stdout, stderr = helpers.run_applescript(create_reminder_list_script, self.name)
        if return_code == 0:
            self.id = stdout
            return True, "Created local list {}".format(self.name)
        return False, "Failed to create local list {}".format(self.name)

    def delete(self) -> tuple[bool, str]:
        """
        Delete the local list with this object's name.

        :returns:

            -success (:py:class:`bool`) - true if the reminder list is successfully deleted.

            -data (:py:class:`str`) - error message on failure or success message.

        """
        delete_list_script = reminderscript.delete_list_script
        return_code, stdout, stderr = helpers.run_applescript(delete_list_script, self.name)
        if return_code == 0:
            return True, "Local list {} deleted".format(self.name)
        return False, "Failed to delete local list {0}: {1}".format(self.name, stderr)

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name