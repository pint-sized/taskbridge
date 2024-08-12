import csv
import json
import logging
import os
import pathlib
import sys
from datetime import datetime
from getpass import getpass
from pathlib import Path
from typing import Callable

import keyring

from taskbridge import helpers

import argparse

from taskbridge.notes.controller import NoteController
from taskbridge.notes.model import notescript
from taskbridge.reminders.controller import ReminderController
from taskbridge.reminders.model import reminderscript


class TaskBridgeCli:
    """
    Defines the functionality of the TaskBridge CLI.
    """

    SETTINGS = {
        'sync_notes': '0',
        'remote_notes_folder': '',
        'associations': {
            'bi_directional': [],
            'local_to_remote': [],
            'remote_to_local': []
        },
        'sync_reminders': '0',
        'prune_reminders': '0',
        'caldav_server': '',
        'caldav_path': '',
        'caldav_url': '',
        'caldav_username': '',
        'caldav_type': '',
        'reminder_sync': [],
        'log_level': 'debug',
        'autosync': '0',
        'autosync_interval': 0,
        'autosync_unit': 'Minutes'
    }

    def __init__(self, args):
        self.args = args
        self.logger = self.setup_logging()
        self.apply_settings()
        if (TaskBridgeCli.SETTINGS['sync_reminders'] == '1'
                and self.authenticate_caldav() and TaskBridgeCli.preflight_reminders()):
            TaskBridgeCli.sync_reminders()
        if TaskBridgeCli.SETTINGS['sync_notes'] == '1' and TaskBridgeCli.preflight_notes():
            TaskBridgeCli.sync_notes()
        logging.info("Synchronisation tasks completed")

    @staticmethod
    def __process_return(cb: Callable, error: str, code: int) -> None:
        """
        Process the return value of one of the controller method. If there is an error, this is logged and the CLI exits.

        :param cb: The controller function to run.
        :param error: The error message to display on failure.
        :param code: The exit code to use on error.
        """
        success, data = cb()
        if not success:
            logging.critical(error)
            sys.exit(code)

    @staticmethod
    def preflight_notes() -> bool:
        """
        Perform pre-flight checks for notes synchronisation. This includes ensuring a remote notes folder is checked and
        ensuring associations (i.e. which note folders to sync and how) have been set.

        :return: True if all pre-flight checks are successful.
        """
        if TaskBridgeCli.SETTINGS['remote_notes_folder'] == '':
            logging.critical(
                'Remote notes folder not set. ' +
                'Use --remote-notes-folder to specify or add "remote_notes_folder" to configuration file.')
            sys.exit(13)
        associations = TaskBridgeCli.SETTINGS['associations']
        if len(associations['bi_directional']) == 0 and len(associations['local_to_remote']) == 0 and len(
                associations['remote_to_local']) == 0:
            logging.critical("No folders set for synchronisation." +
                             "Use --notes-bi-directional, --notes-local-to-remote, --notes-remote-to-local to specify or " +
                             "add an associations object in configuration file.")
            sys.exit(13)
        return True

    @staticmethod
    def sync_notes() -> None:
        """
        Calls the varous controller methods to perform note synchronisation. If any stage fails, an error message is logged,
        and the CLI exits with a status code.
        """

        NoteController.REMOTE_NOTE_FOLDER = Path(TaskBridgeCli.SETTINGS['remote_notes_folder'])
        NoteController.ASSOCIATIONS = TaskBridgeCli.SETTINGS['associations']

        # Check if the Notes app is running
        is_notes_running_script = notescript.is_notes_running_script
        return_code, stdout, stderr = helpers.run_applescript(is_notes_running_script)
        notes_was_running = stdout.strip() == 'true'

        # Get folder lists
        logging.info("Fetching local note folders...")
        TaskBridgeCli.__process_return(
            NoteController.get_local_folders,
            "Error fetching local note folders.", 14)

        logging.info("Fetching remote note folders...")
        TaskBridgeCli.__process_return(
            NoteController.get_remote_folders,
            "Error fetching remote note folders.", 15)

        # Sync deletions
        logging.info("Synchronising deleted note folders...")
        TaskBridgeCli.__process_return(
            NoteController.sync_folder_deletions,
            "Error synchronising deleted note folders.", 16)

        # Associate folders
        logging.info("Associating note folders...")
        TaskBridgeCli.__process_return(
            NoteController.associate_folders,
            "Error associating note folders.", 17)

        # Synchronise deleted notes
        logging.info('Synchronising deleted notes...')
        TaskBridgeCli.__process_return(
            NoteController.sync_deleted_notes,
            "Failed to synchronise deleted notes.", 18)

        # Synchronise notes
        logging.info('Synchronising notes...')
        TaskBridgeCli.__process_return(
            NoteController.sync_notes,
            "Failed to synchronise notes.", 19)

        if not notes_was_running:
            quit_notes_script = notescript.quit_notes_script
            helpers.run_applescript(quit_notes_script)

        logging.info("Note synchronisation completed successfully.")

    @staticmethod
    def preflight_reminders() -> bool:
        """
        Perform pre-flight checks for reminders synchronisation. This includes ensuring a CalDAV server, path and username
        have been set, and that the list of reminder lists to sync has been specified.

        :return: True if all pre-flight checks are successful.
        """

        if TaskBridgeCli.SETTINGS['caldav_server'] == '':
            logging.critical(
                'CalDAV server missing. Use --caldav-server to specify or add "caldav_server" to configuration file.')
            sys.exit(4)
        elif TaskBridgeCli.SETTINGS['caldav_path'] == '':
            logging.critical('CalDAV path missing. Use --caldav-path to specify or add "caldav_path" in configuration file.')
            sys.exit(4)
        elif TaskBridgeCli.SETTINGS['caldav_username'] == '':
            logging.critical(
                'CalDAV username missing. Use --caldav-username to specify or add "caldav_username" in configuration file.')
            sys.exit(4)
        elif len(TaskBridgeCli.SETTINGS['reminder_sync']) == 0:
            logging.critical(
                'Reminder lists to sync missing. Use --reminder-sync to specify or add "reminder_sync" in configuration file.')
            sys.exit(4)
        return True

    @staticmethod
    def sync_reminders() -> None:
        """
        Calls the varous controller methods to perform reminder synchronisation. If any stage fails, an error message is
        logged, and the CLI exits with a status code.
        """

        caldav_url = TaskBridgeCli.SETTINGS['caldav_server'] + TaskBridgeCli.SETTINGS['caldav_path']
        ReminderController.CALDAV_URL = caldav_url
        ReminderController.CALDAV_USERNAME = TaskBridgeCli.SETTINGS['caldav_username']
        ReminderController.CALDAV_HEADERS = {}
        ReminderController.CALDAV_PASSWORD = keyring.get_password("TaskBridge", "CALDAV-PWD")
        ReminderController.TO_SYNC = TaskBridgeCli.SETTINGS['reminder_sync']

        # Check if the Reminders app is running
        is_reminders_running_script = reminderscript.is_reminders_running_script
        return_code, stdout, stderr = helpers.run_applescript(is_reminders_running_script)
        reminders_was_running = stdout.strip() == 'true'

        # Connect to remote server
        logging.info("Connecting to remote reminder server...")
        TaskBridgeCli.__process_return(
            ReminderController.connect_caldav,
            "Failed to connect to CalDAV server.", 5)

        # Get reminder lists
        logging.info("Fetching local reminder lists...")
        TaskBridgeCli.__process_return(
            ReminderController.fetch_local_reminders,
            "Error fetching local reminder lists.", 6)
        logging.info("Fetching remote reminder lists...")
        TaskBridgeCli.__process_return(
            ReminderController.fetch_remote_reminders,
            "Error fetching remote reminder lists.", 7)

        # Sync deletions
        logging.info("Synchronising deleted reminder containers...")
        TaskBridgeCli.__process_return(
            ReminderController.sync_deleted_containers,
            "Error synchronising deleted reminder containers.", 8)

        # Associate containers
        logging.info("Associating reminder containers...")
        TaskBridgeCli.__process_return(
            ReminderController.associate_containers,
            "Error associating reminder containers.", 9)

        # Prune completed
        if TaskBridgeCli.SETTINGS['prune_reminders'] == '1':
            logging.info('Pruning completed reminders...')
            TaskBridgeCli.__process_return(
                ReminderController.delete_completed,
                "Failed to prune completed reminders.", 10)

        # Sync reminder deletions
        logging.info('Synchronising deleted reminders...')
        TaskBridgeCli.__process_return(
            ReminderController.sync_deleted_reminders,
            "Failed to synchronise deleted reminders.", 11)

        # Sync reminders
        logging.info('Synchronising reminders...')
        TaskBridgeCli.__process_return(
            ReminderController.sync_reminders,
            "Failed to synchronise reminders.", 12)

        success, data = ReminderController.sync_reminders_to_db()
        if not success:
            logging.warning("Failed to update reminder database.")

        # Quit Reminders if it wasn't running
        if not reminders_was_running:
            quit_reminders_script = reminderscript.quit_reminders_script
            helpers.run_applescript(quit_reminders_script)

        logging.info("Reminder synchronisation completed successfully.")

    def authenticate_caldav(self) -> bool:
        """
        Performs CalDAV authentication. If the --caldav-password option is used, this method will ask for a CalDAV password
        regardless of whether one is saved. If no password is saved, the CLI exits with an error.

        :return: True on finding or receiving a CalDAV password.
        """

        if 'caldav_password' in self.args:
            # User specifically wants to be asked for password
            new_password = getpass('CalDAV Password> ')
            keyring.set_password("TaskBridge", "CALDAV-PWD", new_password)
            return True

        # Check if password is in keyring
        password = keyring.get_password("TaskBridge", "CALDAV-PWD")
        if password is None:
            logging.critical('No CalDAV Password in keyring. Use --caldav-password to be prompted for a password.')
            sys.exit(3)
        return True

    def apply_settings(self) -> None:
        """
        Load settings from the configuration file, This is normally in ~/Library/Application Support/TaskBridge/conf.json,
        but may be overridden with the --config option. Any configuration options specified via command-line options will
        override the values in the configuration file.
        """

        # Load settings from file
        if 'config' in self.args:
            # Load settings from custom configuration file
            if os.path.exists(self.args.config):
                conf_file = self.args.config
                self.logger.info('Using custom config file: {}'.format(conf_file))
            else:
                self.logger.critical('Configuration file {} not found.'.format(self.args.config))
                sys.exit(2)
        else:
            # Load settings from default configuration file
            conf_file = helpers.settings_folder() / 'conf.json'
            self.logger.info('Using default config file: {}'.format(conf_file))

        TaskBridgeCli.merge_settings(conf_file)

        # Override settings from command line arguments
        self.override_config()

        logging.debug("Settings in use: {}".format(json.dumps(TaskBridgeCli.SETTINGS, indent=2)))

    @staticmethod
    def merge_settings(conf_file: str) -> None:
        """
        Override any of the default settings of the TaskBrdige CLI with settings found in a configuration file.
        """

        if os.path.exists(conf_file):
            with open(conf_file) as fp:
                try:
                    content = fp.read()
                    loaded_settings = json.loads(content)
                    for key, value in TaskBridgeCli.SETTINGS.items():
                        if key in loaded_settings.keys():
                            if key == "associations":
                                for sync_dir in ['bi_directional', 'local_to_remote', 'remote_to_local']:
                                    if sync_dir in loaded_settings[key]:
                                        TaskBridgeCli.SETTINGS[key][sync_dir] = loaded_settings[key][sync_dir]
                            else:
                                TaskBridgeCli.SETTINGS[key] = loaded_settings[key]
                except json.decoder.JSONDecodeError:
                    logging.critical("Your configuration file at {} is invalid. Please check syntax.".format(conf_file))
                    sys.exit(20)

    def override_config(self) -> None:
        """
        Override any settings (default or from configuration file) which have been specified as command-line options.
        """

        vargs = vars(self.args)
        for key, value in TaskBridgeCli.SETTINGS.items():
            if key in self.args:
                if key == 'reminder_sync' and self.args.reminder_sync:
                    TaskBridgeCli.SETTINGS[key] = list(csv.reader(self.args.reminder_sync))
                elif key == 'associations':
                    if self.args.notes_bi_directional:
                        TaskBridgeCli.SETTINGS[key]['bi_directional'] = list(csv.reader(self.args.notes_bi_directional))
                    if self.args.notes_local_remote:
                        TaskBridgeCli.SETTINGS[key]['local_to_remote'] = list(csv.reader(self.args.notes_local_remote))
                    if self.args.notes_remote_local:
                        TaskBridgeCli.SETTINGS[key]['remote_to_local'] = list(csv.reader(self.args.notes_remote_local))
                else:
                    TaskBridgeCli.SETTINGS[key] = vargs[key]

    def setup_logging(self) -> logging.Logger:
        """
        Sets up the logging system.

        :return: the logging helper for the CLI.
        """

        if 'log_dir' in self.args:
            if os.access(self.args.log_dir, os.W_OK | os.X_OK):
                log_folder = self.args.log_dir
            else:
                print("Specified log directory {} is not accessible.".format(self.args.log_dir))
                sys.exit(1)
        else:
            log_folder = Path.home() / "Library" / "Logs" / "TaskBridge"
        log_folder.mkdir(parents=True, exist_ok=True)

        log_file = datetime.now().strftime("TaskBridge_%Y%m%d-%H%M%S") + '.log'
        log_levels = {
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'critical': logging.CRITICAL
        }
        log_level = log_levels[self.args.log_level]

        logging.basicConfig(
            level=log_level,
            format='%(asctime)s %(levelname)s: %(message)s',
        )
        if log_file:
            logging.getLogger().addHandler(logging.FileHandler(log_folder / log_file))
        return logging.getLogger()


