"""
This is a helper file for both note and reminder synchronisation.
"""

from __future__ import annotations

import logging
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from subprocess import Popen, PIPE
from typing import Callable

from caldav import Principal
import markdown2
from markdownify import markdownify as md

DATA_LOCATION: Path = Path.home() / "Library" / "Application Support" / "TaskBridge"  #: Location where application data is
# stored.
DRY_RUN: bool = False  #: If set to true, the user will have to confirm any change made by TaskBridge.
CALDAV_PRINCIPAL: Principal | None = None


def confirm(prompt: str) -> bool:
    """
    If ``DRY_RUN`` is set to True, asks the user to confirm by displaying a prompt. Otherwise, will always return True.

    :param prompt: the confirmation prompt to display.
    :return: True if the action should be carried out.
    """
    if DRY_RUN:
        ans = input(prompt + ':: [Y]/N> ')
        return ans == 'y' or ans == 'Y' or ans == ''
    return True


def run_applescript(script: str, *args) -> tuple[int, str, str]:
    """
    Runs an AppleScript script.

    :param script: the script to run.
    :param args: a list of arguments to send to the script.

    :returns:

        - return_code (:py:class:`int`) - the script's return code.
        - stdout (:py:class:`str`) - standard output from the script.
        - stderr (:py:class:`str`) - standard error from the script.

    """
    arguments = list(args)
    p = Popen(['osascript', '-'] + arguments, stdin=PIPE, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    stdout, stderr = p.communicate(script)
    return p.returncode, stdout, stderr


def get_uuid() -> str:
    """
    Generates a UUID.

    :return: a UUID.
    """
    return str(uuid.uuid4())


def html_to_markdown(html: str) -> str:
    """
    Converts HTML to Markdown using the `Markdownify <https://pypi.org/project/markdownify/>`_ library.

    :param html: the HTML to convert to Markdown.

    :return: the Markdown version of the HTML given.
    """
    mdown = md(html.replace('<ul', '<br><ul'),
               heading_style='ATX',
               newline_style='SPACES')
    mdown = mdown.replace('\n', '  \n')
    return mdown


def markdown_to_html(text: str) -> str:
    """
    Converts Markdown to HTML using the `markdown2 <https://pypi.org/project/markdown2/>`_ library.

    :param text: the Markdown text to convert to HTMl.

    :return: the HTML version of the Markdown given.
    """
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
    """
    Get the location of the SQLite database file.

    :return: path to the SQLite database file.
    """
    DATA_LOCATION.mkdir(parents=True, exist_ok=True)
    return DATA_LOCATION / "TaskBridge.db"


def temp_folder() -> Path:
    """
    Get the location of the ``tmp`` folder within TaskBridge's Application Data folder.

    :return: path to the ``tmp`` folder.
    """
    tmp_folder = DATA_LOCATION / 'tmp/'
    tmp_folder.mkdir(parents=True, exist_ok=True)
    return tmp_folder


def settings_folder() -> Path:
    """
    Get the location of the Application Data folder for TaskBridge

    :return: path to the Application Data folder.
    """
    folder = DATA_LOCATION
    folder.mkdir(parents=True, exist_ok=True)
    return folder


class DateUtil:
    """
    Utility class for converting between several date and date/time formats.
    """

    APPLE_DATETIME = "%A, %d %B %Y at %H:%M:%S"
    APPLE_DATETIME_ALT = "%A %d %B %Y at %H:%M:%S"  # Date export from Notes is inconsistent??
    CALDAV_DATETIME = "%Y%m%dT%H%M%S"
    CALDAV_DATE = "%Y%m%d"
    SQLITE_DATETIME = "%Y-%m-%d %H:%M:%S"

    @staticmethod
    def convert(source_format: str,
                obj: str | datetime,
                required_format: str = '') -> str | datetime | bool:
        """
        Convert one date/datetime format to another.

        :param source_format: the format of the source date/datetime. Can be left empty if ``obj`` is a :py:class:`datetime`
        object.
        :param obj: what to convert from. Can either be a string, or a :py:class:`datetime` object.
        :param required_format: the format required if the required output is of type :py:class:`str`.

        """
        if isinstance(obj, str):
            try:
                return datetime.strptime(obj, source_format)
            except ValueError:
                if source_format == DateUtil.APPLE_DATETIME:
                    try:
                        return datetime.strptime(obj, DateUtil.APPLE_DATETIME_ALT)
                    except ValueError:
                        return False
        if required_format == '':
            return obj
        else:
            try:
                return obj.strftime(required_format)
            except ValueError:
                print('Could not convert date to specified format {}'.format(required_format), file=sys.stderr)
                return False


class FunctionHandler(logging.Handler):
    def __init__(self, func: Callable):
        logging.Handler.__init__(self)
        self.func = func

    def emit(self, record):
        msg = self.format(record)
        self.func(msg)
