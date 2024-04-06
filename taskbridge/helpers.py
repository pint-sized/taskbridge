"""
This is a helper file
"""

from __future__ import annotations

import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from subprocess import Popen, PIPE

from caldav import Principal
import markdown2
from markdownify import markdownify as md

DATA_LOCATION: Path = Path.home() / "Library" / "Application Support" / "TaskBridge"
DRY_RUN: bool = True
CALDAV_PRINCIPAL: Principal | None = None


def confirm(prompt: str) -> bool:
    if DRY_RUN:
        ans = input(prompt + ':: [Y]/N> ')
        return ans == 'y' or ans == 'Y' or ans == ''
    return True


def run_applescript(script: str, *args) -> tuple[int, str, str]:
    arguments = list(args)
    p = Popen(['osascript', '-'] + arguments, stdin=PIPE, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    stdout, stderr = p.communicate(script)
    return p.returncode, stdout, stderr


def get_uuid() -> str:
    return str(uuid.uuid4())


def html_to_markdown(html: str) -> str:
    mdown = md(html.replace('<ul', '<br><ul'),
               heading_style='ATX',
               newline_style='SPACES')
    mdown = mdown.replace('\n', '  \n')
    return mdown


def markdown_to_html(text: str) -> str:
    html = markdown2.markdown(text, extras={
        'breaks': {'on_newline': True, 'on_backslash': True},
        'cuddled-lists': None
    })
    build = ''
    for line in html.split('\n'):
        build += '<br>' if re.match(r'^\s*$', line) else line
        build += '\n'
    return build


def db_folder() -> Path:
    DATA_LOCATION.mkdir(parents=True, exist_ok=True)
    return DATA_LOCATION / "TaskBridge.db"


def temp_folder() -> Path:
    tmp_folder = DATA_LOCATION / 'tmp/'
    tmp_folder.mkdir(parents=True, exist_ok=True)
    return tmp_folder


class DateUtil:
    APPLE_DATETIME = "%A, %d %B %Y at %H:%M:%S"
    APPLE_DATETIME_ALT = "%A %d %B %Y at %H:%M:%S"  # Date export from Notes is inconsistent??
    CALDAV_DATETIME = "%Y%m%dT%H%M%S"
    CALDAV_DATE = "%Y%m%d"
    SQLITE_DATETIME = "%Y-%m-%d %H:%M:%S"

    @staticmethod
    def convert(source_format: str,
                obj: str | datetime,
                required_format: str = '') -> str | datetime | bool:
        if isinstance(obj, str):
            try:
                return datetime.strptime(obj, source_format)
            except ValueError:
                if source_format == DateUtil.APPLE_DATETIME:
                    try:
                        return datetime.strptime(obj, DateUtil.APPLE_DATETIME_ALT)
                    except ValueError:
                        return False
                return False
        if required_format == '':
            return obj
        else:
            try:
                return obj.strftime(required_format)
            except ValueError:
                print('Could not convert date to specified format {}'.format(required_format), file=sys.stderr)
                return False