def main():
    """
    Defines arguments accepted by the CLI.
    """

    parser = argparse.ArgumentParser(
        prog="TaskBridge CLI",
        description="Export your Apple Reminders & Notes to NextCloud, a local folder, or CalDav - and keep them in sync!",
    )

    # TaskBridge options
    parser.add_argument(
        "--sync-notes",
        type=str,
        choices=['0', '1'],
        default=argparse.SUPPRESS,
        help="set to 1 to enable note synchronisation, or 0 to disable it.")
    parser.add_argument(
        "--remote-notes-folder",
        type=str,
        default=argparse.SUPPRESS,
        help="set the location of the folder where remote notes are synchronised.")
    parser.add_argument(
        "--notes-bi-directional",
        type=str,
        default=argparse.SUPPRESS,
        help="note folders which should be bi-directionally synchronised.")
    parser.add_argument(
        "--notes-local-remote",
        type=str,
        default=argparse.SUPPRESS,
        help="note folders which should be synchronised from local to remote.")
    parser.add_argument(
        "--notes-remote-local",
        type=str,
        default=argparse.SUPPRESS,
        help="note folders which should be synchronised from remote to local.")
    parser.add_argument(
        "--sync-reminders",
        type=str,
        choices=['0', '1'],
        default=argparse.SUPPRESS,
        help="set to 1 to enable reminder synchronisation, or 0 to disable it.")
    parser.add_argument(
        "--prune-reminders",
        type=str,
        choices=['0', '1'],
        default=argparse.SUPPRESS,
        help="set to 0 to disable reminder pruning.")
    parser.add_argument(
        "--caldav-server",
        type=str,
        default=argparse.SUPPRESS,
        help="specify the hostname of the CalDAV server.")
    parser.add_argument(
        "--caldav-path",
        type=str,
        default=argparse.SUPPRESS,
        help="specify calendar path on the CalDAV server.")
    parser.add_argument(
        "--caldav-username",
        type=str,
        default=argparse.SUPPRESS,
        help="specify username for CalDAV server.")
    parser.add_argument(
        "--caldav-password",
        default=argparse.SUPPRESS,
        action='store_true',
        help="prompt for CalDAV password.")
    parser.add_argument(
        "--reminder-sync",
        type=str,
        default=argparse.SUPPRESS,
        help="specify reminder lists to be synchronised.")

    # Cli-specific options
    parser.add_argument(
        "--config",
        type=pathlib.Path,
        default=argparse.SUPPRESS,
        help="use to provide a path to a custom configuration file.")
    parser.add_argument(
        "--log-dir",
        type=pathlib.Path,
        default=argparse.SUPPRESS,
        help="specify a custom directory to use for logging.")
    parser.add_argument(
        "--log-level",
        type=str,
        choices=['debug', 'info', 'critical', 'warning'],
        default='info',
        help="specify the logging level.")

    TaskBridgeCli(parser.parse_args())


if __name__ == "__main__":
    main()
