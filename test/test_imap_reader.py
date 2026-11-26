import unittest
from unittest.mock import MagicMock, patch

from gdo.mail_connector.ImapReader import ImapReader


class ImapReaderTest(unittest.IsolatedAsyncioTestCase):
    async def test_readonly_connect_fetch_and_close(self):
        client = MagicMock()
        client.select.return_value = ('OK', [b'2'])
        client.uid.side_effect = [
            ('OK', [b'4 5']),
            ('OK', [b'1 (RFC822.SIZE 4)']),
            ('OK', [(b'1 (BODY[] {4}', b'test'), b')']),
            ('OK', [b'2 (RFC822.SIZE 999999)']),
        ]
        reader = ImapReader('example.test', 993, 'user', 'secret')
        with patch('gdo.mail_connector.ImapReader.imaplib.IMAP4_SSL', return_value=client):
            await reader.connect()
            result = await reader.fetch_after(3)
            await reader.close()
        self.assertEqual([(4, b'test'), (5, None)], result)
        client.select.assert_called_once_with('INBOX', readonly=True)
        self.assertEqual(('fetch', '4', '(BODY.PEEK[])'), client.uid.call_args_list[2].args)
        client.logout.assert_called_once_with()

    async def test_bad_uid_and_disconnected_reader_are_rejected(self):
        reader = ImapReader('example.test', 993, 'user', 'secret')
        with self.assertRaises(RuntimeError):
            await reader.fetch_after(0)
        reader.client = MagicMock()
        for invalid in (-1, True, '1'):
            with self.assertRaises(ValueError):
                await reader.fetch_after(invalid)

    async def test_bad_size_does_not_fetch_body(self):
        reader = ImapReader('example.test', 993, 'user', 'secret')
        reader.client = MagicMock()
        reader.client.uid.side_effect = [('OK', [b'1']), ('OK', [b'invalid'])]
        with self.assertRaises(RuntimeError):
            await reader.fetch_after(0)
        self.assertEqual(2, reader.client.uid.call_count)
