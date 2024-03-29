import logging
import os
from datetime import date
from typing import List

import caldav
from caldav import Principal, Calendar, CalendarObjectResource

from Controller import reminders_as
from Model.LinkedCalendar import ReminderList, LinkedCalendar
from Model.Reminder import Reminder
from Model.Util import Util


logger = logging.getLogger(__name__)


def get_caldav_tasks_calendars(principal: Principal) -> List[Calendar]:
    logging.info("Retrieving CalDav Tasks Calendars.")
    task_calendars = []
    calendars = principal.calendars()
    for c in calendars:
        acceptable_component_types = c.get_supported_components()
        if "VTODO" in acceptable_component_types:
            task_calendars.append(c)
    logging.info("Found {0:d} CalDav Tasks Calendars: {1:s}".format(
        len(task_calendars),
        ','.join([tc.name for tc in task_calendars])))
    return task_calendars


def get_local_reminder_lists() -> List[ReminderList]:
    logging.info("Retrieving Local Reminder Lists.")
    reminder_lists = []
    script_result = reminders_as.run(reminders_as.GET_REMINDER_LISTS)
    stdout = script_result['stdout']
    for r_list in stdout.split('|'):
        data = r_list.split(':')
        reminder_lists.append(ReminderList(data[0], data[1]))
    logging.info("Found {0:d} Local Reminder Lists: {1:s}".format(
        len(reminder_lists),
        ','.join([rl.name for rl in reminder_lists])))
    return reminder_lists


def sync_lists(caldav_calendars: List[Calendar], reminder_lists: List[ReminderList], principal: Principal) -> bool:
    # The List "Reminders" is always associated with the calendar "Tasks"

    # Create a CalDav tasks calendar for every reminder list
    logger.info("Associating Local Lists with CalDav Calendars.")
    for r_list in reminder_lists:
        create_caldav_name = None
        if r_list.name == "Reminders":
            assoc_caldav = next((x for x in caldav_calendars if x.name == "Tasks"), None)
            if assoc_caldav is None:
                create_caldav_name = "Tasks"
            else:
                logger.info(
                    "Associating local list {0} with CalDav calendar {1}".format(r_list.name, assoc_caldav.name))
                LinkedCalendar(r_list, assoc_caldav)
        else:
            assoc_caldav = next((x for x in caldav_calendars if x.name == r_list.name), None)
            if assoc_caldav is None:
                create_caldav_name = r_list.name
            else:
                logger.info(
                    "Associating local list {0} with CalDav calendar {1}".format(r_list.name, assoc_caldav.name))
                LinkedCalendar(r_list, assoc_caldav)

        if create_caldav_name is not None:
            logger.info("Creating CalDav calendar {}".format(create_caldav_name))
            new_calendar = principal.make_calendar(
                name=create_caldav_name,
            )
            logger.info("Associating local list {0} with CalDav calendar {1}".format(r_list.name, new_calendar.name))
            LinkedCalendar(r_list, new_calendar)

    # Create a Reminder list for every CalDav tasks calendar
    logger.info("Associating CalDav calendars with local lists.")
    for c_cal in caldav_calendars:
        if c_cal.name == "Tasks":
            continue
        create_reminder_list_name = None
        assoc_r_list = next((x for x in reminder_lists if x.name == c_cal.name), None)
        if assoc_r_list is None:
            create_reminder_list_name = c_cal.name

        if create_reminder_list_name is not None:
            logger.info("Creating local reminder list {}".format(create_reminder_list_name))
            script_result = reminders_as.run(reminders_as.CREATE_REMINDER_LIST, [create_reminder_list_name])
            new_list = ReminderList(script_result['stdout'], create_reminder_list_name)
            logger.info("Associating CalDav calendar {0} with local list {1}".format(c_cal.name, new_list.name))
            LinkedCalendar(new_list, c_cal)

    Util.export_list_db(LinkedCalendar.CALENDAR_LIST)

    return True


