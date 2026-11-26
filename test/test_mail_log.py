import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from gdo.mail_connector.MailLog import log_incoming_mail


class MailLogTest(unittest.TestCase):
    def test_raw_mail_is_private_and_console_only_shows_subject(self):
        raw = b'Subject: Hello\r\nFrom: someone@example.test\r\n\r\nPrivate body\r\n'
        with tempfile.TemporaryDirectory() as temp, \
             patch('gdo.mail_connector.MailLog.Logger._base', temp, create=True), \
             patch('gdo.mail_connector.MailLog.Logger.debug') as debug:
            user = MagicMock()
            user.get_id.return_value = 42
            path = log_incoming_mail(user, raw)
            self.assertEqual(raw, path.read_bytes())
            self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
            self.assertEqual(Path(temp) / 'mail' / '42', path.parent)
            debug.assert_called_once_with('Mail << Hello')
            self.assertNotIn('Private body', debug.call_args.args[0])

    def test_rejects_unsafe_user_and_public_directory(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch('gdo.mail_connector.MailLog.Logger._base', temp, create=True):
            user = MagicMock()
            user.get_id.return_value = '../other'
            with self.assertRaises(ValueError):
                log_incoming_mail(user, b'')
            user.get_id.return_value = 1
            (Path(temp) / 'mail').mkdir(mode=0o755)
            with self.assertRaises(PermissionError):
                log_incoming_mail(user, b'Subject: test\n\nbody')
