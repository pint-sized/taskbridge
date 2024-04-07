"""
This is the reminder synchronisation controller. It takes care of the reminder synchronisation process.
"""

import logging
import sys
from typing import List

import caldav

from taskbridge import helpers
from taskbridge.reminders.model.remindercontainer import ReminderContainer


def sync(caldav_url: str, username: str, password: str, headers: dict, to_sync: List[str]):
    """
    Carries out the reminder synchronisation process.

    :param caldav_url: URL to the CalDav endpoint for this user.
    :param username: username for CalDav.
    :param password: password for CalDav.
    :param headers: any headers to send to the CalDav server.
    :param to_sync: list of reminder lists or task calendars which should be synchronised.

    """
    logging.info('-- STARTING REMINDER SYNC --')

    with caldav.DAVClient(
            url=caldav_url,
            username=username,
            password=password,
            headers=headers,
    ) as client:
        helpers.CALDAV_PRINCIPAL = client.principal()

        # Fetch remote CalDav VTODO Calendars
        success, data = ReminderContainer.load_caldav_calendars()
        if not success:
            logging.critical('Failed to fetch remote CalDav calendars: {}'.format(data))
            sys.exit(7)
        remote_calendars = data
        logging.debug('Found remote CalDav calendars: {}'.format([rc.name for rc in remote_calendars]))

        # Fetch local reminder lists
        success, data = ReminderContainer.load_local_lists()
        if not success:
            logging.critical('Failed to fetch local reminder lists: {}'.format(data))
            sys.exit(8)
        local_lists = data
        logging.debug('Found local reminder lists: {}'.format([ll.name for ll in local_lists]))

        # Sync deleted containers
        success, data = ReminderContainer.sync_container_deletions(local_lists, remote_calendars, to_sync)
        if not success:
            logging.critical('Failed to sync container deletions: {}'.format(data))
            sys.exit(9)
        local_lists = data['updated_local_list']
        remote_calendars = data['updated_remote_list']
        logging.debug(
            "Lists after deletion:: Local List: {} | Remote List: {}".format(
                ', '.join(str(u) for u in data['updated_local_list']),
                ', '.join(str(u) for u in data['updated_remote_list'])
            ))

        # Associate containers
        success, data = ReminderContainer.create_linked_containers(local_lists, remote_calendars, to_sync)
        if not success:
            logging.critical('Failed to associate containers: {}'.format(data))
            sys.exit(10)
        logging.debug('Containers synchronised: {}'.format(ReminderContainer.CONTAINER_LIST))

        # Sync deleted reminders
        success, data = ReminderContainer.sync_reminder_deletions()
        if not success:
            logging.critical('Failed to sync reminder deletions: {}'.format(data))
            sys.exit(11)
        logging.debug(
            "Reminders deleted:: Local: {} | Remote: {}".format(
                ', '.join(str(r) for r in data['deleted_local_reminders']),
                ', '.join(str(r) for r in data['deleted_remote_reminders'])
            ))

        # Sync reminders
        for container in ReminderContainer.CONTAINER_LIST:
            success, data = container.sync_reminders()
            if not success:
                logging.critical('Failed to sync reminders {}'.format(data))
                sys.exit(12)
        logging.debug(
            "Notes synchronisation:: Remote Added: {} | Remote Updated: {} | Local Added: {} | Local Updated: {}".format(
                ','.join(data['remote_added']),
                ', '.join(data['remote_updated']),
                ', '.join(data['local_added']),
                ', '.join(data['local_updated'])
            ))

        # Save reminders to DB
        success, data = ReminderContainer.persist_reminders()
        if not success:
            logging.critical('Failed to save reminders in database {}'.format(data))
            sys.exit(13)

    logging.info('-- FINISHED REMINDER SYNC --')
