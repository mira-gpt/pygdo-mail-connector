"""Logging for mail already associated with a verified Dog user."""
import os
import re
import uuid
from email import policy
from email.parser import BytesParser
from pathlib import Path

from gdo.base.Logger import Logger


def log_incoming_mail(user, raw_message: bytes) -> Path:
    """Store the original RFC 822 message privately, then log only its subject.

    The caller is responsible for verifying the sender before associating a
    message with a user.  This function does not authenticate messages.
    """
    user_id = str(user.get_id())
    if not user_id.isascii() or not user_id.isdecimal():
        raise ValueError('A persisted numeric user ID is required')
    if not isinstance(raw_message, bytes):
        raise TypeError('Mail must be supplied as original bytes')
    parsed = BytesParser(policy=policy.default).parsebytes(raw_message, headersonly=True)
    subject = str(parsed.get('Subject', '(no subject)'))
    subject = re.sub(r'[\x00-\x1f\x7f-\x9f\u2028\u2029]+', ' ', subject)[:300]
    root = Path(Logger._base) / 'mail'
    root.mkdir(mode=0o700, exist_ok=True)
    if root.is_symlink() or root.stat().st_mode & 0o077:
        raise PermissionError('Mail log directory is not private')
    directory = root / user_id
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink() or directory.stat().st_mode & 0o077:
        raise PermissionError('Mail log directory is not private')
    path = directory / (uuid.uuid4().hex + '.eml')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw_message)
    Logger.debug(f'Mail << {subject}')
    return path
