import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from gdo.mail_connector.IncomingPoller import IncomingPoller
from gdo.mail_connector.MailArchive import MailArchive
from gdo.mail_connector.UidCheckpoint import UidCheckpoint
from gdo.mail_connector.connector.Mail import Mail
from gdo.mail_connector.IncomingMail import parse_incoming


class IncomingPollerTest(unittest.IsolatedAsyncioTestCase):
    async def test_userstuff_and_inbox_are_independent(self):
        connector = Mail()
        parsed = parse_incoming(b'From: owner@example.test\r\n\r\n.ping')
        module = MagicMock()
        with patch('gdo.mail_connector.module_mail_connector.module_mail_connector.instance', return_value=module), \
             patch.object(connector, '_incoming_message', new_callable=AsyncMock) as dispatch, \
             patch('gdo.mira.util.send_to_mira') as send:
            module.get_config_value.side_effect = lambda key: key == 'mail_connector_userstuff'
            await connector._incoming_mail(Path('/archive/message.eml'), parsed)
            dispatch.assert_awaited_once_with(parsed)
            send.assert_not_called()
            dispatch.reset_mock()
            module.get_config_value.return_value = False
            module.get_config_value.side_effect = None
            await connector._incoming_mail(Path('/archive/message.eml'), parsed)
            dispatch.assert_not_awaited()

    async def test_userstuff_uses_unauthenticated_ghost(self):
        connector = Mail()
        connector._server = MagicMock()
        parsed = parse_incoming(b'From: owner@example.test\r\nReturn-Path: <other@example.test>\r\nSubject: Hi\r\n\r\n.ping')
        ghost = MagicMock()
        message = MagicMock()
        message.env_server.return_value = message
        message.execute = AsyncMock()
        with patch('gdo.core.GDO_User.GDO_User.ghost', return_value=ghost), \
             patch('gdo.base.Message.Message', return_value=message):
            await connector._incoming_message(parsed)
        message.env_user.assert_called_once_with(ghost, True)
        message.platform_identity.assert_called_once_with(None, trusted=False)
        self.assertEqual('owner@example.test', message.mail_claimed_from)
        self.assertEqual('other@example.test', message.mail_envelope_from)
        message.execute.assert_awaited_once()

    async def test_connector_connects_polls_handoffs_and_disconnects(self):
        with tempfile.TemporaryDirectory() as temp:
            reader = MagicMock()
            reader.client = object()
            reader.connect = AsyncMock()
            reader.uidvalidity = AsyncMock(return_value=7)
            reader.fetch_after = AsyncMock(return_value=[(2, b'From: a@example.test\r\n\r\nHello')])
            waiting = asyncio.Event()
            async def wait_for_activity(_):
                await waiting.wait()
            reader.wait_for_activity = AsyncMock(side_effect=wait_for_activity)
            reader.close = AsyncMock()
            module = MagicMock()
            values = {'mail_connector_imap_host': 'mail.example', 'mail_connector_imap_user': 'user',
                      'mail_connector_imap_password': 'test', 'mail_connector_imap_folder': 'INBOX'}
            module.get_config_val.side_effect = values.get
            module.get_config_value.side_effect = lambda key: 993 if key == 'mail_connector_imap_port' else key == 'mail_connector_mira_inbox'
            connector = Mail()
            with patch('gdo.mail_connector.module_mail_connector.module_mail_connector.instance', return_value=module), \
                 patch('gdo.mail_connector.ImapReader.ImapReader', return_value=reader), \
                 patch('gdo.mail_connector.connector.Mail.Application.files_path', return_value=str(Path(temp) / 'mails')), \
                 patch('gdo.mira.util.send_to_mira') as send:
                self.assertTrue(await connector.gdo_connect())
                for _ in range(100):
                    if send.called:
                        break
                    await asyncio.sleep(0.01)
                self.assertTrue(send.called)
                await connector.gdo_disconnect()
            reader.connect.assert_awaited_once()
            reader.close.assert_awaited_once()
            self.assertFalse(connector.is_connected())

    async def test_poll_archives_and_sends_inbox_event(self):
        with tempfile.TemporaryDirectory() as temp:
            reader = AsyncMock()
            reader.uidvalidity.return_value = 7
            reader.fetch_after.return_value = [(2, b'From: a@example.test\r\n\r\nHello')]
            connector = Mail()
            module = MagicMock()
            module.get_config_value.side_effect = lambda key: key == 'mail_connector_mira_inbox'
            poller = IncomingPoller(reader, UidCheckpoint(Path(temp) / 'cursor.sqlite'),
                                    MailArchive(Path(temp) / 'mails'), 'box', connector._incoming_mail)
            with patch('gdo.mail_connector.module_mail_connector.module_mail_connector.instance', return_value=module), \
                 patch('gdo.mira.util.send_to_mira') as send:
                self.assertEqual(1, await poller.poll_once())
            event = send.call_args.args[0]
            self.assertTrue(event.startswith('$inbox '))
            self.assertTrue(Path(event[len('$inbox '):]).is_file())
            self.assertEqual({'interrupt': False}, send.call_args.kwargs)

    async def test_archive_then_deliver_then_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            reader = AsyncMock()
            reader.uidvalidity.return_value = 42
            raw = b'From: a@example.test\r\nSubject: Hello\r\n\r\nBody'
            reader.fetch_after.return_value = [(3, raw)]
            callback = AsyncMock()
            checkpoint = UidCheckpoint(Path(temp) / 'cursor.sqlite')
            poller = IncomingPoller(reader, checkpoint, MailArchive(Path(temp) / 'mails'), 'mailbox/INBOX', callback)
            self.assertEqual(1, await poller.poll_once())
            path, parsed = callback.await_args.args
            self.assertEqual(raw, path.read_bytes())
            self.assertEqual(0o600, path.stat().st_mode & 0o777)
            self.assertEqual('a@example.test', parsed.claimed_from)
            self.assertEqual(3, checkpoint.advance('mailbox/INBOX', 42, 0))

    async def test_failed_delivery_retries_without_advancing(self):
        with tempfile.TemporaryDirectory() as temp:
            reader = AsyncMock()
            reader.uidvalidity.return_value = 42
            reader.fetch_after.return_value = [(3, b'Subject: Hi\r\n\r\nBody')]
            callback = AsyncMock(side_effect=[RuntimeError('failed'), None])
            checkpoint = UidCheckpoint(Path(temp) / 'cursor.sqlite')
            poller = IncomingPoller(reader, checkpoint, MailArchive(Path(temp) / 'mails'), 'box', callback)
            with self.assertRaises(RuntimeError):
                await poller.poll_once()
            self.assertEqual(0, checkpoint.advance('box', 42, 0))
            self.assertEqual(1, await poller.poll_once())
