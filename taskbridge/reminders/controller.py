"""
This is the reminder synchronisation controller. It takes care of the reminder synchronisation process.
"""

import logging
from typing import List

import caldav

from taskbridge import helpers
from taskbridge.reminders.model.remindercontainer import ReminderContainer


class ReminderController:
    LOCAL_LISTS = []
    REMOTE_CALENDARS = []
    CALDAV_URL = ''
    CALDAV_USERNAME = ''
    CALDAV_PASSWORD = ''
    CALDAV_HEADERS = {}
    TO_SYNC = []

    @staticmethod
    def fetch_local_reminders() -> tuple[bool, str]:
        success, data = ReminderContainer.load_local_lists()
        if not success:
            error = 'Failed to fetch local reminder lists: {}'.format(data)
            logging.critical(error)
            return False, error
        ReminderController.LOCAL_LISTS = data
        debug_msg = 'Found local reminder lists: {}'.format([ll.name for ll in ReminderController.LOCAL_LISTS])
        logging.debug(debug_msg)
        return True, debug_msg

    @staticmethod
    def connect_caldav() -> tuple[bool, str]:
        client = caldav.DAVClient(
            url=ReminderController.CALDAV_URL,
            username=ReminderController.CALDAV_USERNAME,
            password=ReminderController.CALDAV_PASSWORD,
            headers=ReminderController.CALDAV_HEADERS,
        )
        helpers.CALDAV_PRINCIPAL = client.principal()
        return True, "Successfully connected to CalDav."

    @staticmethod
    def fetch_remote_reminders() -> tuple[bool, str]:
        success, data = ReminderContainer.load_caldav_calendars()
        if not success:
            error = 'Failed to fetch remote CalDav calendars: {}'.format(data)
            logging.critical(error)
            return False, error
        ReminderController.REMOTE_CALENDARS = data
        debug_msg = 'Found remote CalDav calendars: {}'.format([rc.name for rc in ReminderController.REMOTE_CALENDARS])
        logging.debug(debug_msg)
        return True, debug_msg

    @staticmethod
    def sync_deleted_containers() -> tuple[bool, str]:
        success, data = ReminderContainer.sync_container_deletions(
            ReminderController.LOCAL_LISTS,
            ReminderController.REMOTE_CALENDARS,
            ReminderController.TO_SYNC)
        if not success:
            error = 'Failed to sync container deletions: {}'.format(data)
            logging.critical(error)
            return False, error
        ReminderController.LOCAL_LISTS = data['updated_local_list']
        ReminderController.REMOTE_CALENDARS = data['updated_remote_list']
        debug_msg = "Lists after deletion:: Local List: {} | Remote List: {}".format(
                ', '.join(str(u) for u in data['updated_local_list']),
                ', '.join(str(u) for u in data['updated_remote_list'])
            )
        logging.debug(debug_msg)
        return True, debug_msg

    @staticmethod
    def associate_containers() -> tuple[bool, str] | tuple[bool, List[ReminderContainer]]:
        ReminderContainer.CONTAINER_LIST.clear()
        success, data = ReminderContainer.create_linked_containers(
            ReminderController.LOCAL_LISTS,
            ReminderController.REMOTE_CALENDARS,
            ReminderController.TO_SYNC)
        if not success:
            error = 'Failed to associate containers: {}'.format(data)
            logging.critical(error)
            return False, error
        debug_msg = 'Containers synchronised: {}'.format(ReminderContainer.CONTAINER_LIST)
        logging.debug(debug_msg)
        return True, ReminderContainer.CONTAINER_LIST

    @staticmethod
    def sync_deleted_reminders() -> tuple[bool, str]:
        success, data = ReminderContainer.sync_reminder_deletions()
        if not success:
            error = 'Failed to sync reminder deletions: {}'.format(data)
            logging.critical(error)
            return False, error
        debug_msg = "Reminders deleted:: Local: {} | Remote: {}".format(
                ', '.join(str(r) for r in data['deleted_local_reminders']),
                ', '.join(str(r) for r in data['deleted_remote_reminders']))
        logging.debug(debug_msg)
        return True, debug_msg

    @staticmethod
    def sync_reminders() -> tuple[bool, str] | tuple[bool, dict]:
        data = None
        for container in ReminderContainer.CONTAINER_LIST:
            success, data = container.sync_reminders()
            if not success:
                error = 'Failed to sync reminders {}'.format(data)
                logging.critical(error)
                return False, error
        debug_msg = "Notes synchronisation:: Remote Added: {} | Remote Updated: {} | Local Added: {} | Local Updated: {}".format(
                ','.join(data['remote_added']),
                ', '.join(data['remote_updated']),
                ', '.join(data['local_added']),
                ', '.join(data['local_updated']))
        logging.debug(debug_msg)
        return True, data

    @staticmethod
    def sync_reminders_to_db() -> tuple[bool, str]:
        success, data = ReminderContainer.persist_reminders()
        if not success:
            error = 'Failed to save reminders in database {}'.format(data)
            logging.critical(error)
            return False, error
        debug_msg = 'Notes saved to database.'
        logging.debug(debug_msg)
        return True, debug_msg

    @staticmethod
    def count_completed() -> tuple[bool, str] | tuple[bool, int]:
        success, data = ReminderContainer.count_local_completed()
        if not success:
            error = data
            logging.critical(error)
            return False, error
        debug_msg = 'Number of completed reminders: {}'.format(data)
        logging.debug(debug_msg)
        return True, data

    @staticmethod
    def delete_completed() -> tuple[bool, str]:
        success, data = ReminderContainer.delete_local_completed()
        if not success:
            error = 'Failed to delete completed reminders.'
            logging.critical(error)
            return False, error
        debug_msg = 'Deleted completed reminders.'
        logging.debug(debug_msg)
        return True, debug_msg
