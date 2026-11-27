"""Private, UID-addressed copies of incoming RFC 822 mail."""
import hashlib
import os
from pathlib import Path


class MailArchive:
    def __init__(self, root):
        self.root = Path(root)

    def store(self, mailbox: str, uidvalidity: int, uid: int, raw: bytes) -> Path:
        if not isinstance(mailbox, str) or not mailbox:
            raise ValueError('Mailbox identity is required')
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 1
               for value in (uidvalidity, uid)):
            raise ValueError('Invalid IMAP UID or UIDVALIDITY')
        if not isinstance(raw, bytes):
            raise TypeError('Mail must be bytes')
        directory = self.root / hashlib.sha256(mailbox.encode('utf-8')).hexdigest()
        directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        if directory.is_symlink() or directory.stat().st_mode & 0o077:
            raise PermissionError('Mail archive directory must be private')
        path = directory / f'{uidvalidity}-{uid}.eml'
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != raw:
                raise ValueError('Existing archive does not match this IMAP message')
            return path
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
        return path
