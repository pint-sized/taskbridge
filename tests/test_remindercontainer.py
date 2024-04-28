import datetime
import os
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import caldav
import pytest
import keyring
from caldav.lib.error import AuthorizationError
from decouple import config

import taskbridge.helpers as helpers
from taskbridge.reminders.model import reminderscript
from taskbridge.reminders.model.remindercontainer import ReminderContainer, LocalList, RemoteCalendar
from taskbridge.reminders.model.reminder import Reminder
from taskbridge.reminders.controller import ReminderController

TEST_ENV = config('TEST_ENV', default='remote')


class TestReminderContainer:
    CALDAV_CONNECTED: bool = False

    @staticmethod
    def __connect_caldav(fail: bool = False):
        if TestReminderContainer.CALDAV_CONNECTED and not fail:
            TestReminderContainer.CALDAV_CONNECTED = False
            return

        conf_file = helpers.settings_folder() / 'conf.json'
        if not os.path.exists(conf_file):
            assert False, "Failed to load configuration file."
        with open(helpers.settings_folder() / 'conf.json', 'r') as fp:
            settings = json.load(fp)

        ReminderController.CALDAV_USERNAME = settings['caldav_username']
        ReminderController.CALDAV_URL = settings['caldav_url']
        ReminderController.CALDAV_HEADERS = {}
        ReminderController.CALDAV_PASSWORD = keyring.get_password("TaskBridge", "CALDAV-PWD") \
            if not fail else 'bogus'
        ReminderController.TO_SYNC = settings['reminder_sync']
        ReminderController.connect_caldav()
        TestReminderContainer.CALDAV_CONNECTED = True

    @staticmethod
    def __create_reminder_from_local() -> Reminder:
        uuid = "x-apple-id://1234-5678-9012"
        name = "Test reminder"
        created_date = "Thursday, 18 April 2024 at 08:00:00"
        completed = 'false'
        due_date = "Thursday, 18 April 2024 at 18:00:00"
        all_day = 'false'
        remind_me_date = "Thursday, 18 April 2024 at 18:00:00"
        modified_date = "Thursday, 18 April 2024 at 17:50:00"
        completion = 'missing value'
        body = "Test reminder body."

        values = [uuid, name, created_date, completed, due_date, all_day, remind_me_date, modified_date, completion, body]
        reminder = Reminder.create_from_local(values)
        return reminder

    # noinspection SpellCheckingInspection
    @staticmethod
    def __create_reminder_from_remote() -> Reminder:
        obj = caldav.CalendarObjectResource()
        # noinspection PyUnresolvedReferences
        obj._set_data("""BEGIN:VCALENDAR
    VERSION:2.0
    PRODID:-//Nextcloud Tasks v0.15.0
    BEGIN:VTODO
    CREATED:20240418T084019
    DESCRIPTION:Test reminder body
    DTSTAMP:20240418T084042
    DUE:20240418T180000
    LAST-MODIFIED:20240418T084042
    SUMMARY:Test reminder
    UID:f4a682ac-86f2-4f81-a08e-ccbff061d7da
    END:VTODO
    END:VCALENDAR
    """)
        reminder = Reminder.create_from_remote(obj)
        return reminder

    @staticmethod
    def __get_sync_container() -> ReminderContainer:
        ReminderContainer.CONTAINER_LIST.clear()
        TestReminderContainer.__connect_caldav()

        # Fetch containers
        success, data = ReminderContainer.load_local_lists()
        if not success:
            assert False, 'Could not load local lists {}'.format(data)
        local_containers = data
        success, data = ReminderContainer.load_caldav_calendars()
        if not success:
            assert False, 'Could not load remote calendars {}'.format(data)
        remote_containers = data

        # Associate containers and find the Sync container
        ReminderContainer.create_linked_containers(local_containers, remote_containers, ['Sync'])
        sync_container = next((c for c in ReminderContainer.CONTAINER_LIST if c.local_list.name == "Sync"))
        return sync_container

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires CalDAV credentials")
    def test_load_caldav_calendars(self):
        TestReminderContainer.__connect_caldav()
        success, remote_calendars = ReminderContainer.load_caldav_calendars()
        assert success is True
        assert len(remote_calendars) > 0

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud")
    def test_load_local_lists(self):
        success, local_lists = ReminderContainer.load_local_lists()
        assert success is True
        assert len(local_lists) > 0

        # Fail to load local lists
        success, local_lists = ReminderContainer.load_local_lists(True)
        assert success is False

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud")
    def test_count_local_completed(self):
        success, data = ReminderContainer.count_local_completed()
        assert success is True
        assert isinstance(data, int)

        # Fail to count
        success, data = ReminderContainer.count_local_completed(True)
        assert success is False

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud")
    def test_delete_local_completed(self):
        success, data = ReminderContainer.delete_local_completed()
        assert success is True
        success, count = ReminderContainer.count_local_completed()
        assert count == 0

    def test_assoc_list_local_remote(self):
        mock_local = [LocalList("sync_me"), LocalList("do_not_sync_me")]
        mock_remote = [RemoteCalendar(calendar_name="sync_me"), RemoteCalendar(calendar_name="do_not_sync_me")]
        mock_sync = ['sync_me']
        success, data = ReminderContainer.assoc_list_local_remote(mock_local, mock_remote, mock_sync)
        assert success is True
        assoc_containers = ReminderContainer.CONTAINER_LIST

        synced_container = [c for c in assoc_containers if c.local_list.name == "sync_me"]
        assert len(synced_container) == 1
        assert synced_container[0].sync is True

        not_synced_container = [c for c in assoc_containers if c.local_list.name == "do_not_sync_me"]
        assert len(not_synced_container) == 1
        assert not_synced_container[0].sync is False

        # Clean up
        ReminderContainer.CONTAINER_LIST.clear()

    def test_assoc_list_remote_local(self):
        mock_local = [LocalList("sync_me"), LocalList("do_not_sync_me")]
        mock_remote = [RemoteCalendar(calendar_name="sync_me"), RemoteCalendar(calendar_name="do_not_sync_me")]
        mock_sync = ['sync_me']
        success, data = ReminderContainer.assoc_list_remote_local(mock_local, mock_remote, mock_sync)
        assert success is True
        assoc_containers = ReminderContainer.CONTAINER_LIST

        synced_container = [c for c in assoc_containers if c.local_list.name == "sync_me"]
        assert len(synced_container) == 1
        assert synced_container[0].sync is True

        not_synced_container = [c for c in assoc_containers if c.local_list.name == "do_not_sync_me"]
        assert len(not_synced_container) == 1
        assert not_synced_container[0].sync is False

        # Fail
        mock_local = [LocalList("sync_me"), LocalList("do_not_sync_me")]
        mock_remote = [RemoteCalendar(calendar_name="sync_me"), RemoteCalendar(calendar_name="do_not_sync_me")]
        mock_sync = ['sync_me']
        success, data = ReminderContainer.assoc_list_remote_local(mock_local, mock_remote, mock_sync, True)
        assert success is False

        # Clean up
        ReminderContainer.CONTAINER_LIST.clear()

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and CalDAV credentials")
    def test_create_linked_containers(self):
        helpers.DRY_RUN = False
        TestReminderContainer.__connect_caldav()
        mock_local = [LocalList("sync_me"),
                      LocalList("do_not_sync_me"),
                      LocalList("Reminders"),
                      LocalList("local_only")]
        mock_remote = [RemoteCalendar(calendar_name="sync_me"),
                       RemoteCalendar(calendar_name="do_not_sync_me"),
                       RemoteCalendar(calendar_name="Tasks"),
                       RemoteCalendar(calendar_name="remote_only")]
        mock_sync = ['sync_me', 'Reminders', 'local_only', 'remote_only']
        success, data = ReminderContainer.create_linked_containers(mock_local, mock_remote, mock_sync)

        assert success is True
        assoc_containers = ReminderContainer.CONTAINER_LIST

        synced_container = [c for c in assoc_containers if c.local_list.name == "sync_me"]
        assert len(synced_container) == 1
        assert synced_container[0].sync is True

        not_synced_container = [c for c in assoc_containers if c.local_list.name == "do_not_sync_me"]
        assert len(not_synced_container) == 1
        assert not_synced_container[0].sync is False

        # Tests Reminders <-> Tasks association
        reminders_tasks_container = [c for c in assoc_containers if
                                     c.local_list.name == "Reminders" and c.remote_calendar.name == "Tasks"]
        assert len(reminders_tasks_container) == 1
        assert reminders_tasks_container[0].sync is True

        # Test local list gets created
        success, local_lists = ReminderContainer.load_local_lists()
        remote_only = [lst for lst in local_lists if lst.name == "remote_only"]
        assert len(remote_only) == 1

        # Test remote calendar gets created
        success, remote_calendars = ReminderContainer.load_caldav_calendars()
        local_only = [cal for cal in remote_calendars if cal.name == "local_only"]
        assert len(local_only) == 1

        # Clean up
        ReminderContainer.CONTAINER_LIST.clear()
        RemoteCalendar(calendar_name='local_only').delete()
        delete_list_script = reminderscript.delete_list_script
        helpers.run_applescript(delete_list_script, 'remote_only')

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem.")
    def test_seed_container_table(self):
        ReminderContainer.seed_container_table()
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_table_exists = "SELECT name FROM sqlite_master WHERE type='table' AND name='tb_container';"
                    table_result = cursor.execute(sql_table_exists)

                    table_list = [t for t in table_result if t['name'] == "tb_container"]
                    assert len(table_list) == 1

                    sql_columns_exist = "PRAGMA table_info('tb_container');"
                    columns_result = cursor.execute(sql_columns_exist)

                    columns = ['id', 'local_name', 'remote_name', 'sync']
                    for col in columns_result:
                        assert col['name'] in columns
        except sqlite3.OperationalError as e:
            assert False, repr(e)

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem.")
    def test_persist_containers(self):
        ReminderContainer(LocalList("sync_me"), RemoteCalendar(calendar_name="sync_me"), True)
        ReminderContainer(LocalList("do_not_sync_me"), RemoteCalendar(calendar_name="do_not_sync_me"), False)
        ReminderContainer.persist_containers()

        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_get_containers = "SELECT * FROM tb_container;"
                    results = cursor.execute(sql_get_containers).fetchall()

                    assert len(results) == 2
                    for result in results:
                        if result['local_name'] == 'sync_me':
                            assert result['remote_name'] == 'sync_me'
                            assert result['sync'] == 1
                        elif result['local_name'] == 'do_not_sync_me':
                            assert result['remote_name'] == 'do_not_sync_me'
                            assert result['sync'] == 0
                        else:
                            assert False, 'Unrecognised record in tb_container'
        except sqlite3.OperationalError as e:
            assert False, repr(e)

        # Clean Up
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_delete_containers = "DELETE FROM tb_container"
                    cursor.execute(sql_delete_containers)
                    connection.commit()
        except sqlite3.OperationalError as e:
            print(e)

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem.")
    def test_seed_reminder_table(self):
        ReminderContainer.seed_reminder_table()
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_table_exists = "SELECT name FROM sqlite_master WHERE type='table' AND name='tb_reminder';"
                    table_result = cursor.execute(sql_table_exists)

                    table_list = [t for t in table_result if t['name'] == "tb_reminder"]
                    assert len(table_list) == 1

                    sql_columns_exist = "PRAGMA table_info('tb_reminder');"
                    columns_result = cursor.execute(sql_columns_exist)

                    columns = ['id', 'local_uuid', 'local_name', 'remote_uuid', 'remote_name', 'local_container',
                               'remote_container']
                    for col in columns_result:
                        assert col['name'] in columns
        except sqlite3.OperationalError as e:
            assert False, repr(e)

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires local filesystem.")
    def test_persist_reminders(self):
        container = ReminderContainer(LocalList("sync_me"), RemoteCalendar(calendar_name="sync_me"), True)
        local_reminder = Reminder("local_uuid", "local_name", None, datetime.datetime.now(),
                                  None, None, None, None, False)
        remote_reminder = Reminder("remote_uuid", "remote_name", None, datetime.datetime.now(),
                                   None, None, None, None, False)
        container.local_reminders.append(local_reminder)
        container.remote_reminders.append(remote_reminder)
        ReminderContainer.persist_reminders()

        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_get_containers = "SELECT * FROM tb_reminder;"
                    results = cursor.execute(sql_get_containers).fetchall()
                    assert len(results) >= 2

                    local_persisted = [r for r in results if r['local_name'] == 'local_name']
                    assert len(local_persisted) >= 1
                    local = local_persisted[0]
                    assert local['local_uuid'] == 'local_uuid'
                    assert local['local_container'] == 'sync_me'

                    remote_persisted = [r for r in results if r['remote_name'] == 'remote_name']
                    assert len(remote_persisted) >= 1
                    remote = remote_persisted[0]
                    assert remote['remote_uuid'] == 'remote_uuid'
                    assert remote['remote_container'] == 'sync_me'
        except sqlite3.OperationalError as e:
            assert False, repr(e)

        # Clean Up
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_delete_containers = "DELETE FROM tb_reminder"
                    cursor.execute(sql_delete_containers)
                    connection.commit()
        except sqlite3.OperationalError as e:
            print(e)

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires CalDAV credentials")
    def test__delete_remote_containers(self):
        helpers.DRY_RUN = False
        TestReminderContainer.__connect_caldav()

        # Create a remote container
        to_delete = RemoteCalendar(calendar_name='DELETE_ME')
        to_keep = RemoteCalendar(calendar_name='KEEP_ME')
        success, data = to_delete.create()
        if not success:
            assert False, 'Could not create remote container: {}'.format(data)
        success, data = to_keep.create()
        if not success:
            assert False, 'Could not create remote container: {}'.format(data)

        # Run the function
        removed_local_containers = [{'local_name': 'DELETE_ME'}]
        discovered_remote = [to_delete, to_keep]
        to_sync = ['DELETE_ME', 'KEEP_ME']
        result = {'updated_remote_list': []}
        # noinspection PyTypeChecker
        success, data = ReminderContainer._delete_remote_containers(removed_local_containers, discovered_remote, to_sync,
                                                                    result)

        # Check that the remote container has been deleted
        assert success is True, 'Could not delete remote container: {}'.format(data)
        success, data = ReminderContainer.load_caldav_calendars()
        assert success is True, 'Could not load remote calendars: {}'.format(data)
        remote_calendars = data
        keep_list = [c for c in remote_calendars if c.name == "KEEP_ME"]
        assert len(keep_list) > 0
        delete_list = [c for c in remote_calendars if c.name == "DELETE_ME"]
        assert len(delete_list) == 0

        # Check the results are properly updated
        deleted_calendar = next((c for c in result['updated_remote_list'] if c.name == 'DELETE_ME'), None)
        assert deleted_calendar is None

        # Clean Up
        ReminderContainer.CONTAINER_LIST.clear()
        RemoteCalendar(calendar_name='KEEP_ME').delete()

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud")
    def test__delete_local_containers(self):
        helpers.DRY_RUN = False

        # Create a local container
        to_delete = LocalList('DELETE_ME')
        to_keep = LocalList('KEEP_ME')
        success, data = to_delete.create()
        if not success:
            assert False, 'Could not create local container: {}'.format(data)
        success, data = to_keep.create()
        if not success:
            assert False, 'Could not create local container: {}'.format(data)

        # Run the function
        removed_remote_containers = [{'remote_name': 'DELETE_ME'}]
        removed_local_containers = []
        discovered_local = [to_delete, to_keep]
        to_sync = ['DELETE_ME', 'KEEP_ME']
        result = {'updated_local_list': []}
        # noinspection PyTypeChecker
        success, data = ReminderContainer._delete_local_containers(removed_remote_containers, removed_local_containers,
                                                                   discovered_local, to_sync, result)

        # Check that the local container has been deleted
        assert success is True, 'Could not delete local container: {}'.format(data)
        success, data = ReminderContainer.load_local_lists()
        assert success is True, 'Could not load local lists: {}'.format(data)
        local_lists = data
        keep_list = [lst for lst in local_lists if lst.name == 'KEEP_ME']
        assert len(keep_list) > 0
        delete_list = [lst for lst in local_lists if lst.name == 'DELETE_ME']
        assert len(delete_list) == 0

        # Check the results are properly updated
        deleted_list = next((lst for lst in result['updated_local_list'] if lst.name == 'DELETE_ME'), None)
        assert deleted_list is None

        # Clean Up
        delete_list_script = reminderscript.delete_list_script
        helpers.run_applescript(delete_list_script, 'KEEP_ME')

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and CalDAV credentials")
    def test_sync_container_deletions(self):
        helpers.DRY_RUN = False
        TestReminderContainer.__connect_caldav()
        helpers.DATA_LOCATION = Path.home() / "Library" / "Application Support" / "TaskBridge"

        for run in range(4):
            fail = None
            if run == 1:
                # Fail to seed reminders
                fail = 'fail_seed'
            elif run == 2:
                # Fail to retrieve containers
                fail = 'fail_retrieve'
            elif run == 3:
                # Fail to delete container table
                fail = 'fail_delete'

            # Create containers to be deleted
            delete_local = LocalList("DELETE_LOCAL")
            success, data = delete_local.create()
            if not success:
                assert False, 'Could not create local list {}'.format(delete_local.name)
            delete_remote = RemoteCalendar(calendar_name="DELETE_REMOTE")
            success, data = delete_remote.create()
            if not success:
                assert False, 'Could not create remote calendar {}'.format(delete_remote.name)

            # Fetch current containers
            success, data = ReminderContainer.load_local_lists()
            if not success:
                assert False, 'Could not load local lists {}'.format(data)
            discovered_local = data
            success, data = ReminderContainer.load_caldav_calendars()
            if not success:
                assert False, 'Could not load remote calendars {}'.format(data)
            discovered_remote = data

            # Persist containers
            to_sync = ['DELETE_LOCAL', 'DELETE_REMOTE']
            success, data = ReminderContainer.create_linked_containers(discovered_local, discovered_remote, to_sync)
            if not success:
                assert False, 'Could not create linked containers'

            # Delete the containers
            success, data = delete_local.delete()
            if not success:
                assert False, 'Could not delete local list {}'.format(delete_local.name)
            success, data = delete_remote.delete()
            if not success:
                assert False, 'Could not delete remote calendar {}'.format(delete_remote.name)

            # Fetch current containers
            success, data = ReminderContainer.load_local_lists()
            if not success:
                assert False, 'Could not load local lists {}'.format(data)
            discovered_local = data
            success, data = ReminderContainer.load_caldav_calendars()
            if not success:
                assert False, 'Could not load remote calendars {}'.format(data)
            discovered_remote = data

            # Synchronise the deletion
            success, data = ReminderContainer.sync_container_deletions(discovered_local, discovered_remote, to_sync, fail)
            if run > 0:
                assert success is False
            else:
                assert success is True
                # Ensure the containers have been deleted
                success, data = ReminderContainer.load_local_lists()
                if not success:
                    assert False, 'Could not load local lists {}'.format(data)
                local_lists = data
                success, data = ReminderContainer.load_caldav_calendars()
                if not success:
                    assert False, 'Could not load remote calendars {}'.format(data)
                remote_calendars = data
                local_presence = next((lst for lst in local_lists if lst.name == "DELETE_LOCAL"), None)
                remote_presence = next((cal for cal in remote_calendars if cal.name == "DELETE_REMOTE"), None)
                assert local_presence is None
                assert remote_presence is None

            # Clean Up
            ReminderContainer.CONTAINER_LIST.clear()
            try:
                with closing(sqlite3.connect(helpers.db_folder())) as connection:
                    connection.row_factory = sqlite3.Row
                    with closing(connection.cursor()) as cursor:
                        sql_delete_containers = "DELETE FROM tb_container"
                        cursor.execute(sql_delete_containers)
                        connection.commit()
            except sqlite3.OperationalError as e:
                print(e)

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and CalDAV credentials")
    def test__delete_remote_reminders(self):
        helpers.DRY_RUN = False

        sync_container = TestReminderContainer.__get_sync_container()

        # Create the reminder which will be deleted
        to_delete = Reminder(None, "DELETE_ME", None, datetime.datetime.now(), None,
                             None, None, None)
        success, data = to_delete.upsert_local(sync_container)
        if not success:
            assert False, 'Failed to create local reminder.'
        to_delete.uuid = data
        success, data = to_delete.upsert_remote(sync_container)
        if not success:
            assert False, 'Failed to create remote task.'

        # Refresh the container with the new reminder, and persist
        sync_container.load_local_reminders()
        sync_container.load_remote_reminders()
        sync_container.persist_reminders()

        # Delete the reminder locally
        delete_reminder_script = reminderscript.delete_reminder_script
        return_code, stdout, stderr = helpers.run_applescript(delete_reminder_script, to_delete.uuid)
        if return_code != 0:
            assert False, 'Failed to delete local reminder: {}'.format(stderr)

        # Refresh the container
        sync_container.local_reminders.clear()
        sync_container.load_local_reminders()
        sync_container.load_remote_reminders()

        # Get persisted reminders
        success, data = ReminderContainer.get_saved_reminders()
        if not success:
            assert False, 'Could not get saved reminders: {}'.format(data)
        saved_reminders = data
        container_saved_local = [r for r in saved_reminders if r['local_container'] == sync_container.local_list.name]

        # Synchronise the deletion
        result = {'deleted_remote_reminders': []}
        success, data = ReminderContainer._delete_remote_reminders(container_saved_local, sync_container, result)
        assert success is True

        # Ensure the locally deleted reminder has been deleted remotely
        deleted_reminder = next((dr for dr in result['deleted_remote_reminders'] if dr.name == to_delete.name), None)
        assert deleted_reminder is not None

        # Fail to delete
        to_delete.uuid = "BOGUS"
        success, data = ReminderContainer._delete_remote_reminders(container_saved_local, sync_container, result)
        assert success is False

        # Clean Up
        ReminderContainer.CONTAINER_LIST.clear()
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_delete_containers = "DELETE FROM tb_reminder"
                    cursor.execute(sql_delete_containers)
                    connection.commit()
        except sqlite3.OperationalError as e:
            print(e)

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and CalDAV credentials")
    def test__delete_local_reminders(self):
        helpers.DRY_RUN = False

        sync_container = TestReminderContainer.__get_sync_container()

        # Create the reminder which will be deleted
        to_delete = Reminder(None, "DELETE_ME", None, datetime.datetime.now(), None,
                             None, None, None)
        success, data = to_delete.upsert_local(sync_container)
        if not success:
            assert False, 'Failed to create local reminder.'
        to_delete.uuid = data
        success, data = to_delete.upsert_remote(sync_container)
        if not success:
            assert False, 'Failed to create remote task.'

        # Refresh the container with the new reminder, and persist
        sync_container.load_local_reminders()
        sync_container.load_remote_reminders()
        sync_container.persist_reminders()

        # Delete the reminder remotely
        to_delete_remote = sync_container.remote_calendar.cal_obj.search(todo=True, uid=to_delete.uuid)
        remote_reminder = next((r for r in sync_container.remote_reminders
                                if r.uuid == to_delete.uuid or r.name == to_delete.name), None)
        if len(to_delete_remote) > 0:
            to_delete_remote[0].delete()
            sync_container.remote_reminders.remove(remote_reminder)

        # Refresh the container
        sync_container.remote_reminders.clear()
        sync_container.load_local_reminders()
        sync_container.load_remote_reminders()

        # Get persisted reminders
        success, data = ReminderContainer.get_saved_reminders()
        if not success:
            assert False, 'Could not get saved reminders: {}'.format(data)
        saved_reminders = data
        container_saved_remote = [r for r in saved_reminders if r['remote_container'] == sync_container.remote_calendar.name]

        # Synchronise the deletion
        result = {'deleted_local_reminders': []}
        success, data = ReminderContainer._delete_local_reminders(container_saved_remote, sync_container, result)
        assert success is True

        # Ensure the remotely deleted reminder has been deleted locally
        deleted_reminder = next((dr for dr in result['deleted_local_reminders'] if dr.name == to_delete.name), None)
        assert deleted_reminder is not None

        # Fail
        success, data = ReminderContainer._delete_local_reminders(container_saved_remote, sync_container, result, True)
        assert success is False

        # Clean Up
        ReminderContainer.CONTAINER_LIST.clear()
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_delete_containers = "DELETE FROM tb_reminder"
                    cursor.execute(sql_delete_containers)
                    connection.commit()
        except sqlite3.OperationalError as e:
            print(e)

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud")
    def test_get_saved_reminders(self):
        helpers.DRY_RUN = False
        sync_container = TestReminderContainer.__get_sync_container()

        # Create a local reminder
        to_save = Reminder(None, "SAVE_ME", None, datetime.datetime.now(), None,
                           None, None, None)
        success, data = to_save.upsert_local(sync_container)
        if not success:
            assert False, 'Failed to create local reminder.'
        local_uuid = data

        # Refresh the container with the new reminder and persist
        sync_container.load_local_reminders()
        sync_container.persist_reminders()

        success, data = ReminderContainer.get_saved_reminders()
        assert success is True, 'Failed to load saved reminders'

        saved_reminder = next((r for r in data if r['local_name'] == 'SAVE_ME'), None)
        assert saved_reminder is not None

        # Clean Up
        delete_reminder_script = reminderscript.delete_reminder_script
        helpers.run_applescript(delete_reminder_script, local_uuid)
        ReminderContainer.CONTAINER_LIST.clear()
        try:
            with closing(sqlite3.connect(helpers.db_folder())) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    sql_delete_containers = "DELETE FROM tb_reminder"
                    cursor.execute(sql_delete_containers)
                    connection.commit()
        except sqlite3.OperationalError as e:
            print(e)

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and CalDAV credentials")
    def test_sync_reminder_deletions(self):
        helpers.DRY_RUN = False
        TestReminderContainer.__connect_caldav()
        helpers.DATA_LOCATION = Path.home() / "Library" / "Application Support" / "TaskBridge"

        tests = [None, 'fail_seed', 'fail_load_local', 'fail_load_remote', 'fail_get_saved', 'fail_db']
        for run in range(6):
            fail = tests[run]

            sync_container = TestReminderContainer.__get_sync_container()

            # Create the local reminder which will be deleted
            to_delete_local = Reminder(None, "DELETE_ME_LOCAL", None, datetime.datetime.now(), None,
                                       None, None, None)
            success, data = to_delete_local.upsert_local(sync_container)
            if not success:
                assert False, 'Failed to create local reminder.'
            to_delete_local.uuid = data
            success, data = to_delete_local.upsert_remote(sync_container)
            if not success:
                assert False, 'Failed to create remote task.'

            # Create the remote reminder which will be deleted
            to_delete_remote = Reminder(helpers.get_uuid(), "DELETE_ME_REMOTE", None, datetime.datetime.now(),
                                        None, None, None, None)
            success, data = to_delete_remote.upsert_remote(sync_container)
            if not success:
                assert False, 'Failed to create remote reminder.'
            success, data = to_delete_remote.upsert_local(sync_container)
            if not success:
                assert False, 'Failed to create remote task.'

            # Refresh the container with the new reminders, sync, and persist
            sync_container.load_local_reminders()
            sync_container.load_remote_reminders()
            success, data = sync_container.sync_reminders()
            if not success:
                assert False, 'Failed to sync reminders'
            sync_container.persist_reminders()

            # Get the new UUID of the remote reminder
            synced_local = next((r for r in sync_container.local_reminders if r.name == 'DELETE_ME_REMOTE'), None)
            to_delete_remote.uuid = synced_local.uuid

            # Delete the local reminder
            delete_reminder_script = reminderscript.delete_reminder_script
            return_code, stdout, stderr = helpers.run_applescript(delete_reminder_script, to_delete_local.uuid)
            if return_code != 0:
                assert False, 'Failed to delete local reminder: {}'.format(stderr)

            # Delete the remote reminder
            remote_object = sync_container.remote_calendar.cal_obj.search(todo=True, uid=to_delete_remote.uuid)
            if len(remote_object) > 0:
                remote_object[0].delete()

            # Sync reminder deletions
            sync_container.local_reminders.clear()
            sync_container.remote_reminders.clear()
            success, data = sync_container.sync_reminder_deletions(fail)
            if run > 0:
                assert success is False
            else:
                assert success is True
                # Ensure the remote reminder is not present locally
                sync_container.local_reminders.clear()
                sync_container.load_local_reminders()
                local_presence = next((r for r in sync_container.local_reminders if r.name == 'DELETE_ME_REMOTE'), None)
                assert local_presence is None

                # Ensure the local reminder is not present remotely
                sync_container.remote_reminders.clear()
                sync_container.load_remote_reminders()
                remote_presence = next((r for r in sync_container.remote_reminders if r.name == 'DELETE_ME_LOCAL'), None)
                assert remote_presence is None

            # Clean Up
            delete_reminder_script = reminderscript.delete_reminder_script
            helpers.run_applescript(delete_reminder_script, synced_local.uuid)
            remote_object = sync_container.remote_calendar.cal_obj.search(todo=True, uid=to_delete_remote.uuid)
            if len(remote_object) > 0:
                remote_object[0].delete()
            ReminderContainer.CONTAINER_LIST.clear()
            try:
                with closing(sqlite3.connect(helpers.db_folder())) as connection:
                    connection.row_factory = sqlite3.Row
                    with closing(connection.cursor()) as cursor:
                        sql_delete_containers = "DELETE FROM tb_reminder"
                        cursor.execute(sql_delete_containers)
                        connection.commit()
            except sqlite3.OperationalError as e:
                print(e)

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud")
    def test_load_local_reminders(self):
        helpers.DRY_RUN = False
        sync_container = TestReminderContainer.__get_sync_container()

        # Create a local reminder
        to_load = Reminder(None, "LOAD_ME", None, datetime.datetime.now(), None,
                           None, None, None)
        success, data = to_load.upsert_local(sync_container)
        if not success:
            assert False, 'Failed to create local reminder.'
        local_uuid = data

        fail = None
        for run in range(3):
            if run == 1:
                fail = "fail_load"
            elif run == 2:
                fail = "fail_psv"

            # Load local reminders
            success, data = sync_container.load_local_reminders(fail)
            if run > 0:
                assert success is False
            else:
                local_loaded = next((r for r in sync_container.local_reminders if r.name == "LOAD_ME"), None)
                assert local_loaded is not None

            # Clean Up
            ReminderContainer.CONTAINER_LIST.clear()
            delete_reminder_script = reminderscript.delete_reminder_script
            helpers.run_applescript(delete_reminder_script, local_uuid)

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires CalDAV credentials")
    def test_load_remote_reminders(self):
        helpers.DRY_RUN = False
        sync_container = TestReminderContainer.__get_sync_container()

        # Create a remote reminder
        to_load = Reminder("1234-2222-0909", "LOAD_ME", None, datetime.datetime.now(),
                           None, None, None, None)
        success, data = to_load.upsert_remote(sync_container)
        if not success:
            assert False, 'Failed to create remote reminder.'

        # Load remote reminders
        sync_container.load_remote_reminders()
        remote_loaded = next((r for r in sync_container.remote_reminders if r.name == "LOAD_ME"), None)
        assert remote_loaded is not None

        # Clean Up
        to_delete = sync_container.remote_calendar.cal_obj.search(todo=True, uid="1234-2222-0909")
        if len(to_delete) > 0:
            try:
                to_delete[0].delete()
            except AuthorizationError:
                print('Warning, failed to delete remote item.')
        ReminderContainer.CONTAINER_LIST.clear()

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and CalDAV credentials")
    def test_sync_local_reminders_to_remote(self):
        helpers.DRY_RUN = False
        sync_container = TestReminderContainer.__get_sync_container()

        fail = None
        for run in range(3):
            if run == 1:
                fail = "fail_upsert_remote"
            elif run == 2:
                fail = "local_older"

            # Create the local reminder
            to_sync = Reminder(None, "SYNC_ME_LOCAL", None, datetime.datetime.now(), None,
                               None, None, None)
            success, data = to_sync.upsert_local(sync_container)
            assert success is True
            to_sync.uuid = data

            # Sync Local --> Remote
            sync_container.load_local_reminders()
            sync_container.load_remote_reminders()
            result = {'remote_added': [], 'remote_updated': [], 'local_updated': []}
            success, data = sync_container.sync_local_reminders_to_remote(result, fail)
            if run == 1:
                assert success is False
            else:
                assert success is True

                if run == 0:
                    assert len(result['remote_added']) > 0, 'Failed to verify newly added reminder.'
                elif run == 2:
                    assert len(result['local_updated']) > 0, 'Failed to verify updated reminder.'

                # Get remote reminders
                sync_container.load_remote_reminders()
                remote_loaded = next((r for r in sync_container.remote_reminders if r.name == "SYNC_ME_LOCAL"), None)
                assert remote_loaded is not None

            # Clean Up
            to_delete = sync_container.remote_calendar.cal_obj.search(todo=True, uid=to_sync.uuid)
            if len(to_delete) > 0:
                try:
                    to_delete[0].delete()
                except AuthorizationError:
                    print('Warning, failed to delete remote item.')
            delete_reminder_script = reminderscript.delete_reminder_script
            helpers.run_applescript(delete_reminder_script, to_sync.uuid)
            ReminderContainer.CONTAINER_LIST.clear()

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and CalDAV credentials")
    def test_sync_remote_reminders_to_local(self):
        helpers.DRY_RUN = False
        sync_container = TestReminderContainer.__get_sync_container()

        fail = None
        for run in range(3):
            if run == 1:
                fail = "fail_upsert"
            elif run == 2:
                fail = "fail_uuid"

            # Create the remote reminder
            to_sync = Reminder("1234-2222-0909", "SYNC_ME_REMOTE", None, datetime.datetime.now(),
                               None, None, None, None)
            success, data = to_sync.upsert_remote(sync_container)
            if not success:
                assert False, 'Failed to create remote reminder.'

            # Sync Local <-- Remote
            sync_container.load_local_reminders()
            sync_container.load_remote_reminders()
            result = {'local_added': []}
            success, data = sync_container.sync_remote_reminders_to_local(result, fail)
            if run > 0:
                assert success is False
            else:
                assert success is True, 'Failed to sync remote reminders to local.'
                assert len(result['local_added']) > 0, 'Failed to verify newly added reminder.'

            # Get local reminders
            sync_container.load_local_reminders()
            local_loaded = next((r for r in sync_container.local_reminders if r.name == "SYNC_ME_REMOTE"), None)
            if run == 0:
                assert local_loaded is not None
            delete_reminder_script = reminderscript.delete_reminder_script
            helpers.run_applescript(delete_reminder_script, local_loaded.uuid)

            # Clean Up
            sync_container.local_reminders.clear()
            sync_container.remote_reminders.clear()
            if local_loaded:
                to_delete = sync_container.remote_calendar.cal_obj.search(todo=True, uid=local_loaded.uuid)
                if len(to_delete) > 0:
                    try:
                        to_delete[0].delete()
                    except AuthorizationError:
                        print('Warning, failed to delete remote item.')
            ReminderContainer.CONTAINER_LIST.clear()

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and CalDAV credentials")
    def test_sync_reminders(self):
        helpers.DRY_RUN = False
        sync_container = TestReminderContainer.__get_sync_container()

        fail = None
        for run in range(4):
            if run == 1:
                fail = "no_sync"
            elif run == 2:
                fail = "fail_upsert_remote"
            elif run == 3:
                fail = "fail_upsert"

            # Create the local reminder
            local_reminder = Reminder(None, "SYNC_ME_LOCAL", None, datetime.datetime.now(), None,
                                      None, None, None)
            success, data = local_reminder.upsert_local(sync_container)
            if not success:
                assert False, 'Failed to create local reminder.'
            local_reminder.uuid = data

            # Create the remote reminder
            remote_reminder = Reminder("1234-2222-0909", "SYNC_ME_REMOTE", None, datetime.datetime.now(),
                                       None, None, None, None)
            success, data = remote_reminder.upsert_remote(sync_container)
            assert success is True

            # Sync Reminders
            sync_container.load_local_reminders()
            sync_container.load_remote_reminders()
            sync_container.sync = not fail == "no_sync"
            success, data = sync_container.sync_reminders(fail)
            if run > 1:
                assert success is False
            else:
                assert success is True

                if fail == "no_sync":
                    assert data == "Container Sync is set to NO SYNC so skipped"

                # Verify results
                sync_container.load_local_reminders()
                local_loaded = next((r for r in sync_container.local_reminders if r.name == "SYNC_ME_REMOTE"), None)
                if sync_container.sync:
                    assert local_loaded is not None, 'Failed to sync remote reminder to local.'
                sync_container.load_remote_reminders()
                remote_loaded = next((r for r in sync_container.remote_reminders if r.name == "SYNC_ME_LOCAL"), None)
                if sync_container.sync:
                    assert remote_loaded is not None, 'Failed to sync local reminder to remote.'

            # Clean Up
            sync_container.load_local_reminders()
            local_loaded = next((r for r in sync_container.local_reminders if r.name == "SYNC_ME_REMOTE"), None)
            synced_local_uid = next((r for r in sync_container.local_reminders if r.name == "SYNC_ME_REMOTE"), None)
            if synced_local_uid is not None:
                to_delete = sync_container.remote_calendar.cal_obj.search(todo=True, uid=synced_local_uid.uuid)
                if len(to_delete) > 0:
                    try:
                        to_delete[0].delete()
                    except AuthorizationError:
                        print('Warning, failed to delete remote item.')
            to_delete = sync_container.remote_calendar.cal_obj.search(todo=True, uid=local_reminder.uuid)
            if len(to_delete) > 0:
                try:
                    to_delete[0].delete()
                except AuthorizationError:
                    print('Warning, failed to delete remote item.')
            delete_reminder_script = reminderscript.delete_reminder_script
            helpers.run_applescript(delete_reminder_script, local_reminder.uuid)
            if local_loaded is not None:
                helpers.run_applescript(delete_reminder_script, local_loaded.uuid)
            sync_container.local_reminders.clear()
            sync_container.remote_reminders.clear()
            ReminderContainer.CONTAINER_LIST.clear()

    def test___str__(self):
        sync_container = TestReminderContainer.__get_sync_container()
        desc = sync_container.__str__()
        assert desc == "<Local: Sync, Remote: Sync, Sync: True>"

    def test___repr__(self):
        sync_container = TestReminderContainer.__get_sync_container()
        desc = sync_container.__str__()
        assert desc == "<Local: Sync, Remote: Sync, Sync: True>"

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and CalDAV credentials")
    def test_disconnected_caldav(self):
        helpers.DRY_RUN = False
        TestReminderContainer.__connect_caldav(True)
        ReminderContainer.CONTAINER_LIST.clear()

        # Fail to load remote calendars
        success, data = ReminderContainer.load_caldav_calendars()
        assert success is False

        # Fail to associate local with remote
        mock_local = [LocalList("sync_me"), LocalList("do_not_sync_me")]
        mock_remote = [RemoteCalendar(calendar_name="sync_me"), RemoteCalendar(calendar_name="do_not_sync_me")]
        mock_sync = ['sync_me']
        success, data = ReminderContainer.assoc_list_local_remote(mock_local, mock_remote, mock_sync)
        assert success is True

        # Fail to delete remote container
        to_delete = LocalList('DELETE_ME')
        to_keep = LocalList('KEEP_ME')
        removed_remote_containers = [{'remote_name': 'NON_EXISTENT'}]
        removed_local_containers = []
        discovered_local = [to_delete, to_keep]
        to_sync = ['DELETE_ME', 'KEEP_ME', 'NON_EXISTENT']
        result = {'updated_local_list': []}
        # noinspection PyTypeChecker
        success, data = ReminderContainer._delete_local_containers(removed_remote_containers, removed_local_containers,
                                                                   discovered_local, to_sync, result)
        assert success is False

        # Fail to delete local container
        to_delete = LocalList('DELETE_ME')
        to_keep = LocalList('KEEP_ME')
        removed_remote_containers = [{'remote_name': 'NON_EXISTENT'}]
        removed_local_containers = []
        discovered_local = [to_delete, to_keep]
        to_sync = ['DELETE_ME', 'KEEP_ME', 'NON_EXISTENT']
        result = {'updated_local_list': []}
        # noinspection PyTypeChecker
        success, data = ReminderContainer._delete_local_containers(removed_remote_containers, removed_local_containers,
                                                                   discovered_local, to_sync, result, True)
        assert success is False

    @pytest.mark.skipif(TEST_ENV != 'local', reason="Requires Mac system with iCloud and CalDAV credentials")
    def test_unavailable_db(self):
        helpers.DATA_LOCATION = Path("/")

        success, data = ReminderContainer.seed_container_table()
        assert success is False

        success, data = ReminderContainer.seed_reminder_table()
        assert success is False

        success, data = ReminderContainer.persist_reminders()
        assert success is False

        success, data = ReminderContainer.persist_containers()
        assert success is False

        success, data = ReminderContainer.get_saved_reminders()
        assert success is False
