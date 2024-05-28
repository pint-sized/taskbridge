"""
Contains the ``Note`` class, which represents a note (whether local or remote), and the ``Attachment`` class, which
represents an attachment within a note.
"""

from __future__ import annotations

import base64
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import List

from taskbridge import helpers
from taskbridge.helpers import DateUtil
from taskbridge.notes.model import notescript


class Note:
    """
    Represents a note. Used to create notes from the local machine via a staged via or from the remote server from
    a Markdown file.
    Can also convert one type to the other.
    """

    def __init__(self,
                 name: str,
                 created_date: datetime.date,
                 modified_date: datetime.date,
                 body_markdown: str = '',
                 body_html: str = '',
                 attachments: List[Attachment] = None,
                 uuid: str | None = None):
        """
        Create a new note.

        :param name: the name of the note. Added to first line of note when rendered
        :param created_date: creation date of the note
        :param modified_date: modification date of the note (same as creation date in local)
        :param body_markdown: the body of the note as markdown
        :param body_html: the body of the note as html
        :param attachments: a list of attachments for this note
        :param uuid: the UUID for this note
        """
        if attachments is None:
            attachments = []
        self.uuid: str = uuid
        self.name: str = name
        self.created_date: datetime.date = created_date
        self.modified_date: datetime.date = modified_date
        self.body_markdown: str = body_markdown
        self.body_html: str = body_html
        self.attachments: List[Attachment] = attachments

    @staticmethod
    def create_from_local(staged_content: str, staged_location: Path) -> Note:
        """
        Creates a Note instance from a staged file exported locally.

        :param staged_content: the content of the staged file.
        :param staged_location: the location of the staged file, used for adding attachments to a ``/.attachments`` dir.
        :return: a Note instance representing the content of the staged file.
        """
        staged_lines = staged_content.splitlines()

        # Meta Data
        uuid, name, c_date, m_date = staged_lines[0].split('~~')
        created_date = DateUtil.convert(DateUtil.APPLE_DATETIME, c_date.strip())
        modified_date = DateUtil.convert(DateUtil.APPLE_DATETIME, m_date.strip())

        # Attachments
        attachments = []
        attachment_end = staged_lines.index("~~END_ATTACHMENTS~~")
        for idx in range(2, attachment_end):
            filename, url = staged_lines[idx].split("~~")
            attachments.append(Attachment(file_name=filename, url=url))

        parsed_attachments = (
            Attachment.parse_local(attachments, staged_lines, Path(os.path.join(staged_location, '.attachments/'))))

        # Body
        body_html = ""
        for idx in range(attachment_end + 1, len(staged_lines)):
            body_html += staged_lines[idx] + "\n"
        body_markdown = Note.staged_to_markdown(staged_lines, parsed_attachments, attachment_end)

        return Note(
            uuid=uuid,
            name=name,
            created_date=created_date,
            modified_date=modified_date,
            body_markdown=body_markdown,
            body_html=body_html,
            attachments=parsed_attachments)

    @staticmethod
    def create_from_remote(remote_content: str, remote_location: Path, remote_file_name: str) -> Note:
        """
        Creates a Note instance from an exported Markdown file.

        :param remote_content: a list of strings from the remote Markdown content.
        :param remote_location: the location of the remote note *excluding file name*.
        :param remote_file_name: the file name of the remote note *excluding path*.
        :return: a Note instance representing the content of the Markdown document.
        """
        remote_lines = remote_content.splitlines()

        # Meta Data
        name = os.path.splitext(remote_file_name)[0]
        created_date = datetime.fromtimestamp(os.path.getctime(remote_location / remote_file_name))
        modified_date = datetime.fromtimestamp(os.path.getmtime(remote_location / remote_file_name))

        # Attachments
        attachments = []
        for idx in range(len(remote_lines)):
            line = remote_lines[idx]
            pattern = r"\(([^)]+\.(?:{}))\)".format(Attachment.get_supported_image_types_string())
            match = re.search(pattern, line)
            if match:
                image_filename = match.group(1)
                image_path = os.path.join(remote_location, image_filename)
                attachments.append(Attachment(
                    file_type=Attachment.TYPE_IMAGE,
                    file_name=image_filename,
                    url=image_path
                ))

        parsed_attachments = Attachment.parse_remote(attachments)

        # Body
        body_markdown = ""
        for idx in range(len(remote_lines)):
            body_markdown += remote_lines[idx] + "\n"
        body_html = Note.markdown_to_html(remote_lines, parsed_attachments)

        return Note(
            name=name,
            created_date=created_date,
            modified_date=modified_date,
            body_markdown=body_markdown,
            body_html=body_html,
            attachments=parsed_attachments)

    @staticmethod
    def staged_to_markdown(staged_lines: List[str], attachments: List[Attachment], attachment_end: int) -> str:
        """
        Converts a Note's body from the HTML in a staged file to Markdown.

        :param staged_lines: a list of lines from the staged file.
        :param attachments: a list of Attachment associated with this note.
        :param attachment_end: the index of the line containing ``~~END ATTACHMENTS~~`` in the staged content.
        :return: a Markdown representation of the note's content.
        """
        md = ""
        image_list = [attachment for attachment in attachments if attachment.file_type == Attachment.TYPE_IMAGE]
        image_index = 0
        for idx in range(attachment_end + 1, len(staged_lines)):
            line = staged_lines[idx]
            if line.startswith("<div><img "):
                try:
                    line = "![{filename}](.attachments/{filename})".format(filename=image_list[image_index].uuid)
                except IndexError:
                    print('Error parsing images of note.', file=sys.stderr)
                image_index += 1
            md += line + "\n"
        return helpers.html_to_markdown(md)

    @staticmethod
    def markdown_to_html(remote_lines: List[str], attachments: List[Attachment]) -> str:
        """
        Converts a Note's body from Markdown to HTML.

        :param remote_lines: a list of Markdown lines.
        :param attachments: A list of Attachment associated with this note.
        :return: an HTML representation of this note's content.
        """
        html = ""
        remote_lines.pop(0)  # First line is note name
        image_list = [attachment for attachment in attachments if
                      attachment and attachment.file_type == Attachment.TYPE_IMAGE]
        image_index = 0
        for idx in range(len(remote_lines)):
            line = remote_lines[idx]
            match = re.search(r"\(.*?\)", line)
            if match:
                f_ext = os.path.splitext(match.group()[1:-1])[1]
                if f_ext in Attachment.get_supported_image_types():
                    image_path = "file://" + image_list[image_index].url
                    line = '<div><img style="max-width: 100%; max-height: 100%;" src="{image_path}"/><br></div>'.format(
                        image_path=image_path)
                    remote_lines[idx] = line
                    image_index += 1
            html += line + "\n"
        return helpers.markdown_to_html(html)

    def create_local(self, folder_name: str) -> tuple[bool, str]:
        """
        Creates this note locally.

        :param folder_name: the name of the folder where this note should be created.
        :returns:

            -success (:py:class:`bool`) - true if the note is successfully created.

            -data (:py:class:`str`) - success message, or error message on failure.

        """
        try:
            temp_file_name = helpers.temp_folder() / (self.name + '.html')
            with open(temp_file_name, 'w') as fp:
                fp.write(self.body_html)
                fp.close()
        except (IOError, OSError) as e:
            return False, 'Failed to export data for local note {0}: {1}'.format(self.name, e)

        create_note_script = notescript.create_note_script
        return_code, stdout, stderr = helpers.run_applescript(
            create_note_script, folder_name, self.name, str(temp_file_name))
        if return_code == 0:
            temp_file_name.unlink()
            return True, 'Created local note {}'.format(self.name)
        return False, 'Error creating local note {0}: {1}'.format(self.name, stderr)

    def update_local(self, folder_name: str) -> tuple[bool, str]:
        """
        Updates this note locally.

        :param folder_name: the name of the folder where this note resides.
        :returns:

            -success (:py:class:`bool`) - true if the note is successfully updated.

            -data (:py:class:`str`) - success message, or error message on failure.

        """
        try:
            temp_file_name = helpers.temp_folder() / (self.name + '.html')
            with open(temp_file_name, 'w') as fp:
                fp.write(self.body_html)
                fp.close()
        except (IOError, OSError) as e:
            return False, 'Failed to export data for local note {0}: {1}'.format(self.name, e)

        update_note_script = notescript.update_note_script
        return_code, stdout, stderr = helpers.run_applescript(
            update_note_script, folder_name, self.name, str(temp_file_name))
        if return_code == 0:
            temp_file_name.unlink()
            return True, 'Updated local note {}'.format(self.name)
        return False, 'Error updating local note {0}: {1}'.format(self.name, stderr)

    def upsert_remote(self, remote_path: Path) -> tuple[bool, str]:
        """
        Upserts the remote note.

        :param remote_path: the path where the remote note resides, *excluding the file name*.
        :returns:

            -success (:py:class:`bool`) - true if the note is successfully upserted.

            -data (:py:class:`str`) - success message, or error message on failure.

        """
        filename = self.name + '.md'
        try:
            with open(remote_path / filename, 'w') as fp:
                fp.write(self.body_markdown)
                fp.close()
            os.utime(remote_path / filename, (self.modified_date.timestamp(), self.modified_date.timestamp()))
        except IOError as e:
            return False, 'Failed to create remote note {0}: {1}'.format(remote_path / filename, e)

        # Attachments
        for attachment in [a for a in self.attachments if a.file_type == Attachment.TYPE_IMAGE]:
            att_path = remote_path / '.attachments/'
            Path(att_path).mkdir(parents=True, exist_ok=True)
            attachment.remote_location = att_path / attachment.uuid
            try:
                shutil.copy2(attachment.url, attachment.remote_location)
            except (FileNotFoundError, TypeError):
                return False, 'Failed to read attachment {}'.format(attachment.staged_location)

        return True, 'Remote note {} created.'.format(remote_path / filename)

    def __str__(self):
        return self.name


