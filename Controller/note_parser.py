import base64
import os.path
import random
import re
import string
from datetime import datetime
from pathlib import Path
from typing import List

from Model import Util


def from_html(staged_content: str, staged_folder: str) -> tuple[str, datetime, List[dict], str]:
    partitioned_string = staged_content.splitlines()

    # Get the metadata we're interested in
    note_meta = partitioned_string[0].split("~~")
    name = note_meta[1]
    modification_date = Util.get_apple_datetime(note_meta[3].strip())

    # Get the list of attachments
    attachments = []
    attachment_end = partitioned_string.index("~~END_ATTACHMENTS~~")
    for idx in range(2, attachment_end):
        filename, url = partitioned_string[idx].split("~~")
        attachments.append({
            'filename': filename,
            'url': url
        })

    # Get the type of each attachment
    image_index = 0
    for attachment in attachments:
        image_ext = ['.png', '.jpg', '.jpeg', '.gif']
        att_name, att_ext = os.path.splitext(attachment['filename'])
        if att_ext in image_ext:
            # This is an image attachment
            attachment['type'] = 'image'
            attachment['data'] = get_local_image(partitioned_string, image_index)
            attachment['random'] = ''.join(random.choices(string.ascii_uppercase + string.digits, k=15)) + att_ext
            img_base64_file(attachment, staged_folder)
            image_index += 1
        elif att_ext == "":
            # This is a link
            attachment['type'] = 'link'
        else:
            # Unsupported attachment type
            attachment['type'] = 'unsupported'

    # Get body
    body = html_to_markdown(partitioned_string, attachments, attachment_end)

    return name, modification_date, attachments, body


def from_markdown(remote_content: str, remote_folder: str) -> tuple[str, str]:
    partitioned_string = remote_content.splitlines()
    note_name = partitioned_string[0].replace('#', '').strip()

    for idx in range(len(partitioned_string)):
        line = partitioned_string[idx]
        match = re.search(r"\(([^)]+\.(?:jpg|jpeg|png))\)", line)
        if match:
            image_filename = match.group(1)
            image_path = "file://" + remote_folder + '/' + image_filename
            line = '<div><img style="max-width: 100%; max-height: 100%;" src="{image_path}"/><br></div>'.format(image_path=image_path)
            partitioned_string[idx] = line

    body = markdown_to_html(partitioned_string)
    with open('/tmp/note_input.html', 'w') as fp:
        fp.write(body)
        fp.close()

    return note_name, '/tmp/note_input.html'


def get_local_image(staged_note: List[str], image_index: int) -> str | None:
    current_image = 0
    for line in staged_note:
        if line.startswith("<div><img "):
            if current_image == image_index:
                return re.search(r'src="(.*?)"', line).group(1)
            current_image += 1
    return None


def img_base64_file(attachment: dict, staged_folder: str) -> None:
    base64_img = attachment['data'].split('base64,')[1].encode()
    Path(staged_folder + '/.attachments/').mkdir(parents=True, exist_ok=True)
    with open(staged_folder + '/.attachments/' + attachment['random'], 'wb') as fp:
        fp.write(base64.decodebytes(base64_img))


def html_to_markdown(body: List[str], attachments: List[dict], body_offset: int) -> str:
    """
    Convert HTML attachment references to Markdown attachment references
    :param body:
    :param attachments:
    :param body_offset:
    :return:
    """
    result = ""
    image_list = [item for item in attachments if item['type'] == 'image']
    image_index = 0
    for idx in range(body_offset + 1, len(body)):
        line = body[idx]
        if line.startswith("<div><img "):
            line = "![{filename}](.attachments/{filename})".format(filename=image_list[image_index]['random'])
            image_index += 1
        result += line
    return Util.html_to_markdown(result)


def markdown_to_html(body: List[str]) -> str:
    body.pop(0)  # First line is note name
    content = '\n'.join(body)
    return Util.markdown_to_html(content)