def sync_local_to_caldav(linked: LinkedCalendar) -> bool:
    logger.info("Synchronising local reminders from list {} to CalDav".format(linked.reminder_list.name))
    logger.info("Exporting reminders to file.")
    script_result = reminders_as.run(reminders_as.GET_LIST_REMINDERS, [linked.reminder_list.name])
    export_path = script_result['stdout'].strip() + '/' + linked.reminder_list.name + '.psv'

    # Load exported reminders
    logger.info("Reading reminders from file.")
    with open(export_path, 'r') as infile:
        file_data = infile.read()
        infile.close()
    for local_reminder in file_data.split('\n'):
        value_count = local_reminder.split('|')
        if len(value_count) > 1:
            Reminder.from_tokenized(local_reminder, '|')

    sync_deletions(linked.reminder_list.name, Reminder.REMINDER_LIST, linked.caldav_calendar.name,
                   linked.caldav_calendar)

    local_uuids = Util.get_local_uuids(Reminder.REMINDER_LIST)
    caldav_uuids = Util.get_caldav_uuids(linked.caldav_calendar)

    # Loop through the list of reminders from the file
    for local_reminder in Reminder.REMINDER_LIST:
        # Check if this reminder is already in caldav
        tasks_in_caldav = linked.caldav_calendar.search(todo=True, uid=local_reminder.id)
        if len(tasks_in_caldav) > 0:
            remote_task = tasks_in_caldav[0]
            # Reminder is in both the local file and in caldav, so we need to update one or the other
            remote_modification_date = remote_task.icalendar_component['LAST-MODIFIED'].dt
            if remote_modification_date > local_reminder.modification_date:
                # Remote is newer. Overwrite local with CalDav
                logger.info("Updating local reminder {} from CalDav.".format(local_reminder.name))
                upsert_local_reminder(linked.reminder_list.name, remote_task, local_reminder)
            elif local_reminder.modification_date > remote_modification_date:
                # Local is newer. Overwrite CalDav with local
                logger.info("Updating CalDav task {} from local reminder.".format(remote_task.name))
                update_caldav_reminder(local_reminder, remote_task)
        else:
            logger.info("Adding Reminder {} to CalDav.".format(local_reminder.name))
            # Reminder is not in caldav, so we need to add it
            linked.caldav_calendar.save_todo(ical=local_reminder.get_ical_string())
            caldav_uuids.append(local_reminder.id)
    os.remove(export_path)

    logger.info("Synchronising::: Remote:{0} --> Local:{1}".format(
        linked.caldav_calendar.name, linked.reminder_list.name
    ))
    modified_uuids = sync_caldav_to_local(linked)
    local_uuids.extend(modified_uuids['added'])
    caldav_uuids = [uuid for uuid in caldav_uuids if uuid not in modified_uuids['removed']]  # Remove old CalDav UUIDs
    caldav_uuids.extend(modified_uuids['added'])

    Util.export_uuids('local', linked.reminder_list.name, local_uuids)
    Util.export_uuids('caldav', linked.caldav_calendar.name, caldav_uuids)
    Reminder.REMINDER_LIST.clear()
    return True


def upsert_local_reminder(r_list: str, remote: CalendarObjectResource, local: Reminder | None = None) -> str | None:
    r_id = '' if local is None else local.id
    r_name = remote.icalendar_component['summary']
    r_body = remote.icalendar_component['description'] if 'DESCRIPTION' in remote.icalendar_component else ''
    r_due_date = ''
    r_allday_due = "false"
    if 'DUE' in remote.icalendar_component:
        due_date = remote.icalendar_component['DUE'].dt
        r_due_date = Util.get_apple_datetime_string(due_date)
        r_allday_due = "true" if isinstance(due_date, date) else "false"

    r_completed_date = ''
    r_completed = "false"
    if 'COMPLETED' in remote.icalendar_component:
        completed_date = remote.icalendar_component['COMPLETED'].dt
        r_completed_date = Util.get_apple_datetime_string(completed_date)
        r_completed = "true"

    r_remind_date = ''
    if 'TRIGGER' in remote.icalendar_component:
        remind_date = remote.icalendar_component['TRIGGER'].dt
        r_remind_date = Util.get_apple_datetime_string(remind_date)

    script_result = reminders_as.run(reminders_as.ADD_REMINDER,
                                     [r_id, r_name, r_body, r_completed, r_completed_date, r_due_date,
                                      r_allday_due, r_remind_date, r_list])

    # Set CalDav UID to local UID
    if local is None:
        try:
            new_id = script_result['stdout'].decode().strip()
        except AttributeError:
            new_id = script_result['stdout'].strip()
        remote.icalendar_component["uid"] = new_id
        remote.save()
        return new_id


def update_caldav_reminder(local: Reminder, remote: CalendarObjectResource):
    if local.due_date.strftime("%H:%M:%S") == "00:00:00":
        due_date = Util.get_caldav_date_string(local.due_date)
    else:
        due_date = Util.get_caldav_datetime_string(local.due_date)

    if local.reminder_date.strftime("%H:%M:%S") == "00:00:00":
        # Alarm with no time
        local.reminder_date = local.reminder_date.replace(hour=local.default_alarm_hour, minute=0)
    alarm_trigger = Util.get_caldav_datetime_string(local.reminder_date)

    remote.icalendar_component["uid"] = local.id
    remote.icalendar_component["summary"] = local.name
    remote.icalendar_component["due"] = due_date
    remote.icalendar_component["status"] = local.status
    remote.icalendar_component["trigger"] = alarm_trigger
    if local.status == 'COMPLETED':
        remote.icalendar_component["PERCENT-COMPLETE"] = "100"
        remote.icalendar_component["COMPLETED"] = Util.get_caldav_datetime_string(local.completion_date)
    remote.save()


