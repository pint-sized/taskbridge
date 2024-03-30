import os
import time

import schedule

from Controller import reminder_sync, notes_sync


# Notes Settings
NC_NOTES_FOLDER = '/Users/keith/Nextcloud/Notes/'
FOLDERS_BI_DIRECTIONAL = ['Sync']
FOLDERS_LOCAL_TO_REMOTE = ['Notes', 'Recipes', 'Shared', 'Work']
FOLDERS_REMOTE_TO_LOCAL = []

# Reminders Settings
caldav_url = "https://nextcloud.vassallo.cloud/remote.php/dav/calendars/Admin"
username = "Admin"
password = "qrb_qbm*KAB3cpy@bxz"
headers = {}


def do_sync():
    print('Synchronising Reminders...')
    reminder_sync.sync(caldav_url, username, password, headers)
    print('Synchronising Notes...')
    notes_sync.sync(NC_NOTES_FOLDER, FOLDERS_BI_DIRECTIONAL, FOLDERS_LOCAL_TO_REMOTE, FOLDERS_REMOTE_TO_LOCAL)


notes_sync.sync(NC_NOTES_FOLDER, FOLDERS_BI_DIRECTIONAL, FOLDERS_LOCAL_TO_REMOTE, FOLDERS_REMOTE_TO_LOCAL)

# schedule.every(10).minutes.do(do_sync)
#
# while True:
#     schedule.run_pending()
#     time.sleep(1)