class Attachment:
    """
    Represents an attachment in a note.
    """

    #: used to denote that this attachment is an image.
    TYPE_IMAGE: int = 0
    #: used to denote that this attachment is a hyperlink.
    TYPE_LINK: int = 1
    #: used to denote that this attachment is of an unsupported type.
    TYPE_UNSUPPORTED: int = 10

    _SUPPORTED_IMAGE_TYPES = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.apng',
                              '.avif', '.bmp', '.ico', '.tiff', '.svg']

    def __init__(self, file_type: int = '', file_name: str = '', url: str = '', b64_data: str | None = None,
                 uuid: str = ''):
        """
        Creates a new instance of Attachment.

        :param file_type: the type of attachment. Accepts ``Attachment.TYPE_IMAGE``, ``Attachment.TYPE_LINK`` or
        ``Attachment.TYPE_UNSUPPORTED``.
        :param file_name: the file name of the attachment (for images).
        :param url: the url of the attachment (location for images, address for links).
        :param b64_data: the Base64 encoded data of an image.
        :param uuid: the UUID for this attachment.

        """
        self.file_type: int = file_type
        self.file_name: str = file_name
        self.url: str = url
        self.b64_data: str = b64_data
        self.uuid: str = uuid
        self.staged_location: Path | None = None
        self.remote_location: Path | None = None

    def save_image_to_file(self, file_path: Path) -> tuple[bool, Path] | tuple[bool, str]:
        """
        Saves a Base64 image attachment to a file.

        :param file_path: the path where to save the image *excluding file name*.

        :returns:

            -success (:py:class:`bool`) - true if the note is successfully created.

            -data (:py:class:`str` | :py:class:`Path`) - error message on failure, or path to created image.

        """
        img_data_b64 = self.b64_data.split('base64,')[1].encode()
        staged_path = file_path / self.uuid
        try:
            file_path.mkdir(parents=True, exist_ok=True)
            with open(staged_path, 'wb') as fp:
                fp.write(base64.decodebytes(img_data_b64))
                self.staged_location = staged_path
                return True, staged_path
        except OSError:
            return False, 'Could not save remote attachment to {}'.format(staged_path)

    def delete_remote(self) -> tuple[bool, str]:
        """
        Deletes the remote file linked to this attachment.

        :returns:

            -success (:py:class:`bool`) - true if the note is successfully deleted.

            -data (:py:class:`str`) - success message, or error message on failure.

        """
        try:
            Path(self.url).unlink()
        except FileNotFoundError:
            return False, 'Remote attachment could not be found for deletion: {}'.format(self.remote_location)
        return True, 'Remote attachment deleted: {}'.format(self.remote_location)

    @staticmethod
    def parse_local(attachments: List[Attachment], staged_lines: List[str], dest_folder: Path) \
            -> List[Attachment] | tuple[bool, str]:
        """
        Parses attachments from a staged file content into a list of Attachment.

        :param attachments: the list of attachment. Each object should contain the file name
        :param staged_lines: a list of lines from the staged file
        :param dest_folder: the directory where parsed attachments are to be saved (for images)

        :returns:

            -success (:py:class:`bool`) - true if the note is successfully parsed.

            -data (:py:class:`str` | :py:class:`List[Attachment]`) - error message on failure or List[Attachment].

        """
        result = []
        image_index = 0
        for attachment in attachments:
            f_name, f_ext = os.path.splitext(attachment.file_name)
            if f_ext in Attachment._SUPPORTED_IMAGE_TYPES:
                attachment.file_type = Attachment.TYPE_IMAGE
                attachment.b64_data = Attachment._get_local_image(staged_lines, image_index)
                if attachment.b64_data is None:
                    return False, "Warning, could not find Base64 data for image {}".format(attachment.file_name)
                attachment.uuid = helpers.get_uuid() + f_ext
                attachment.save_image_to_file(dest_folder)
                image_index += 1
            elif f_ext == '' and not attachment.url == '':
                attachment.file_type = Attachment.TYPE_LINK
            else:
                attachment.file_type = Attachment.TYPE_UNSUPPORTED
            result.append(attachment)
        return result

    @staticmethod
    def parse_remote(attachments: List[Attachment]) -> List[Attachment]:
        """
        Parses attachments from a remote note and updates Attachment fields

        :param attachments: the list of attachments from the file

        :return: the list of parsed attachments for this note

        """
        result = []
        for attachment in attachments:
            f_name, f_ext = os.path.splitext(attachment.file_name)
            if f_ext in Attachment._SUPPORTED_IMAGE_TYPES:
                attachment.b64_data = Attachment._get_remote_image(attachment.url)
                attachment.uuid = helpers.get_uuid() + f_ext
            result.append(attachment)
        return result

    @staticmethod
    def _get_local_image(staged_lines: List[str], image_index: int) -> str | None:
        """
        Given the lines of a staged file and an index, retrieves the associated image ``src`` attribute.

        :param staged_lines: the lines from a staged file.
        :param image_index: the index of the image attachment to retrieve.
        :returns:

            -success (:py:class:`bool`) - true if image source is retrieved successfully.

            -data (None | :py:class:`str`) - nothing on failure, or the ``src`` attribute.

        """
        current_image = 0
        for line in staged_lines:
            if line.startswith("<div><img "):
                if current_image == image_index:
                    return re.search(r'src="(.*?)"', line).group(1)
                current_image += 1
        return None

    @staticmethod
    def _get_remote_image(url: str) -> str | None:
        """
        Given the path to an image, returns a Base64 representation of the image.

        :param url: the path to the image.
        :returns:

            -success (:py:class:`bool`) - true if image is parsed successfully.

            -data (None | :py:class:`str`) - nothing on failure, or the Base64 image data.

        """
        try:
            with open(url, "rb") as fp:
                encoded_string = base64.b64encode(fp.read()).decode()
                return encoded_string if encoded_string != '' else None
        except FileNotFoundError:
            return None

    @staticmethod
    def get_supported_image_types() -> List[str]:
        """
        Get a list of supported image types.

        :return: a list of supported image types.
        """
        return Attachment._SUPPORTED_IMAGE_TYPES

    @staticmethod
    def get_supported_image_types_string() -> str:
        """
        Get a list of supported image types as a pipe-separated string.

        :return: a list of supported image types as a pipe-separated string.
        """
        return '|'.join(att[1:] for att in Attachment._SUPPORTED_IMAGE_TYPES)
