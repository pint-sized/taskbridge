"""
This is the reminder synchronisation controller. It contains all methods required for reminder synchronisation. These are
called by the GUI, but can be called separately if imported.
"""
from __future__ import annotations

import logging
from typing import List

import caldav


from taskbridge import helpers
from taskbridge.reminders.model.remindercontainer import ReminderContainer


class ReminderController:
    """
    Contains various static methods for the stages of reminder synchronisation.
    """

    #: Local reminder lists
    LOCAL_LISTS = []
    #: Remote note calendars
    REMOTE_CALENDARS = []
    #: URL of the remote calendar server
    CALDAV_URL = ''
    #: Username of the remote calendar server
    CALDAV_USERNAME = ''
    #: Password of the remote calendar server (this is stored in KeyChain)
    CALDAV_PASSWORD = ''
    #: Headers to send to the remote calendar server (currently unused)
    CALDAV_HEADERS = {}
    #: List of reminder lists to be synchronised
    TO_SYNC = []

    @staticmethod
    def fetch_local_reminders() -> tuple[bool, str]:
        """
        Fetch local reminder lists

        :returns:

            -success (:py:class:`bool`) - true if local reminder lists are fetched successfully.

            -data (:py:class:`str`) - error message on failure, or success message.
        """
        success, data = ReminderContainer.load_local_lists()
        if not success:
            error = 'Failed to fetch local reminder lists: {}'.format(data)
            logging.critical(error)
            return False, error
        ReminderController.LOCAL_LISTS = data
        debug_msg = 'Found local reminder lists: {}'.format([ll.name for ll in ReminderController.LOCAL_LISTS])
        logging.debug(debug_msg)
        return True, debug_msg

    # noinspection PyUnresolvedReferences
    @staticmethod
    def connect_caldav() -> tuple[bool, str]:
        """
        Connect to the remote CalDav server.

        :returns:

            -success (:py:class:`bool`) - true if a connection is successfully made.

            -data (:py:class:`str`) - success message.

        """
        try:
            client = caldav.DAVClient(
                url=ReminderController.CALDAV_URL,
                username=ReminderController.CALDAV_USERNAME,
                password=ReminderController.CALDAV_PASSWORD,
                headers=ReminderController.CALDAV_HEADERS,
            )
            helpers.CALDAV_PRINCIPAL = client.principal()
            return True, "Successfully connected to CalDav."
        except caldav.lib.error.AuthorizationError:
            return False, "Failed to connect to CalDAV."

    @staticmethod
    def fetch_remote_reminders() -> tuple[bool, str]:
        """
        Fetch remote reminders.

        :returns:

            -success (:py:class:`bool`) - true if remote reminders are fetched successfully.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
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
        """
        Synchronise deleted local reminder lists / remote task calendars.

        :returns:

            -success (:py:class:`bool`) - true if reminder containers are synchronised successfully.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
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
        """
        Associate local reminder lists with remote task calendars.

        :returns:

            -success (:py:class:`bool`) - true if associations are successfully created.

            -data (:py:class:`str` | :py:class:`List[ReminderContainer]`) - error message on failure, or list of reminder
            containers.

        """
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
        """
        Synchronise deleted reminders.

        :returns:

            -success (:py:class:`bool`) - true if deleted reminders are synchronised successfully.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
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
        """
        Synchronise reminders. Returns a dictionary with the following keys:

        - ``remote_added`` - name of reminders added to the remote calendar as :py:class:`List[str]`.
        - ``remote_updated`` - name of reminders updated in the remote calendar as :py:class:`List[str]`.
        - ``local_added`` - name of reminders added to the local list as :py:class:`List[str]`.
        - ``local_updated`` - name of reminders updated in the local list as :py:class:`List[str]`.

        Any of the above may be empty if no such changes were made.

        :returns:

            -success (:py:class:`bool`) - true if notes are successfully synchronised.

            -data (:py:class:`str` | :py:class:`dict`) - error message on failure, or :py:class:`dict` with results as above.

        """
        if len(ReminderContainer.CONTAINER_LIST) == 0:
            return True, {}
        data = None
        for container in ReminderContainer.CONTAINER_LIST:
            success, data = container.sync_reminders()
            if not success:
                error = 'Failed to sync reminders {}'.format(data)
                logging.critical(error)
                return False, error
        debug_msg = ("Reminder synchronisation:: Remote Added: {} | Remote Updated: {} | Local Added: {} | Local Updated: {"
                     "}").format(
            ','.join(data['remote_added'] if 'remote_added' in data else ['No remote reminders added']),
            ', '.join(data['remote_updated'] if 'remote_updated' in data else ['No remote reminders updated']),
            ', '.join(data['local_added'] if 'local_added' in data else ['No local reminders added']),
            ', '.join(data['local_updated'] if 'local_updated' in data else ['No local reminders updated']))
        logging.debug(debug_msg)
        return True, data

    @staticmethod
    def sync_reminders_to_db() -> tuple[bool, str]:
        """
        Save list of reminders to SQLite database.

        :returns:

            -success (:py:class:`bool`) - true if reminders are saved successfully.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
        success, data = ReminderContainer.persist_reminders()
        if not success:
            error = 'Failed to save reminders in database {}'.format(data)
            logging.critical(error)
            return False, error
        debug_msg = 'Reminders saved to database.'
        logging.debug(debug_msg)
        return True, debug_msg

    @staticmethod
    def count_completed() -> tuple[bool, str] | tuple[bool, int]:
        """
        Count the number of local completed reminders.

        :returns:

            -success (:py:class:`bool`) - true if completed reminders are counted successfully.

            -data (:py:class:`str` | :py:class:`int`) - error message on failure, or number of completed reminders.

        """
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
        """
        Delete completed reminders.

        :returns:

            -success (:py:class:`bool`) - true if completed reminders are deleted successfully.

            -data (:py:class:`str`) - error message on failure, or success message.

        """
        success, data = ReminderContainer.delete_local_completed()
        if not success:
            error = 'Failed to delete completed reminders.'
            logging.critical(error)
            return False, error
        debug_msg = 'Deleted completed reminders.'
        logging.debug(debug_msg)
        return True, debug_msg
