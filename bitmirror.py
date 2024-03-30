import os
import threading
import time
import datetime

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
    print('Reminders Synchronised Successfully.')
    print('Synchronising Notes...')
    notes_sync.sync(NC_NOTES_FOLDER, FOLDERS_BI_DIRECTIONAL, FOLDERS_LOCAL_TO_REMOTE, FOLDERS_REMOTE_TO_LOCAL)
    print('Notes Synchronised Successfully.')


def run_threaded(job_func):
    job_thread = threading.Thread(target=job_func)
    job_thread.start()


schedule.every(2).minutes.do(run_threaded, do_sync)

while True:
    n = schedule.idle_seconds()
    next_sync = (datetime.datetime.now() + datetime.timedelta(0, n)).strftime('%H:%M:%S')
    print('Next sync in {s:0.0f} seconds at {d}'.format(s=n, d=next_sync))
    time.sleep(1)
    schedule.run_pending()

# https://schedule.readthedocs.io/en/stable/background-execution.html
