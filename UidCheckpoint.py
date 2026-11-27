"""Durable IMAP cursor; delivery must be idempotent across crashes."""
import sqlite3
from contextlib import closing


class UidValidityChanged(RuntimeError):
    pass


class UidCheckpoint:
    def __init__(self, path):
        self.path = str(path)

    def advance(self, mailbox: str, uidvalidity: int, uid: int) -> int:
        if not mailbox or isinstance(uidvalidity, bool) or not isinstance(uidvalidity, int) or uidvalidity < 1:
            raise ValueError('Invalid mailbox or UIDVALIDITY')
        if isinstance(uid, bool) or not isinstance(uid, int) or uid < 0:
            raise ValueError('Invalid UID')
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS cursor (mailbox TEXT PRIMARY KEY, validity INTEGER NOT NULL, uid INTEGER NOT NULL)')
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT validity, uid FROM cursor WHERE mailbox = ?', (mailbox,)).fetchone()
            if row and row[0] != uidvalidity:
                raise UidValidityChanged('Mailbox UIDVALIDITY changed; operator review required')
            last = max(uid, row[1]) if row else uid
            db.execute('INSERT OR REPLACE INTO cursor (mailbox, validity, uid) VALUES (?, ?, ?)',
                       (mailbox, uidvalidity, last))
            return last
