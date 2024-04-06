import datetime
import logging
import sys
from pathlib import Path

import helpers
from taskbridge.notes import controller as notes_controller
from taskbridge.reminders import controller as reminder_controller

# DRY RUN
helpers.DRY_RUN = True

# Notes Settings
nc_notes_folder = Path('/Users/keith/Nextcloud/Notes/')
associations = {
    'bi_directional': ['Sync'],
    'local_to_remote': ['Notes', 'Archive', 'Recipes', 'Shared', 'Work'],
    'remote_to_local': ['ncprimary']
}

# Reminders Settings
caldav_url = "https://nextcloud.vassallo.cloud/remote.php/dav/calendars/Admin"
username = "Admin"
password = "qrb_qbm*KAB3cpy@bxz"
headers = {}
to_sync = ['Sync', 'ncprimary']

# Logging Settings
log_folder = Path.home() / "Library" / "Logs" / "TaskBridge"
log_folder.mkdir(parents=True, exist_ok=True)
log_file = datetime.datetime.now().strftime("TaskBridge_%Y%m%d-%H%M%S") + '.log'
log_level = logging.DEBUG
logging.basicConfig(
    level=log_level,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(log_folder / log_file),
        logging.StreamHandler(sys.stdout)
    ]
)


def do_sync():
    print('Synchronising Reminders...')
    reminder_controller.sync(caldav_url, username, password, headers, to_sync)
    print('Reminders Synchronised Successfully.')
    print('Synchronising Notes...')
    notes_controller.sync(nc_notes_folder, associations)
    print('Notes Synchronised Successfully.')


do_sync()

# def run_threaded(job_func):
#     job_thread = threading.Thread(target=job_func)
#     job_thread.start()
#
#
# schedule.every(2).minutes.do(run_threaded, do_sync)
#
# while True:
#     n = schedule.idle_seconds()
#     next_sync = (datetime.datetime.now() + datetime.timedelta(0, n)).strftime('%H:%M:%S')
#     print('Next sync in {s:0.0f} seconds at {d}'.format(s=n, d=next_sync))
#     time.sleep(1)
#     schedule.run_pending()

# https://schedule.readthedocs.io/en/stable/background-execution.html