# noinspection PyUnresolvedReferences
def sync_caldav_to_local(linked: LinkedCalendar) -> dict:
    logger.info("Synchronising CalDav tasks in calendar {} to local".format(linked.caldav_calendar.name))
    caldav_tasks = linked.caldav_calendar.todos()
    added_uuids = []
    removed_uuids = []
    for caldav_task in caldav_tasks:
        remote_uuid = caldav_task.icalendar_component['uid']
        local_task = next((x for x in Reminder.REMINDER_LIST if x.id == remote_uuid), None)
        if local_task is None:
            logger.info("Adding local reminder {} from CalDav".format(caldav_task.name))
            uuid = upsert_local_reminder(linked.caldav_calendar.name, caldav_task)
            added_uuids.append(uuid)
            removed_uuids.append(remote_uuid)

    return {
        'added': added_uuids,
        'removed': removed_uuids
    }


# noinspection PyUnresolvedReferences
def sync_deletions(local_list_name: str, local_reminders: List[Reminder], caldav_list_name: str,
                   caldav_cal: Calendar) -> None:
    # Reminders removed from local need to be removed from CalDav
    already_deleted = []
    logger.info(
        "Synchronising items deleted from local list {0} to CalDav list {1}".format(local_list_name, caldav_list_name))
    stored_local_uuids = Util.import_uuids('local', local_list_name)
    if not stored_local_uuids:
        return
    for stored_uuid in stored_local_uuids:
        if stored_uuid not in [o.id for o in local_reminders]:
            to_delete = caldav_cal.search(todo=True, uid=stored_uuid)
            if len(to_delete) > 0:
                logger.info("Deleting CalDav item {}".format(to_delete[0].icalendar_component['summary']))
                to_delete[0].delete()
                already_deleted.append(stored_uuid)

    # Reminders removed form CalDav need to be removed from local
    logger.info(
        "Synchronising items deleted from CalDav list {0} to local list {1}".format(caldav_list_name, local_list_name))
    stored_caldav_uuids = Util.import_uuids('caldav', caldav_list_name)
    if not stored_caldav_uuids:
        return
    for stored_uuid in stored_caldav_uuids:
        if stored_uuid not in already_deleted and stored_uuid not in [o.icalendar_component['uid'] for o in
                                                                      caldav_cal.todos()]:
            to_delete = next((x for x in local_reminders if x.id == stored_uuid), None)
            logger.info("Deleting local item {}".format(to_delete.name))
            reminders_as.run(reminders_as.DELETE_REMINDER, [stored_uuid])


def sync_reminders(linked_calendars: List[LinkedCalendar]) -> bool:
    for linked in linked_calendars:
        logger.info("Synchronising::: Local:{0} --> Remote:{1}".format(
            linked.reminder_list.name, linked.caldav_calendar.name))
        sync_local_to_caldav(linked)
    return False


def sync_list_deletions(principal: Principal) -> None:
    caldav_calendars = get_caldav_tasks_calendars(principal)
    reminder_lists = get_local_reminder_lists()

    old_state: List[LinkedCalendar] = Util.import_list_db()

    if not old_state:
        return

    # Check for any local reminder lists which have been deleted, and delete associated CalDav calendars
    previous_local = [o.reminder_list.name for o in old_state]
    current_local = [o.name for o in reminder_lists]
    deleted_local = [item for item in previous_local if item not in current_local]
    for to_delete in deleted_local:
        logger.info('The local list {} was deleted. Removing it from CalDav.'.format(to_delete))
        if to_delete == "Reminders":
            to_delete = "Tasks"
        cal = principal.calendar(name=to_delete)
        cal.delete()
        Util.delete_uuid_db(to_delete)

    # Check for any CalDav calendars which have been deleted, and delete associated local lists
    previous_caldav = [o.caldav_calendar.name for o in old_state]
    current_caldav = [o.name for o in caldav_calendars]
    deleted_caldav = [item for item in previous_caldav if item not in current_caldav]
    for to_delete in deleted_caldav:
        logger.info('The CalDav list {} was deleted. Removing it from local.'.format(to_delete))
        if to_delete == "Tasks":
            to_delete = "Reminders"
        reminders_as.run(reminders_as.DELETE_LIST, [to_delete])
        Util.delete_uuid_db(to_delete)


def sync(caldav_url: str, username: str, password: str, headers: dict) -> bool:
    logging.basicConfig(filename='../log/reminder_sync.log', level=logging.INFO, format='%(asctime)s %(message)s')

    logger.info('--- STARTING REMINDER SYNC ---')
    with caldav.DAVClient(
            url=caldav_url,
            username=username,
            password=password,
            headers=headers,
    ) as client:
        principal = client.principal()
        sync_list_deletions(principal)
        caldav_calendars = get_caldav_tasks_calendars(principal)
        reminder_lists = get_local_reminder_lists()
        if sync_lists(caldav_calendars, reminder_lists, principal):
            sync_reminders(LinkedCalendar.CALENDAR_LIST)
        logger.info('--- FINISHED REMINDER SYNC ---')
        return True
